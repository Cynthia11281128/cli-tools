#!/usr/bin/env python3
"""Small, restricted HTTP server for cli-tools video-viewer."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


CHUNK_SIZE = 1024 * 1024
ALLOWED_SUFFIXES = {".mp4", ".mov"}
CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


class ViewerServer(ThreadingHTTPServer):
    allow_reuse_address = True

    video_path: Path
    index_path: Path
    viewer_name: str
    content_type: str
    metadata: dict[str, Any]


class ViewerHandler(BaseHTTPRequestHandler):
    server: ViewerServer
    server_version = "video-viewer/1.0"

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

        if path == "/video":
            self._send_video(head_only)
            return

        if path == "/frame.jpg":
            self._send_frame(parse_qs(parsed.query), head_only)
            return

        if path == "/stream.mjpg":
            self._send_stream(parse_qs(parsed.query), head_only)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _meta_payload(self) -> dict[str, Any]:
        path = self.server.video_path
        stat = path.stat()
        return {
            "name": self.server.viewer_name,
            "path": str(path),
            "video": {
                "name": path.name,
                "url": "/video",
                "size": stat.st_size,
                "suffix": path.suffix.lower(),
                "type": self.server.content_type,
            },
            "opencv": self.server.metadata,
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

    def _send_video(self, head_only: bool) -> None:
        path = self.server.video_path
        try:
            size = path.stat().st_size
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        range_header = self.headers.get("Range")
        if range_header:
            byte_range = parse_range_header(range_header, size)
            if byte_range is None:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return
            start, end = byte_range
            status = HTTPStatus.PARTIAL_CONTENT
        else:
            start, end = 0, max(size - 1, 0)
            status = HTTPStatus.OK

        content_length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header("Content-Type", self.server.content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        if head_only or content_length == 0:
            return

        try:
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = handle.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except BrokenPipeError:
            return

    def _send_frame(self, query: dict[str, list[str]], head_only: bool) -> None:
        index_text = query.get("index", ["0"])[0]
        try:
            index = max(0, int(index_text))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "invalid frame index")
            return

        max_width = query_int(query, "max_width", 1280, 0, 8192)
        quality = query_int(query, "quality", 86, 1, 100)
        frame = read_frame_jpeg(self.server.video_path, index, max_width, quality)
        if frame is None:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "frame preview unavailable")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(frame)

    def _send_stream(self, query: dict[str, list[str]], head_only: bool) -> None:
        if head_only:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        start = query_int(query, "start", 0, 0, None)
        fps = query_float(query, "fps", 12.0, 0.1, 60.0)
        max_width = query_int(query, "max_width", 1280, 0, 8192)
        quality = query_int(query, "quality", 82, 1, 100)
        all_frames = query_bool(query, "all_frames", False)

        try:
            import cv2  # type: ignore[import-not-found]
        except Exception:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "OpenCV is not available")
            return

        cap = cv2.VideoCapture(str(self.server.video_path))
        try:
            if not cap.isOpened():
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "OpenCV could not open the video")
                return

            source_fps = float(cap.get(cv2.CAP_PROP_FPS))
            stride = 1 if all_frames else max(1, round(source_fps / fps)) if source_fps > fps > 0 else 1
            delay = 1.0 / fps
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            while True:
                tick = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    break

                encoded = encode_frame(frame, max_width, quality)
                if encoded is None:
                    break

                payload = encoded.tobytes()
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
                self.wfile.write(payload)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

                for _ in range(stride - 1):
                    if not cap.grab():
                        break

                elapsed = time.monotonic() - tick
                if elapsed < delay:
                    time.sleep(delay - elapsed)
        except BrokenPipeError:
            return
        finally:
            cap.release()

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


def parse_range_header(header: str, size: int) -> tuple[int, int] | None:
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not match or size < 0:
        return None

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None

    if not start_text:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            return None
        start = max(size - suffix_length, 0)
        end = max(size - 1, 0)
    else:
        start = int(start_text)
        end = int(end_text) if end_text else max(size - 1, 0)

    if start >= size or end < start:
        return None

    return start, min(end, max(size - 1, 0))


def is_supported_video(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_SUFFIXES


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def query_int(
    query: dict[str, list[str]],
    name: str,
    default: int,
    minimum: int | None,
    maximum: int | None,
) -> int:
    text = query.get(name, [str(default)])[0]
    try:
        value = int(text)
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def query_float(
    query: dict[str, list[str]],
    name: str,
    default: float,
    minimum: float | None,
    maximum: float | None,
) -> float:
    text = query.get(name, [str(default)])[0]
    try:
        value = float(text)
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def query_bool(query: dict[str, list[str]], name: str, default: bool) -> bool:
    text = query.get(name, ["1" if default else "0"])[0].strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def probe_opencv(path: Path) -> dict[str, Any]:
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on local environment
        return {
            "available": False,
            "can_open": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return {
                "available": True,
                "can_open": False,
                "error": "cv2.VideoCapture could not open the video",
            }

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc = "".join(chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)).strip()
        duration = frame_count / fps if fps > 0 else None

        return {
            "available": True,
            "can_open": True,
            "frame_count": frame_count,
            "fps": fps,
            "width": width,
            "height": height,
            "fourcc": fourcc,
            "duration_seconds": duration,
        }
    finally:
        cap.release()


def encode_frame(frame: Any, max_width: int, quality: int) -> Any | None:
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception:
        return None

    if max_width > 0 and frame.shape[1] > max_width:
        scale = max_width / frame.shape[1]
        height = max(1, round(frame.shape[0] * scale))
        frame = cv2.resize(frame, (max_width, height), interpolation=cv2.INTER_AREA)

    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None
    return encoded


def read_frame_jpeg(path: Path, index: int, max_width: int, quality: int) -> bytes | None:
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception:
        return None

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count > 0:
            index = min(index, frame_count - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok or frame is None:
            return None

        encoded = encode_frame(frame, max_width, quality)
        if encoded is None:
            return None
        return encoded.tobytes()
    finally:
        cap.release()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a video file in a browser viewer.")
    parser.add_argument("--video", required=True, help="Video file to serve")
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

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        print(f"error: video file does not exist: {video_path}", file=sys.stderr)
        return 2
    if not is_supported_video(video_path):
        print(f"error: unsupported video format: {video_path}", file=sys.stderr)
        return 2

    server = ViewerServer((args.host, args.port), ViewerHandler)
    server.video_path = video_path
    server.index_path = index_path
    server.viewer_name = args.name or video_path.name
    server.content_type = content_type_for(video_path)
    server.metadata = probe_opencv(video_path)

    print(f"serving video {video_path} at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
