"""Local HTTP and Unix-socket fixtures only; no external or model requests."""

import http.client
import http.server
from email.message import Message
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "container"))
import gateway
import loopback_adapter


class Upstream(http.server.BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.calls.append((self.path, dict(self.headers), body))
        self.send_response(302 if self.server.redirect else 200)
        self.send_header("Content-Type", "text/event-stream")
        if self.server.redirect:
            self.send_header("Location", "http://127.0.0.1/secret")
        self.end_headers()
        self.wfile.write(b'data: {"tool_calls":[]}\n\ndata: [DONE]\n\n')


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="uds-")
        self.addCleanup(self.temp.cleanup)
        self.upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        self.upstream.calls, self.upstream.redirect = [], False
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), gateway.GatewayHandler)
        self.server.policy = {"base_url": "https://api.example.org/v1", "model": "selected", "credential": "fixture-key"}
        self.server.connection_factory = lambda *a, **kw: http.client.HTTPConnection("127.0.0.1", self.upstream.server_port, timeout=3)
        for server in (self.upstream, self.server):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)

    def request(self, body, path="/v1/chat/completions", method="POST", headers=(), port=None):
        connection = http.client.HTTPConnection("127.0.0.1", port or self.server.server_port, timeout=4)
        try:
            body = body.encode() if isinstance(body, str) else body
            connection.putrequest(method, path)
            for name, value in (("Authorization", "Bearer candidate-supplied"), ("Content-Type", "application/json"),
                                ("Content-Length", str(len(body))), *headers):
                connection.putheader(name, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_custom_tool_schema_and_sse_pass_through(self):
        body = {"model": "selected", "tools": [{"type": "function", "function": {"name": "execute_code", "parameters": {"type": "object", "properties": {"code": {"type": "string"}, "file_id": {"type": "string"}, "image_url": {"type": "string"}}}}}], "messages": [{"role": "user", "content": "fixture"}]}
        status, output = self.request(json.dumps(body))
        self.assertEqual(status, 200)
        self.assertEqual(output, b'data: {"tool_calls":[]}\n\ndata: [DONE]\n\n')
        path, headers, raw = self.upstream.calls[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer fixture-key")
        self.assertFalse(set(gateway.IDENTITY_HEADERS) & {name.lower() for name in headers})
        self.assertEqual(json.loads(raw), body)

    def test_policy_rejections_never_touch_upstream(self):
        bad_bodies = [b'{"model":"selected","model":"selected"}', b'{"model":"other"}',
                      b'{"model":"selected","previous_response_id":"other-history"}',
                      b'{"model":"selected","tools":[{"type":"web_search"}]}',
                      b'{"model":"selected","models":["other"]}',
                      b'{"model":"selected","plugins":[{"id":"web"}]}',
                      b'{"model":"selected","messages":[{"content":[{"type":"video_url","video_url":{"url":"https://private/video"}}]}]}',
                      b'{"model":"selected","messages":[{"content":[{"type":"image_url","image_url":{"url":"https://private/file"}}]}]}']
        for body in bad_bodies:
            with self.subTest(body=body):
                self.assertEqual(self.request(body)[0], 400)
        for path in ("https://example.org/v1/responses", "/v1/%2e%2e/responses", "/v1/models", "/v1/responses?target=other"):
            self.assertEqual(self.request(b'{"model":"selected"}', path)[0], 400)
        self.assertEqual(self.request(b"", method="CONNECT")[0], 405)
        self.assertEqual(self.upstream.calls, [])

    def test_redirect_is_not_followed(self):
        self.upstream.redirect = True
        status, _ = self.request(b'{"model":"selected"}')
        self.assertNotEqual(status, 200)
        self.assertEqual(len(self.upstream.calls), 1)

    def test_private_dns_and_non_https_rejected(self):
        for address in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1"):
            with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 443))]):
                with self.assertRaises(ValueError):
                    gateway.validate_base_url("https://api.example.org/v1")
        for value in ("http://example.org/v1", "https://user:pass@example.org/v1", "https://example.org/v1?x=1", "https://example.org:9875/v1"):
            with self.assertRaises(ValueError):
                gateway.validate_base_url(value)

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix sockets unavailable")
    def test_loopback_adapter_to_actual_unix_socket(self):
        adapter = self.adapter_fixture()
        identity = {"User-Agent": "opencode/1.19.3", "x-opencode-session": "ses_fixture",
                    "x-opencode-request": "req_fixture", "x-opencode-client": "cli"}
        blocked = {"x-api-key": "candidate-secret", "Forwarded": "for=private",
                   "x-forwarded-host": "private", "x-opencode-project": "/private/project",
                   "x-opencode-directory": "/private/path", "x-opencode-parent": "private-parent",
                   "x-opencode-unlisted": "must-not-pass"}
        status, output = self.request(b'{"model":"selected"}', path="/v1/responses",
                                      headers=tuple({**identity, **blocked, "Host": "candidate.invalid"}.items()),
                                      port=adapter.server_port)
        self.assertEqual(status, 200)
        self.assertIn(b"[DONE]", output)
        received = {name.lower(): value for name, value in self.upstream.calls[0][1].items()}
        self.assertEqual({name.lower(): received[name.lower()] for name in identity},
                         {name.lower(): value for name, value in identity.items()})
        self.assertFalse({name.lower() for name in blocked} & set(received))
        self.assertNotEqual(received["host"], "candidate.invalid")
        self.assertEqual(received["authorization"], "Bearer fixture-key")
        self.assertNotIn("candidate-supplied", str(received))

    def adapter_fixture(self):
        path = str(Path(self.temp.name) / "api.sock")
        uds = gateway.UnixHTTPServer(path, gateway.GatewayHandler)
        uds.policy = self.server.policy
        uds.connection_factory = self.server.connection_factory
        adapter = http.server.ThreadingHTTPServer(("127.0.0.1", 0), loopback_adapter.Adapter)
        adapter.socket_path = path
        for server in (uds, adapter):
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        return adapter

    def test_gateway_rejects_duplicate_and_malformed_identity_before_upstream(self):
        for name in gateway.IDENTITY_HEADERS:
            cases = (((name, "one"), (name.upper(), "two")),
                     ((name, "a" * 257),), ((name, "bad\x01value"),), ((name, "nonascii-\xe9"),),
                     ((name, "folded\r\n\tvalue"),))
            for headers in cases:
                with self.subTest(name=name, headers=headers):
                    self.assertEqual(self.request(b'{"model":"selected"}', headers=headers)[0], 400)
        self.assertEqual(self.upstream.calls, [])

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix sockets unavailable")
    def test_adapter_rejects_duplicate_and_malformed_identity_before_gateway(self):
        adapter = self.adapter_fixture()
        for headers in ((("User-Agent", "first"), ("user-agent", "second")),
                        (("x-opencode-client", "x" * 257),), (("x-opencode-session", "bad\x01value"),)):
            with self.subTest(headers=headers):
                self.assertNotEqual(self.request(b'{"model":"selected"}', headers=headers,
                                                port=adapter.server_port)[0], 200)
        self.assertEqual(self.upstream.calls, [])

    def test_identity_header_exact_boundaries_and_no_synthesis(self):
        self.assertEqual(gateway.identity_headers(Message()), {})
        for name in gateway.IDENTITY_HEADERS:
            headers = Message()
            headers[name] = "~" * 256
            self.assertEqual(gateway.identity_headers(headers), {name: "~" * 256})
            for value in ("", "\t", "\x7f", "\xe9", "x" * 257):
                headers.replace_header(name, value)
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    gateway.identity_headers(headers)


if __name__ == "__main__":
    unittest.main()
