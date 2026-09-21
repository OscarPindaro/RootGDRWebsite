"""Ephemeral HTTP server for component tests.

Serves rendered pages, the repository's real static assets and configurable
fake API endpoints on a dynamically allocated port. The server never writes
to the repository and must always be closed by the caller (the fixture
teardown does it unconditionally).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field


class JsonRoute(BaseModel):
    method: str
    path: str
    status: int = 200
    body: dict | list = Field(default_factory=dict)


class ComponentServer:
    """Serve rendered pages, real static assets and fake API endpoints."""

    def __init__(self, static_dir: Path, components_dir: Path) -> None:
        self._static_dir = static_dir
        self._components_dir = components_dir
        self._pages: dict[str, str] = {}
        self._routes: list[JsonRoute] = []
        self._requests: list[tuple[str, str]] = []
        self._server: ThreadingHTTPServer | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @property
    def requests(self) -> list[tuple[str, str]]:
        """(method, path) of every fake-API request the page made."""
        return list(self._requests)

    def mount_page(self, path: str, html: str) -> None:
        self._pages[path] = html

    def mount_page(self, path: str, html: str) -> None:
        self._pages[path] = html

    def set_routes(self, routes: list[JsonRoute]) -> None:
        self._routes = list(routes)

    def start(self) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), self._make_handler())
        self._server = server
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        return self.base_url

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def close(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None

    def __enter__(self) -> "ComponentServer":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # silence stderr
                pass

            def _send(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle(self, method: str) -> None:
                path = urlsplit(self.path).path
                server._requests.append((method, path))
                for route in server._routes:
                    if route.method == method and route.path == path:
                        payload = json.dumps(route.body).encode()
                        self._send(route.status, payload, "application/json")
                        return
                if method == "GET":
                    if path in server._pages:
                        self._send(200, server._pages[path].encode(), "text/html")
                        return
                    for prefix, directory in (
                        ("/static/components/", server._components_dir),
                        ("/static/", server._static_dir),
                    ):
                        if path.startswith(prefix):
                            file = directory / path.removeprefix(prefix)
                            if file.is_file():
                                self._send(200, file.read_bytes(), _content_type(file))
                                return
                self._send(404, b"not found", "text/plain")

            def do_GET(self) -> None:
                self._handle("GET")

            def do_POST(self) -> None:
                self._handle("POST")

            def do_PATCH(self) -> None:
                self._handle("PATCH")

            def do_PUT(self) -> None:
                self._handle("PUT")

            def do_DELETE(self) -> None:
                self._handle("DELETE")

        return Handler


_TYPES = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff2": "font/woff2",
}


def _content_type(path: Path) -> str:
    return _TYPES.get(path.suffix, "application/octet-stream")
