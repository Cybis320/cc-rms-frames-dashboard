# frames_dashboard

Single-window view of the latest captured frame from every RMS station, with
click-to-full-resolution.

## Install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/Cybis320/cc-rms-frames-dashboard/master/scripts/deploy.sh | bash
```

Clones (or updates) the repo into `~/source/CC_Utils/frames_dashboard`,
installs the package into the RMS virtualenv at `~/vRMS` (or a local `.venv`
if there isn't one), and puts a **Frames Dashboard** icon on the Desktop and
in the app menu. Idempotent — re-run the same command any time to update.

Overridable via environment: `CC_DEST` (checkout location), `CC_VENV`
(virtualenv to install into), `CC_REPO_URL`.

To uninstall:

```bash
pkill -f 'frames_dashboard --port' || true
rm -f ~/.local/share/applications/frames-dashboard.desktop \
      "$(xdg-user-dir DESKTOP)/frames-dashboard.desktop"
rm -rf ~/source/CC_Utils/frames_dashboard
```

## Desktop icon

```bash
./scripts/install-desktop.sh
```

Installs a **Frames Dashboard** launcher on the Desktop and in the app menu.
Clicking it starts the server if it isn't already running, then opens the
dashboard in your browser; clicking it again just reopens the tab against the
server already running, so repeat clicks never stack up duplicate servers. The
server keeps running after the browser closes — stop it with
`pkill -f 'frames_dashboard --port'`. Its output goes to
`~/.local/state/frames-dashboard.log`.

The installer marks the entry as trusted via `gio`, which GNOME requires or the
icon appears as "Untrusted application launcher" and won't run when clicked.

## Run from a terminal

```bash
cd ~/source/CC_Utils/frames_dashboard
python3 -m frames_dashboard
```

Then open <http://localhost:8420>.

Useful flags:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Use `0.0.0.0` to reach the dashboard from another machine on the LAN |
| `--port` | `8420` | |
| `--data-root` | `~/RMS_data` | |
| `--stations-csv` | `../stations.csv` | Station order/list; falls back to scanning `~/RMS_data` if absent |

Pillow is the only dependency, and it is optional — without it the server just
serves the original JPEGs and lets the browser scale them.

## Using it

The grid shows all six stations at once. Each tile carries the station ID, the
age of its newest frame, and a status dot: green under 5 minutes, amber under
30, red beyond that (or if no frames were found at all).

Click any tile to open it full-screen. In the viewer:

- **Actual size (1:1)** — switch between fit-to-window and true 1920×1080
  pixels; drag to pan when zoomed. `f` or `space` toggles it.
- **← / →** — step to the previous/next station without going back to the grid.
- **Esc** — close.

The grid re-polls every 10 seconds and each tile refreshes itself as soon as
that station writes a new frame.

## How it works

`scanner.py` finds each station's newest capture. `FramesFiles` nests
`year/day/hour` and every level sorts chronologically by name, so it walks the
newest branch downward and stops at the first level that yields a frame —
a handful of directory listings rather than a full tree walk. Capture times come
from the filename (`STATION_YYYYMMDD_HHMMSS_mmm_d.jpg`, UTC) rather than mtime,
which survives file copies.

`server.py` serves 640px thumbnails to the grid, cached in memory and keyed by
path + mtime so a new capture invalidates its own entry. Full-resolution JPEGs
are read from disk only when you actually open a tile, and images are addressed
by station ID rather than by client-supplied path.
