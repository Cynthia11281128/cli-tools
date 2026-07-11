#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools img-viewer."""

from __future__ import annotations

import argparse
import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse


CHUNK_SIZE = 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


class ViewerServer(ThreadingHTTPServer):
    allow_reuse_address = True

    mode: str
    image_path: Path | None
    folder_path: Path | None
    images: list[Path]
    image_by_name: dict[str, Path]
    index_path: Path
    viewer_name: str


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "img-viewer/1.0"

    def do_GET(self) -> None:
        self._route(head_only=False)

    def do_HEAD(self) -> None:
        self._route(head_only=True)

    def _route(self, head_only: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._send_file(self.server.index_path, "text/html; charset=utf-8", head_only)
            return

        if path == "/meta.json":
            self._send_json(self._meta_payload(), head_only)
            return

        if self.server.mode == "single" and path == "/image":
            assert self.server.image_path is not None
            self._send_image(self.server.image_path, head_only)
            return

        if self.server.mode == "folder" and path.startswith("/images/"):
            image_name = unquote(path[len("/images/") :])
            image_path = self._folder_image_path(image_name)
            if image_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "image not found")
                return
            self._send_image(image_path, head_only)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _folder_image_path(self, image_name: str) -> Path | None:
        if "/" in image_name or "\\" in image_name or image_name in {"", ".", ".."}:
            return None
        return self.server.image_by_name.get(image_name)

    def _meta_payload(self) -> dict[str, Any]:
        if self.server.mode == "single":
            assert self.server.image_path is not None
            return {
                "mode": "single",
                "name": self.server.viewer_name,
                "path": str(self.server.image_path),
                "image": image_item(self.server.image_path, "/image"),
            }

        assert self.server.folder_path is not None
        return {
            "mode": "folder",
            "name": self.server.viewer_name,
            "path": str(self.server.folder_path),
            "count": len(self.server.images),
            "images": [
                image_item(path, "/images/" + quote(path.name, safe=""))
                for path in self.server.images
            ],
        }

    def _send_json(self, payload: dict[str, Any], head_only: bool) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_image(self, path: Path, head_only: bool) -> None:
        content_type = CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
        self._send_file(path, content_type, head_only)

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


def image_item(path: Path, url: str) -> dict[str, Any]:
    return {
        "name": path.name,
        "url": url,
        "size": path.stat().st_size,
        "type": CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"),
    }


def natural_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_SUFFIXES


def collect_folder_images(folder_path: Path) -> list[Path]:
    root = folder_path.resolve()
    images: list[Path] = []

    for path in folder_path.iterdir():
        if not path.is_file() or not is_supported_image(path):
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        images.append(resolved)

    return sorted(images, key=natural_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve an image file or image folder in a browser viewer.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", help="Image file to serve")
    mode.add_argument("--folder", help="Folder containing images to serve")
    parser.add_argument("--port", required=True, type=int, help="Port to bind")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--name", default="", help="Viewer name to show in the browser")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    index_path = Path(__file__).with_name("index.html")
    if not index_path.is_file():
        print(f"error: missing viewer page: {index_path}", file=sys.stderr)
        return 2

    mode = "single"
    image_path = None
    folder_path = None
    images: list[Path] = []
    default_name = ""

    if args.image:
        image_path = Path(args.image).expanduser().resolve()
        if not image_path.is_file():
            print(f"error: image file does not exist: {image_path}", file=sys.stderr)
            return 2
        if not is_supported_image(image_path):
            print(f"error: unsupported image format: {image_path}", file=sys.stderr)
            return 2
        default_name = image_path.name
    else:
        mode = "folder"
        folder_path = Path(args.folder).expanduser().resolve()
        if not folder_path.is_dir():
            print(f"error: image folder does not exist: {folder_path}", file=sys.stderr)
            return 2
        images = collect_folder_images(folder_path)
        if not images:
            print(f"error: folder has no supported images: {folder_path}", file=sys.stderr)
            return 2
        default_name = folder_path.name

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.mode = mode
    server.image_path = image_path
    server.folder_path = folder_path
    server.images = images
    server.image_by_name = {path.name: path for path in images}
    server.index_path = index_path
    server.viewer_name = args.name or default_name

    if mode == "folder":
        print(f"serving image folder {folder_path} at http://{args.host}:{args.port}/", flush=True)
    else:
        print(f"serving {image_path} at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
