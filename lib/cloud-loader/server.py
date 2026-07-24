#!/usr/bin/env python3
"""Server-side filesystem browser and PLY server for cli-tools cloud-loader."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse


CHUNK_SIZE = 1024 * 1024
DEFAULT_START_DIR = Path("/home/xinyuan/GRIP-Layout")


class CloudLoaderServer(ThreadingHTTPServer):
    allow_reuse_address = True

    index_path: Path
    viewer_name: str
    start_dir: Path
    home_dir: Path
    ply_items: list[dict[str, Any]]
    folder_groups: list[dict[str, Any]]
    ply_lock: threading.Lock
    next_ply_id: int
    next_group_id: int


class CloudLoaderHandler(BaseHTTPRequestHandler):
    server: CloudLoaderServer
    server_version = "cloud-loader/1.1"

    def do_GET(self) -> None:
        self._route(head_only=False)

    def do_HEAD(self) -> None:
        self._route(head_only=True)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/load-file":
            self._handle_load_file()
            return
        if parsed.path == "/api/load-folder":
            self._handle_load_folder()
            return
        if parsed.path == "/api/clear":
            self._handle_clear()
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

        if path == "/api/browse":
            query = parse_query(parsed.query)
            try:
                self._send_json(self._browse_payload(query.get("path", "")), head_only)
            except FileNotFoundError as error:
                self._send_json({"error": str(error)}, head_only, HTTPStatus.NOT_FOUND)
            except NotADirectoryError as error:
                self._send_json({"error": str(error)}, head_only, HTTPStatus.BAD_REQUEST)
            except PermissionError as error:
                self._send_json({"error": f"permission denied: {error.filename}"}, head_only, HTTPStatus.FORBIDDEN)
            except OSError as error:
                self._send_json({"error": f"failed to browse path: {error}"}, head_only, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if path == "/api/ply-files":
            self._send_json(self._ply_files_payload(), head_only)
            return

        if path.startswith("/models/"):
            self._send_model_file(path[len("/models/") :], head_only)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _meta_payload(self) -> dict[str, Any]:
        return {
            "name": self.server.viewer_name,
            "mode": "server-filesystem",
            "start_dir": str(self.server.start_dir),
            "home_dir": str(self.server.home_dir),
            "cwd": os.getcwd(),
        }

    def _browse_payload(self, requested_path: str) -> dict[str, Any]:
        path = resolve_browser_path(self.server.start_dir, requested_path)
        if not path.exists():
            raise FileNotFoundError(f"path does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"path is not a directory: {path}")

        entries: list[dict[str, Any]] = []
        dirs: list[dict[str, Any]] = []
        ply_files: list[dict[str, Any]] = []
        with os.scandir(path) as scandir:
            for entry in scandir:
                try:
                    is_dir = entry.is_dir(follow_symlinks=True)
                    is_file = entry.is_file(follow_symlinks=True)
                except OSError:
                    continue

                if not is_dir and not (is_file and entry.name.lower().endswith(".ply")):
                    continue

                try:
                    stat = entry.stat(follow_symlinks=True)
                except OSError:
                    stat = None

                entries.append(
                    {
                        "name": entry.name,
                        "path": str(Path(entry.path).resolve()),
                        "type": "directory" if is_dir else "ply",
                        "size": stat.st_size if stat is not None and is_file else None,
                        "mtime": stat.st_mtime if stat is not None else None,
                        "is_symlink": entry.is_symlink(),
                    }
                )

                if is_dir:
                    child_path = Path(entry.path).resolve()
                    try:
                        child_ply_count = count_direct_plys(child_path)
                    except OSError:
                        child_ply_count = 0
                    dirs.append(
                        {
                            "name": entry.name,
                            "path": str(child_path),
                            "ply_count": child_ply_count,
                            "has_ply": child_ply_count > 0,
                            "is_symlink": entry.is_symlink(),
                        }
                    )
                else:
                    target_path = Path(entry.path).resolve()
                    ply_files.append(
                        {
                            "name": entry.name,
                            "path": str(target_path),
                            "size": stat.st_size if stat is not None else target_path.stat().st_size,
                            "is_symlink": entry.is_symlink(),
                        }
                    )

        entries.sort(key=lambda item: (0 if item["type"] == "directory" else 1, natural_name_key(item["name"])))
        dirs.sort(key=lambda item: natural_name_key(item["name"]))
        ply_files.sort(key=lambda item: natural_name_key(item["name"]))
        parent = path.parent if path.parent != path else None
        return {
            "path": str(path),
            "parent": str(parent) if parent is not None else None,
            "home": str(self.server.home_dir),
            "cwd": str(self.server.start_dir),
            "ply_count": len(ply_files),
            "has_ply": len(ply_files) > 0,
            "dirs": dirs,
            "ply_files": ply_files,
            "entries": entries,
        }

    def _ply_files_payload(self) -> dict[str, Any]:
        return {
            "name": self.server.viewer_name,
            "files": self._current_ply_items(),
            "groups": self._current_folder_groups(),
        }

    def _current_ply_items(self) -> list[dict[str, Any]]:
        with self.server.ply_lock:
            return [dict(item) for item in self.server.ply_items]

    def _current_folder_groups(self) -> list[dict[str, Any]]:
        with self.server.ply_lock:
            return [
                {
                    **group,
                    "item_ids": list(group.get("item_ids", [])),
                }
                for group in self.server.folder_groups
            ]

    def _handle_load_file(self) -> None:
        try:
            payload = self._read_json_body()
            ply_path = resolve_ply_file(self.server.start_dir, payload.get("path"))
            item, created = register_ply_path(self.server, ply_path)
        except FileNotFoundError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.NOT_FOUND)
            return
        except ValueError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.BAD_REQUEST)
            return
        except OSError as error:
            self._send_json({"error": f"failed to load PLY: {error}"}, False, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(
            {
                "status": "added" if created else "existing",
                "item": item,
                "files": self._current_ply_items(),
                "groups": self._current_folder_groups(),
            },
            False,
        )

    def _handle_load_folder(self) -> None:
        try:
            payload = self._read_json_body()
            folder_path = resolve_browser_path(self.server.start_dir, payload.get("path"))
            items, group, added, existing = register_folder_plys(self.server, folder_path)
        except FileNotFoundError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.NOT_FOUND)
            return
        except NotADirectoryError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.BAD_REQUEST)
            return
        except ValueError as error:
            self._send_json({"error": str(error)}, False, HTTPStatus.BAD_REQUEST)
            return
        except OSError as error:
            self._send_json({"error": f"failed to load folder: {error}"}, False, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(
            {
                "status": "added",
                "added": added,
                "existing": existing,
                "folder": str(folder_path),
                "group": group,
                "items": items,
                "files": self._current_ply_items(),
                "groups": self._current_folder_groups(),
            },
            False,
        )

    def _handle_clear(self) -> None:
        with self.server.ply_lock:
            self.server.ply_items = []
            self.server.folder_groups = []
            self.server.next_ply_id = 1
            self.server.next_group_id = 1
        self._send_json({"status": "cleared", "files": [], "groups": []}, False)

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


def parse_query(query: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if not query:
        return result
    for part in query.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        result[unquote(key)] = unquote(value)
    return result


def resolve_browser_path(start_dir: Path, value: Any) -> Path:
    if value is None or value == "":
        return start_dir
    if not isinstance(value, str):
        raise ValueError("path must be a string")

    expanded = Path(os.path.expandvars(value)).expanduser()
    if not expanded.is_absolute():
        expanded = start_dir / expanded
    return expanded.resolve()


def resolve_ply_file(start_dir: Path, value: Any) -> Path:
    path = resolve_browser_path(start_dir, value)
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


def register_ply_path(server: CloudLoaderServer, path: Path) -> tuple[dict[str, Any], bool]:
    resolved = path.resolve()
    with server.ply_lock:
        for item in server.ply_items:
            if item["path"] == str(resolved):
                return dict(item), False

        item_id = f"ply-{server.next_ply_id}"
        server.next_ply_id += 1
        item = ply_item_payload(item_id, resolved)
        server.ply_items.append(item)
        return dict(item), True


def register_folder_plys(server: CloudLoaderServer, folder_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], int, int]:
    if not folder_path.exists():
        raise FileNotFoundError(f"folder does not exist: {folder_path}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"path is not a directory: {folder_path}")

    plys = [path for path in folder_path.iterdir() if path.is_file() and path.suffix.lower() == ".ply"]
    plys.sort(key=lambda path: natural_name_key(path.name))
    if not plys:
        raise ValueError(f"folder has no direct .ply files: {folder_path}")

    items: list[dict[str, Any]] = []
    added = 0
    existing = 0
    for path in plys:
        item, created = register_ply_path(server, path)
        items.append(item)
        if created:
            added += 1
        else:
            existing += 1

    group = register_folder_group(server, folder_path, [item["id"] for item in items])
    return items, group, added, existing


def register_folder_group(server: CloudLoaderServer, folder_path: Path, item_ids: list[str]) -> dict[str, Any]:
    resolved = folder_path.resolve()
    with server.ply_lock:
        for group in server.folder_groups:
            if group["path"] == str(resolved):
                existing_ids = list(group.get("item_ids", []))
                for item_id in item_ids:
                    if item_id not in existing_ids:
                        existing_ids.append(item_id)
                group["item_ids"] = existing_ids
                group["count"] = len(existing_ids)
                return dict(group)

        group_id = f"folder-{server.next_group_id}"
        server.next_group_id += 1
        group = {
            "id": group_id,
            "name": resolved.name or str(resolved),
            "path": str(resolved),
            "item_ids": list(item_ids),
            "count": len(item_ids),
        }
        server.folder_groups.append(group)
        return dict(group)


def count_direct_plys(folder_path: Path) -> int:
    return sum(1 for path in folder_path.iterdir() if path.is_file() and path.suffix.lower() == ".ply")


def natural_name_key(name: str) -> list[Any]:
    parts = re.split(r"(\d+)", name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a server-side PLY cloud loader.")
    parser.add_argument("--port", required=True, type=int, help="Port to bind")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--name", default="", help="Viewer name to show in the browser")
    default_start_dir = DEFAULT_START_DIR if DEFAULT_START_DIR.is_dir() else Path.cwd()
    parser.add_argument(
        "--start-dir",
        default=str(default_start_dir),
        help="Initial server-side directory to browse",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    start_dir = Path(args.start_dir).expanduser().resolve()
    if not start_dir.is_dir():
        print(f"error: start directory does not exist: {start_dir}", file=sys.stderr)
        return 2

    index_path = Path(__file__).with_name("index.html")
    if not index_path.is_file():
        print(f"error: missing viewer page: {index_path}", file=sys.stderr)
        return 2

    server = CloudLoaderServer((args.host, args.port), CloudLoaderHandler)
    server.index_path = index_path
    server.viewer_name = args.name or f"cloud-loader-{args.port}"
    server.start_dir = start_dir
    server.home_dir = Path.home().resolve()
    server.ply_items = []
    server.folder_groups = []
    server.ply_lock = threading.Lock()
    server.next_ply_id = 1
    server.next_group_id = 1

    print(f"serving cloud loader at http://{args.host}:{args.port}/", flush=True)
    print(f"browsing server files from {start_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
