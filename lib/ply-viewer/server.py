#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools ply-viewer."""

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

    ply_path: Path
    index_path: Path


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "ply-viewer/1.0"

    def do_GET(self) -> None:
        self._route(head_only=False)

    def do_HEAD(self) -> None:
        self._route(head_only=True)

    def _route(self, head_only: bool) -> None:
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            self._send_file(self.server.index_path, "text/html; charset=utf-8", head_only)
            return

        if path == "/model.ply":
            self._send_file(self.server.ply_path, "application/octet-stream", head_only)
            return

        if path == "/meta.json":
            self._send_json(
                {
                    "name": self.server.ply_path.name,
                    "path": str(self.server.ply_path),
                    "size": self.server.ply_path.stat().st_size,
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
    parser = argparse.ArgumentParser(description="Serve a single PLY file in a browser viewer.")
    parser.add_argument("--ply", required=True, help="PLY file to serve")
    parser.add_argument("--port", required=True, type=int, help="Port to bind")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    ply_path = Path(args.ply).expanduser().resolve()
    if not ply_path.is_file():
        print(f"error: PLY file does not exist: {ply_path}", file=sys.stderr)
        return 2
    if ply_path.suffix.lower() != ".ply":
        print(f"error: expected a .ply file: {ply_path}", file=sys.stderr)
        return 2

    index_path = Path(__file__).with_name("index.html")
    if not index_path.is_file():
        print(f"error: missing viewer page: {index_path}", file=sys.stderr)
        return 2

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.ply_path = ply_path
    server.index_path = index_path

    print(f"serving {ply_path} at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
