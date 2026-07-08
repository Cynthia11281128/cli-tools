#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools ply-viewer."""

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
LEGACY_PRIMITIVE_RE = re.compile(r"^planarSplat_(?:(?P<iter>\d+)__|(?P<initial>initial-mesh_))colorPrim\.ply$")


class ViewerServer(ThreadingHTTPServer):
    allow_reuse_address = True

    mode: str
    ply_path: Path | None
    sequence_dir: Path | None
    index_path: Path
    viewer_name: str


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "ply-viewer/1.1"

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

        if self.server.mode == "single" and path == "/model.ply":
            assert self.server.ply_path is not None
            self._send_file(self.server.ply_path, "application/octet-stream", head_only)
            return

        if self.server.mode == "sequence":
            if path == "/sequence.json":
                self._send_json(self._sequence_payload(), head_only)
                return
            if path.startswith("/frames/"):
                self._send_sequence_file(path[len("/frames/") :], {"ply"}, head_only)
                return
            if path.startswith("/previews/"):
                self._send_sequence_file(path[len("/previews/") :], {"jpg", "jpeg", "png", "webp"}, head_only)
                return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _meta_payload(self) -> dict[str, Any]:
        if self.server.mode == "single":
            assert self.server.ply_path is not None
            return {
                "mode": "single",
                "name": self.server.viewer_name,
                "file_name": self.server.ply_path.name,
                "path": str(self.server.ply_path),
                "size": self.server.ply_path.stat().st_size,
            }

        assert self.server.sequence_dir is not None
        return {
            "mode": "sequence",
            "name": self.server.viewer_name,
            "path": str(self.server.sequence_dir),
        }

    def _sequence_payload(self) -> dict[str, Any]:
        assert self.server.sequence_dir is not None
        manifest_path = self.server.sequence_dir / "manifest.json"
        if manifest_path.is_file():
            payload = self._manifest_sequence_payload(manifest_path)
        else:
            payload = self._legacy_sequence_payload()

        payload["mode"] = "sequence"
        payload["name"] = self.server.viewer_name
        payload["path"] = str(self.server.sequence_dir)
        return payload

    def _manifest_sequence_payload(self, manifest_path: Path) -> dict[str, Any]:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        frames = []
        for frame in manifest.get("frames", []):
            primitive = frame.get("primitive_ply")
            if not primitive:
                continue
            primitive_path = safe_resolve_under(self.server.sequence_dir, primitive)
            if primitive_path is None or not primitive_path.is_file():
                continue

            normal = frame.get("normal_ply")
            preview = frame.get("view_jpg")
            item = dict(frame)
            item["primitive_url"] = frame_url(primitive)
            item["primitive_size"] = primitive_path.stat().st_size
            item["plane_count"] = item.get("plane_count") or estimate_rectangle_plane_count(primitive_path)

            if normal:
                normal_path = safe_resolve_under(self.server.sequence_dir, normal)
                if normal_path is not None and normal_path.is_file():
                    item["normal_url"] = frame_url(normal)

            if preview:
                preview_path = safe_resolve_under(self.server.sequence_dir, preview)
                if preview_path is not None and preview_path.is_file():
                    item["preview_url"] = preview_url(preview)

            frames.append(item)

        payload = dict(manifest)
        payload["frames"] = sorted(frames, key=lambda item: int(item.get("iter", 0)))
        return payload

    def _legacy_sequence_payload(self) -> dict[str, Any]:
        assert self.server.sequence_dir is not None
        frames = []
        for path in sorted(self.server.sequence_dir.glob("planarSplat_*colorPrim.ply")):
            match = LEGACY_PRIMITIVE_RE.match(path.name)
            if match is None:
                continue
            iter_token = match.group("iter")
            if match.group("initial"):
                iter_value = -1
                label = "initial"
                normal_name = "planarSplat_initial-mesh_colorNormal.ply"
                preview_name = None
            else:
                assert iter_token is not None
                iter_value = int(iter_token)
                label = str(iter_value)
                normal_name = f"planarSplat_{iter_token}__colorNormal.ply"
                preview_name = f"vis_{iter_value}_0_cuda.jpg"

            frame: dict[str, Any] = {
                "iter": iter_value,
                "label": label,
                "primitive_ply": path.name,
                "primitive_url": frame_url(path.name),
                "primitive_size": path.stat().st_size,
                "plane_count": estimate_rectangle_plane_count(path),
            }

            normal_path = self.server.sequence_dir / normal_name
            if normal_path.is_file():
                frame["normal_ply"] = normal_name
                frame["normal_url"] = frame_url(normal_name)

            if preview_name:
                preview_path = self.server.sequence_dir / preview_name
                if preview_path.is_file():
                    frame["view_jpg"] = preview_name
                    frame["preview_url"] = preview_url(preview_name)

            frames.append(frame)

        frames.sort(key=lambda item: item["iter"])
        return {
            "version": 1,
            "status": "complete",
            "source": "legacy-plane-plots",
            "snapshot_freq": None,
            "frames": frames,
        }

    def _send_sequence_file(self, rel_url: str, allowed_suffixes: set[str], head_only: bool) -> None:
        assert self.server.sequence_dir is not None
        rel_path = unquote(rel_url)
        path = safe_resolve_under(self.server.sequence_dir, rel_path)
        if path is None or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        suffix = path.suffix.lower().lstrip(".")
        if suffix not in allowed_suffixes:
            self.send_error(HTTPStatus.FORBIDDEN, "file type is not allowed")
            return

        content_type = "application/octet-stream"
        if suffix in {"jpg", "jpeg"}:
            content_type = "image/jpeg"
        elif suffix == "png":
            content_type = "image/png"
        elif suffix == "webp":
            content_type = "image/webp"
        self._send_file(path, content_type, head_only)

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


