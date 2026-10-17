"""Fixed-destination inference gateway. No model API calls occur at import."""

import argparse
import http.client
import http.server
import ipaddress
import json
import os
from pathlib import Path
import socket
import socketserver
import ssl
from urllib.parse import urlsplit

MAX_BODY = 32 * 1024 * 1024
MAX_RESPONSE = 128 * 1024 * 1024
FORBIDDEN_KEYS = {"previous_response_id", "conversation", "conversation_id", "thread", "thread_id", "assistant_id", "vector_store_ids", "file_id", "file_ids", "mcp_servers", "container", "models", "plugins", "video_url", "audio_url", "file_url", "document_url", "fallbacks", "provider"}
TOP_LEVEL_KEYS = {"model", "messages", "input", "tools", "tool_choice", "stream", "stream_options", "max_tokens", "max_completion_tokens", "max_output_tokens", "temperature", "top_p", "top_k", "stop", "stop_sequences", "presence_penalty", "frequency_penalty", "seed", "logprobs", "top_logprobs", "logit_bias", "response_format", "reasoning", "reasoning_effort", "verbosity", "system", "metadata", "thinking", "service_tier", "store", "prompt_cache_key", "prompt_cache_retention", "user", "context_management", "include", "safety_identifier", "text", "parallel_tool_calls"}
ROUTES = ("/chat/completions", "/responses", "/messages")
IDENTITY_HEADERS = ("user-agent", "x-opencode-session", "x-opencode-request", "x-opencode-client")


def identity_headers(received):
    headers = {}
    for name in IDENTITY_HEADERS:
        values = received.get_all(name, [])
        if len(values) > 1:
            raise ValueError("Duplicate client identity header")
        if values:
            value = values[0]
            if not 1 <= len(value) <= 256 or any(not 32 <= ord(char) <= 126 for char in value):
                raise ValueError("Invalid client identity header")
            headers[name] = value
    return headers


def public_addresses(host, port):
    values = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    if not values or any(not ipaddress.ip_address(value).is_global for value in values):
        raise ValueError("API destination must resolve exclusively to public addresses")
    return sorted(values)


def validate_base_url(value, resolve=True):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port not in (None, 443)
            or "%" in parsed.netloc or "\\" in value or ".." in parsed.path
            or "%" in parsed.path or "//" in parsed.path):
        raise ValueError("API base URL must be a public HTTPS origin and simple fixed path")
    if resolve:
        public_addresses(parsed.hostname, 443)
    return parsed


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are forbidden")
        result[key] = value
    return result


def validate_body(raw, model):
    data = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(data, dict) or data.get("model") != model:
        raise ValueError("Only the configured exact model is allowed")
    if set(data) - TOP_LEVEL_KEYS or data.get("store") not in (None, False):
        raise ValueError("Unsupported inference options or remote persistence")

    def visit(value):
        if isinstance(value, dict):
            if FORBIDDEN_KEYS.intersection(value):
                raise ValueError("Remote history and file references are forbidden")
            if value.get("type") in {"input_file", "file", "file_search", "web_search", "web_search_preview", "mcp", "computer", "computer_use", "code_interpreter", "video", "video_url", "audio_url", "document"}:
                raise ValueError("Provider-managed tools and files are forbidden")
            if "image_url" in value:
                image = value["image_url"]
                url = image.get("url") if isinstance(image, dict) else image
                if not isinstance(url, str) or not url.startswith("data:image/"):
                    raise ValueError("Only inline image data is allowed")
            if isinstance(value.get("source"), dict) and value["source"].get("type") == "url":
                raise ValueError("Remote content sources are forbidden")
            for key, nested in value.items():
                if key not in {"tools", "parameters", "input_schema", "response_format"}:
                    visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(data)
    tools = data.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tools must be a list")
    for tool in tools:
        if not isinstance(tool, dict) or (tool.get("type") != "function" and not
                (tool.get("type") is None and isinstance(tool.get("name"), str) and isinstance(tool.get("input_schema"), dict))):
            raise ValueError("Only client-executed custom function tools are allowed")
    return data


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        address = public_addresses(self.host, self.port)[0]
        raw = socket.create_connection((address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    address_family = getattr(socket, "AF_UNIX", socket.AF_INET)
    daemon_threads = True


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "InferenceGateway"

    def log_message(self, *_):
        pass

    def do_POST(self):
        connection = None
        status = 400
        response_started = False
        try:
            policy = self.server.policy
            parsed = validate_base_url(policy["base_url"], resolve=False)
            prefix = parsed.path.rstrip("/")
            if self.path not in {prefix + route for route in ROUTES}:
                raise ValueError("Inference route is not allowed")
            if self.headers.get("Transfer-Encoding") or self.headers.get("Upgrade"):
                raise ValueError("Transfer-Encoding and Upgrade are forbidden")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isdigit():
                raise ValueError("One Content-Length header is required")
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise ValueError("Request size exceeds policy")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Truncated request")
            validate_body(raw, policy["model"])
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            headers.update(identity_headers(self.headers))
            for name in ("anthropic-version", "anthropic-beta"):
                if self.headers.get(name):
                    headers[name] = self.headers[name]
            if policy.get("credential"):
                headers["Authorization"] = "Bearer " + policy["credential"]
                if self.path.endswith("/messages"):
                    headers["x-api-key"] = policy["credential"]
            elif parsed.hostname == "opencode.ai" and prefix == "/zen/v1" and policy["model"].endswith("-free"):
                headers["Authorization"] = "Bearer public"
            connection = self.server.connection_factory(parsed.hostname, 443, timeout=60, context=ssl.create_default_context())
            connection.request("POST", self.path, body=raw, headers=headers)
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise ValueError("Upstream redirects are forbidden")
            status = response.status
            self.send_response(status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Connection", "close")
            self.end_headers()
            response_started = True
            self.close_connection = True
            total = 0
            while chunk := response.read1(65536):
                total += len(chunk)
                if total > MAX_RESPONSE:
                    raise ValueError("Response size exceeds policy")
                self.wfile.write(chunk)
                self.wfile.flush()
        except (ValueError, OSError, http.client.HTTPException, json.JSONDecodeError):
            if not response_started:
                self.send_error(400, "Request rejected by inference policy")
            self.close_connection = True
        finally:
            if connection is not None:
                connection.close()
            print(json.dumps({"type": "gateway_request", "status": status}), flush=True)

    def _deny(self):
        self.send_error(405, "Only inference POST requests are allowed")
        self.close_connection = True

    do_GET = do_HEAD = do_PUT = do_DELETE = do_PATCH = do_CONNECT = do_OPTIONS = _deny


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--credential-file")
    args = parser.parse_args()
    validate_base_url(args.base_url)
    credential = Path(args.credential_file).read_text().strip() if args.credential_file else ""
    path = Path(args.socket)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("API socket must be fresh")
    with UnixHTTPServer(str(path), GatewayHandler) as server:
        os.chmod(path, 0o660)
        server.policy = {"base_url": args.base_url, "model": args.model, "credential": credential}
        server.connection_factory = PinnedHTTPSConnection
        print(json.dumps({"type": "gateway_ready"}), flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
