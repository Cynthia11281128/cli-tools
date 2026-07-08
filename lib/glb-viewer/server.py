#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools glb-viewer."""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CHUNK_SIZE = 1024 * 1024


class ViewerServer(ThreadingHTTPServer):
    allow_reuse_address = True

    glb_path: Path
    display_path: Path
    index_path: Path
    viewer_name: str


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "glb-viewer/1.0"

    def do_GET(self) -> None:
        self._route(head_only=False)

    def do_HEAD(self) -> None:
        self._route(head_only=True)

    def _route(self, head_only: bool) -> None:
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            self._send_file(self.server.index_path, "text/html; charset=utf-8", head_only)
            return

        if path == "/model.glb":
            self._send_file(self.server.glb_path, "model/gltf-binary", head_only)
            return

        if path == "/meta.json":
            self._send_json(
                {
                    "name": self.server.viewer_name,
                    "file_name": self.server.display_path.name,
                    "path": str(self.server.display_path),
                    "size": self.server.glb_path.stat().st_size,
                },
                head_only,
            )
            return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _send_json(self, payload: dict[str, Any], head_only: bool) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str, head_only: bool) -> None:
        try:
            size = path.stat().st_size
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        if head_only:
            return

        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except BrokenPipeError:
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a single GLB file in a browser viewer.")
    parser.add_argument("--glb", required=True, help="GLB file to serve")
    parser.add_argument("--port", required=True, type=int, help="Port to bind")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--name", default="", help="Viewer name to show in the browser")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.glb).expanduser()
    display_path = input_path if input_path.is_absolute() else Path.cwd() / input_path
    if not display_path.is_file():
        print(f"error: GLB file does not exist: {display_path}", file=sys.stderr)
        return 2
    if display_path.suffix.lower() != ".glb":
        print(f"error: expected a .glb file: {display_path}", file=sys.stderr)
        return 2
    glb_path = display_path.resolve()

    index_path = Path(__file__).with_name("index.html")
    if not index_path.is_file():
        print(f"error: missing viewer page: {index_path}", file=sys.stderr)
        return 2

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.glb_path = glb_path
    server.display_path = display_path
    server.index_path = index_path
    server.viewer_name = args.name or display_path.name

    print(f"serving {display_path} at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
