"""CLI entry point: python -m frames_dashboard"""

from __future__ import annotations

import argparse
from pathlib import Path

from .server import serve

DEFAULT_ROOT = Path.home() / "RMS_data"
DEFAULT_STATIONS_CSV = Path(__file__).resolve().parents[2] / "stations.csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="frames_dashboard",
        description="Web dashboard showing the latest capture from each RMS station.",
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT,
                        help=f"RMS data directory (default: {DEFAULT_ROOT})")
    parser.add_argument("--stations-csv", type=Path, default=DEFAULT_STATIONS_CSV,
                        help="station list; falls back to directory scan if missing")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (use 0.0.0.0 to reach it from the LAN)")
    parser.add_argument("--port", type=int, default=8420)
    args = parser.parse_args()

    if not args.data_root.is_dir():
        raise SystemExit(f"data root not found: {args.data_root}")

    serve(args.data_root, args.host, args.port, args.stations_csv)


if __name__ == "__main__":
    main()