def safe_resolve_under(root: Path | None, rel_path: str) -> Path | None:
    if root is None:
        return None
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def frame_url(rel_path: str) -> str:
    return "/frames/" + quote(rel_path.replace("\\", "/"), safe="/")


def preview_url(rel_path: str) -> str:
    return "/previews/" + quote(rel_path.replace("\\", "/"), safe="/")


def estimate_rectangle_plane_count(path: Path) -> int | None:
    vertex_count = None
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                try:
                    line = raw_line.decode("ascii", errors="ignore").strip()
                except UnicodeDecodeError:
                    return None
                if line.startswith("element vertex "):
                    vertex_count = int(line.split()[-1])
                if line == "end_header":
                    break
    except OSError:
        return None
    if vertex_count is None:
        return None
    return vertex_count // 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a PLY file or PLY snapshot sequence in a browser viewer.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ply", help="PLY file to serve")
    mode.add_argument("--sequence", help="Directory containing optimization snapshots or legacy plane_plots")
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

    ply_path = None
    sequence_dir = None
    mode = "single"
    default_name = ""

    if args.ply:
        ply_path = Path(args.ply).expanduser().resolve()
        if not ply_path.is_file():
            print(f"error: PLY file does not exist: {ply_path}", file=sys.stderr)
            return 2
        if ply_path.suffix.lower() != ".ply":
            print(f"error: expected a .ply file: {ply_path}", file=sys.stderr)
            return 2
        default_name = ply_path.name
    else:
        mode = "sequence"
        sequence_dir = Path(args.sequence).expanduser().resolve()
        if not sequence_dir.is_dir():
            print(f"error: sequence directory does not exist: {sequence_dir}", file=sys.stderr)
            return 2
        default_name = sequence_dir.name

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.mode = mode
    server.ply_path = ply_path
    server.sequence_dir = sequence_dir
    server.index_path = index_path
    server.viewer_name = args.name or default_name

    if mode == "sequence":
        print(f"serving PLY sequence {sequence_dir} at http://{args.host}:{args.port}/", flush=True)
    else:
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
