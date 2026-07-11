#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools ply-viewer."""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
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
    ply_items: list[dict[str, Any]]
    ply_lock: threading.Lock
    next_ply_id: int
    folder_path: Path | None
    folder_items: list[dict[str, Any]]
    sequence_dir: Path | None
    index_path: Path
    viewer_name: str


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "ply-viewer/1.2"

    def do_GET(self) -> None:
        self._route(head_only=False)

    def do_HEAD(self) -> None:
        self._route(head_only=True)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/ply-add":
            self._handle_ply_add()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _route(self, head_only: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._send_file(self.server.index_path, "text/html; charset=utf-8", head_only)
            return

        if path == "/meta.json":
            self._send_json(self._meta_payload(), head_only)
            return

        if path == "/api/ply-files":
            if self.server.mode != "multi":
                self._send_json({"error": "PLY add is not supported for this viewer"}, head_only, HTTPStatus.CONFLICT)
                return
            self._send_json(self._ply_files_payload(), head_only)
            return

        if self.server.mode == "multi" and path == "/model.ply":
            assert self.server.ply_path is not None
            self._send_file(self.server.ply_path, "application/octet-stream", head_only)
            return

        if self.server.mode == "multi" and path.startswith("/models/"):
            self._send_model_file(path[len("/models/") :], head_only)
            return

        if self.server.mode == "folder" and path.startswith("/folder-models/"):
            self._send_folder_model_file(path[len("/folder-models/") :], head_only)
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
        if self.server.mode == "multi":
            assert self.server.ply_path is not None
            files = self._current_ply_items()
            first = files[0]
            return {
                "mode": "multi",
                "name": self.server.viewer_name,
                "file_name": first["name"],
                "path": first["path"],
                "size": first["size"],
                "count": len(files),
            }

        if self.server.mode == "folder":
            assert self.server.folder_path is not None
            return {
                "mode": "folder",
                "name": self.server.viewer_name,
                "path": str(self.server.folder_path),
                "count": len(self.server.folder_items),
                "files": [dict(item) for item in self.server.folder_items],
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

    def _handle_ply_add(self) -> None:
        if self.server.mode != "multi":
            self._send_json(
                {"error": "PLY add is not supported for this viewer"},
                False,
                HTTPStatus.CONFLICT,
            )
            return

        try:
            payload = self._read_json_body()
            ply_path = resolve_ply_file(payload.get("path"))
            item, created = register_ply_path(self.server, ply_path)
        except FileNotFoundError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.NOT_FOUND)
            return
        except ValueError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.BAD_REQUEST)
            return
        except OSError as error:
            self._send_json({"error": f"failed to add PLY: {error}"}, False, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(
            {
                "status": "added" if created else "existing",
                "item": item,
                "files": self._current_ply_items(),
            },
            False,
        )

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error

        if length <= 0:
            raise ValueError("missing JSON request body")
        if length > 1024 * 1024:
            raise ValueError("JSON request body is too large")

        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid JSON request body") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def _ply_files_payload(self) -> dict[str, Any]:
        return {
            "mode": "multi",
            "name": self.server.viewer_name,
            "files": self._current_ply_items(),
        }

    def _current_ply_items(self) -> list[dict[str, Any]]:
        with self.server.ply_lock:
            return [dict(item) for item in self.server.ply_items]

    def _send_model_file(self, rel_url: str, head_only: bool) -> None:
        item_id = unquote(rel_url)
        if item_id.endswith(".ply"):
            item_id = item_id[:-4]

        with self.server.ply_lock:
            item = next((candidate for candidate in self.server.ply_items if candidate["id"] == item_id), None)

        if item is None:
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        self._send_file(Path(item["path"]), "application/octet-stream", head_only)

    def _send_folder_model_file(self, rel_url: str, head_only: bool) -> None:
        file_name = unquote(rel_url)
        if "/" in file_name or "\\" in file_name or file_name in {"", ".", ".."}:
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        item = next((candidate for candidate in self.server.folder_items if candidate["name"] == file_name), None)
        if item is None:
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        self._send_file(Path(item["path"]), "application/octet-stream", head_only)

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

    def _send_json(self, payload: dict[str, Any], head_only: bool, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
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


def resolve_ply_file(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path must be a non-empty string")

    path = Path(value).expanduser().resolve()
    if path.suffix.lower() != ".ply":
        raise ValueError(f"expected a .ply file: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"PLY file does not exist: {path}")
    return path


def ply_item_payload(item_id: str, path: Path) -> dict[str, Any]:
    return {
        "id": item_id,
        "name": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "url": f"/models/{quote(item_id, safe='')}.ply",
    }


def register_ply_path(server: ViewerServer, path: Path) -> tuple[dict[str, Any], bool]:
    resolved = path.resolve()
    with server.ply_lock:
        for item in server.ply_items:
            if item["path"] == str(resolved):
                return dict(item), False

        item_id = f"ply-{server.next_ply_id}"
        server.next_ply_id += 1
        item = ply_item_payload(item_id, resolved)
        server.ply_items.append(item)
        if server.ply_path is None:
            server.ply_path = resolved
        return dict(item), True


def natural_name_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def folder_ply_item_payload(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "url": f"/folder-models/{quote(path.name, safe='')}",
    }


def collect_folder_ply_items(folder_path: Path) -> list[dict[str, Any]]:
    root = folder_path.resolve()
    ply_paths: list[Path] = []

    for path in folder_path.iterdir():
        if not path.is_file() or path.suffix.lower() != ".ply":
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        ply_paths.append(resolved)

    return [folder_ply_item_payload(path) for path in sorted(ply_paths, key=natural_name_key)]


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
    parser = argparse.ArgumentParser(description="Serve a PLY file, PLY folder, or PLY snapshot sequence in a browser viewer.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ply", help="PLY file to serve")
    mode.add_argument("--folder", help="Folder containing ordinary PLY files to browse")
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
    folder_path = None
    folder_items: list[dict[str, Any]] = []
    sequence_dir = None
    mode = "multi"
    default_name = ""

    if args.ply:
        try:
            ply_path = resolve_ply_file(args.ply)
        except (FileNotFoundError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        default_name = ply_path.name
    elif args.folder:
        mode = "folder"
        folder_path = Path(args.folder).expanduser().resolve()
        if not folder_path.is_dir():
            print(f"error: PLY folder does not exist: {folder_path}", file=sys.stderr)
            return 2
        folder_items = collect_folder_ply_items(folder_path)
        if not folder_items:
            print(f"error: folder has no .ply files: {folder_path}", file=sys.stderr)
            return 2
        default_name = folder_path.name
    else:
        mode = "sequence"
        sequence_dir = Path(args.sequence).expanduser().resolve()
        if not sequence_dir.is_dir():
            print(f"error: sequence directory does not exist: {sequence_dir}", file=sys.stderr)
            return 2
        default_name = sequence_dir.name

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.mode = mode
    server.ply_path = None
    server.ply_items = []
    server.ply_lock = threading.Lock()
    server.next_ply_id = 1
    server.folder_path = folder_path
    server.folder_items = folder_items
    server.sequence_dir = sequence_dir
    server.index_path = index_path
    server.viewer_name = args.name or default_name
    if mode == "multi":
        assert ply_path is not None
        register_ply_path(server, ply_path)

    if mode == "sequence":
        print(f"serving PLY sequence {sequence_dir} at http://{args.host}:{args.port}/", flush=True)
    elif mode == "folder":
        print(f"serving PLY folder {folder_path} at http://{args.host}:{args.port}/", flush=True)
    else:
        print(f"serving PLY viewer with {ply_path} at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
