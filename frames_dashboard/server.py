"""Tiny stdlib HTTP server exposing the latest frame from each station."""

from __future__ import annotations

import io
import json
import threading
from collections import OrderedDict
from datetime import timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .scanner import Frame, discover_stations, scan

STATIC_DIR = Path(__file__).parent / "static"
THUMB_WIDTH = 640
THUMB_QUALITY = 82
CACHE_SIZE = 24


class ThumbCache:
    """Thumbnails keyed by (path, mtime) so a new capture invalidates itself."""

    def __init__(self, maxsize: int = CACHE_SIZE) -> None:
        self._entries: OrderedDict[tuple[str, float], bytes] = OrderedDict()
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def get(self, path: Path) -> bytes:
        key = (str(path), path.stat().st_mtime)
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None:
                self._entries.move_to_end(key)
                return hit

        data = self._render(path)

        with self._lock:
            self._entries[key] = data
            self._entries.move_to_end(key)
            while len(self._entries) > self._maxsize:
                self._entries.popitem(last=False)
        return data

    @staticmethod
    def _render(path: Path) -> bytes:
        try:
            from PIL import Image
        except ImportError:
            # No Pillow: hand back the original and let the browser scale it.
            return path.read_bytes()

        with Image.open(path) as img:
            img.draft("RGB", (THUMB_WIDTH, THUMB_WIDTH))  # fast JPEG downscale
            img = img.convert("RGB")
            img.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 2), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
        return buf.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "FramesDashboard/1.0"

    def __init__(self, *args, data_root: Path, stations: list[str], cache: ThumbCache, **kw):
        self.data_root = data_root
        self.stations = stations
        self.cache = cache
        super().__init__(*args, **kw)

    # --- routing ---------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._send_static("index.html", "text/html; charset=utf-8")
            elif path == "/api/latest":
                self._send_latest()
            elif path.startswith("/thumb/"):
                self._send_image(path[len("/thumb/"):], full=False)
            elif path.startswith("/full/"):
                self._send_image(path[len("/full/"):], full=True)
            else:
                self._send_error(404, "not found")
        except BrokenPipeError:
            pass  # browser navigated away mid-transfer
        except Exception as exc:  # keep one bad frame from killing the server
            self._send_error(500, str(exc))

    # --- handlers --------------------------------------------------------

    def _frame_for(self, station: str) -> Frame | None:
        if station not in self.stations:
            return None
        return scan(self.data_root, [station])[station]

    def _send_latest(self) -> None:
        frames = scan(self.data_root, self.stations)
        payload = []
        for station in self.stations:
            frame = frames[station]
            if frame is None:
                payload.append({"station": station, "online": False})
                continue
            payload.append(
                {
                    "station": station,
                    "online": True,
                    "filename": frame.path.name,
                    "captured": frame.captured.astimezone(timezone.utc).isoformat(),
                    "age_seconds": round(frame.age_seconds, 1),
                    # Cache-buster so a fresh capture always beats the browser cache.
                    "version": frame.path.stat().st_mtime_ns,
                }
            )
        body = json.dumps({"stations": payload}).encode()
        self._respond(200, "application/json", body, cache=False)

    def _send_image(self, station: str, *, full: bool) -> None:
        frame = self._frame_for(station)
        if frame is None:
            self._send_error(404, f"no frames for {station!r}")
            return
        data = frame.path.read_bytes() if full else self.cache.get(frame.path)
        self._respond(200, "image/jpeg", data, cache=True)

    def _send_static(self, name: str, content_type: str) -> None:
        target = STATIC_DIR / name
        if not target.is_file():
            self._send_error(404, "not found")
            return
        self._respond(200, content_type, target.read_bytes(), cache=False)

    # --- plumbing --------------------------------------------------------

    def _respond(self, status: int, content_type: str, body: bytes, *, cache: bool) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Images are versioned by query string; everything else must stay fresh.
        self.send_header(
            "Cache-Control", "public, max-age=3600" if cache else "no-store"
        )
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._respond(status, "application/json", json.dumps({"error": message}).encode(), cache=False)

    def log_message(self, fmt: str, *args) -> None:
        pass  # quiet; the dashboard polls a few times a minute


def serve(data_root: Path, host: str, port: int, stations_csv: Path | None = None) -> None:
    stations = discover_stations(data_root, stations_csv)
    if not stations:
        raise SystemExit(f"no stations found under {data_root}")

    handler = partial(
        DashboardHandler,
        data_root=data_root,
        stations=stations,
        cache=ThumbCache(),
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    shown = host if host not in ("0.0.0.0", "") else "localhost"
    print(f"Frames dashboard: http://{shown}:{port}")
    print(f"Watching {len(stations)} stations: {', '.join(stations)}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
