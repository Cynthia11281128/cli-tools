#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools img-compare-viewer."""

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

    index_path: Path
    viewer_name: str
    left_folder_path: Path
    right_folder_path: Path
    left_images: list[Path]
    right_images: list[Path]
    left_by_name: dict[str, Path]
    right_by_name: dict[str, Path]


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "img-compare-viewer/1.0"

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

        if path.startswith("/left/"):
            self._send_side_image("left", unquote(path[len("/left/") :]), head_only)
            return

        if path.startswith("/right/"):
            self._send_side_image("right", unquote(path[len("/right/") :]), head_only)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _send_side_image(self, side: str, image_name: str, head_only: bool) -> None:
        image_path = self._side_image_path(side, image_name)
        if image_path is None:
            self.send_error(HTTPStatus.NOT_FOUND, "image not found")
            return
        self._send_image(image_path, head_only)

    def _side_image_path(self, side: str, image_name: str) -> Path | None:
        if "/" in image_name or "\\" in image_name or image_name in {"", ".", ".."}:
            return None
        if side == "left":
            return self.server.left_by_name.get(image_name)
        return self.server.right_by_name.get(image_name)

    def _meta_payload(self) -> dict[str, Any]:
        return {
            "name": self.server.viewer_name,
            "left": folder_payload("left", self.server.left_folder_path, self.server.left_images),
            "right": folder_payload("right", self.server.right_folder_path, self.server.right_images),
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


def folder_payload(side: str, folder_path: Path, images: list[Path]) -> dict[str, Any]:
    return {
        "path": str(folder_path),
        "name": folder_path.name,
        "count": len(images),
        "images": [
            image_item(path, f"/{side}/" + quote(path.name, safe=""))
            for path in images
        ],
    }


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
    parser = argparse.ArgumentParser(description="Serve two image folders in a side-by-side browser viewer.")
    parser.add_argument("--left-folder", required=True, help="Left image folder to serve")
    parser.add_argument("--right-folder", required=True, help="Right image folder to serve")
    parser.add_argument("--port", required=True, type=int, help="Port to bind")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--name", default="", help="Viewer name to show in the browser")
    return parser.parse_args()


def prepare_folder(path_text: str, label: str) -> tuple[Path, list[Path]]:
    folder_path = Path(path_text).expanduser().resolve()
    if not folder_path.is_dir():
        print(f"error: {label} image folder does not exist: {folder_path}", file=sys.stderr)
        raise SystemExit(2)

    images = collect_folder_images(folder_path)
    if not images:
        print(f"error: {label} image folder has no supported images: {folder_path}", file=sys.stderr)
        raise SystemExit(2)

    return folder_path, images


def main() -> int:
    args = parse_args()

    index_path = Path(__file__).with_name("index.html")
    if not index_path.is_file():
        print(f"error: missing viewer page: {index_path}", file=sys.stderr)
        return 2

    left_folder_path, left_images = prepare_folder(args.left_folder, "left")
    right_folder_path, right_images = prepare_folder(args.right_folder, "right")

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.index_path = index_path
    server.viewer_name = args.name or f"{left_folder_path.name} vs {right_folder_path.name}"
    server.left_folder_path = left_folder_path
    server.right_folder_path = right_folder_path
    server.left_images = left_images
    server.right_images = right_images
    server.left_by_name = {path.name: path for path in left_images}
    server.right_by_name = {path.name: path for path in right_images}

    print(
        f"serving image folders {left_folder_path} and {right_folder_path} "
        f"at http://{args.host}:{args.port}/",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
