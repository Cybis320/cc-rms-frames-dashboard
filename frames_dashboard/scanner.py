"""Locate the most recent capture for each station under RMS_data."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# RMS writes captures as STATION_YYYYMMDD_HHMMSS_mmm_d.jpg
FRAME_RE = re.compile(
    r"^(?P<station>[A-Z0-9]+)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<ms>\d{3})_\w+\.jpg$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Frame:
    station: str
    path: Path
    captured: datetime

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.captured).total_seconds()


def parse_capture_time(path: Path) -> datetime | None:
    m = FRAME_RE.match(path.name)
    if not m:
        return None
    try:
        stamp = datetime.strptime(m["date"] + m["time"], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    # RMS timestamps the filename in UTC.
    return stamp.replace(microsecond=int(m["ms"]) * 1000, tzinfo=timezone.utc)


def discover_stations(data_root: Path, stations_csv: Path | None = None) -> list[str]:
    """Station IDs from stations.csv when available, else from directory names."""
    if stations_csv and stations_csv.is_file():
        with stations_csv.open(newline="") as fh:
            ids = [
                row["station_id"].strip()
                for row in csv.DictReader(fh)
                if row.get("station_id", "").strip()
            ]
        if ids:
            return ids
    def is_station_dir(p: Path) -> bool:
        try:
            return p.is_dir() and (p / "FramesFiles").is_dir()
        except OSError:  # e.g. root-owned lost+found on a mounted data disk
            return False

    return sorted(p.name for p in data_root.iterdir() if is_station_dir(p))


def _newest_frame_in(directory: Path) -> Frame | None:
    best: Frame | None = None
    for entry in directory.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".jpg":
            continue
        captured = parse_capture_time(entry)
        if captured is None:
            continue
        if best is None or captured > best.captured:
            best = Frame(entry.name.split("_")[0], entry, captured)
    return best


def latest_frame(data_root: Path, station: str) -> Frame | None:
    """Newest jpg for a station.

    FramesFiles nests year/day/hour and every level sorts chronologically by
    name, so we walk the newest branch first and stop at the first level that
    actually yields a frame. That keeps the scan to a handful of listings
    instead of walking every directory the station has ever written.
    """
    root = data_root / station / "FramesFiles"
    if not root.is_dir():
        return None

    def descend(directory: Path, depth: int) -> Frame | None:
        if depth == 0:
            return _newest_frame_in(directory)
        subdirs = sorted(
            (p for p in directory.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        for sub in subdirs:
            found = descend(sub, depth - 1)
            if found is not None:
                return found
        # Tolerate frames parked directly at this level.
        return _newest_frame_in(directory)

    return descend(root, depth=3)  # year / day / hour / *.jpg


def scan(data_root: Path, stations: list[str]) -> dict[str, Frame | None]:
    return {station: latest_frame(data_root, station) for station in stations}
