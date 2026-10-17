"""Relay loopback model HTTP to a trial-specific Unix socket."""

import argparse
import http.client
import http.server
import socket
from gateway import identity_headers


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=90)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Adapter(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_POST(self):
        connection = None
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isdigit():
                raise ValueError("One Content-Length is required")
            size = int(lengths[0])
            if not 0 < size <= 32 * 1024 * 1024:
                raise ValueError("Request is too large")
            identity = identity_headers(self.headers)
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError("Truncated request")
            connection = UnixConnection(self.server.socket_path)
            headers = {key: value for key, value in self.headers.items()
                       if key.lower() in {"content-type", "anthropic-version", "anthropic-beta"}}
            headers.update(identity)
            connection.request("POST", self.path, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            while chunk := response.read1(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (ValueError, OSError, http.client.HTTPException):
            if not self.close_connection:
                self.send_error(502, "Local inference channel failed")
            self.close_connection = True
        finally:
            if connection:
                connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="127.0.0.1:18080")
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    host, port = args.listen.rsplit(":", 1)
    if host != "127.0.0.1":
        raise ValueError("Adapter may listen on private loopback only")
    with http.server.ThreadingHTTPServer((host, int(port)), Adapter) as server:
        server.socket_path = args.socket
        server.serve_forever()


if __name__ == "__main__":
    main()
