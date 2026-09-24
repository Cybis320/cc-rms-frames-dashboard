#!/bin/bash
# Open the frames dashboard, starting the server first if it isn't already up.
# Safe to run repeatedly: a second click reuses the running server.

set -euo pipefail

PORT="${FRAMES_DASHBOARD_PORT:-8420}"
URL="http://localhost:${PORT}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/frames-dashboard.log"
MATCH="frames_dashboard --port ${PORT}"

is_up() {
    # Any HTTP answer means something is already serving this port.
    curl -sf --max-time 2 -o /dev/null "${URL}/api/latest" 2>/dev/null
}

notify() {
    command -v notify-send >/dev/null && notify-send "Frames Dashboard" "$1" || echo "$1" >&2
}

# A server started before an update (the hourly cc-utils updater) keeps running
# the old code: restart it once the checkout has moved past the commit it
# started on.
REV_FILE="${LOG%.log}.rev"
HEAD_REV="$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || true)"
if [ -n "$HEAD_REV" ] && is_up && [ "$(cat "$REV_FILE" 2>/dev/null || true)" != "$HEAD_REV" ]; then
    pkill -f "$MATCH" 2>/dev/null || true
    for _ in $(seq 20); do is_up || break; sleep 0.2; done
fi

# Prefer the interpreter deploy.sh installed into (it has Pillow for fast
# thumbnails); plain python3 still works, just serves full-size images.
PYTHON="${FRAMES_DASHBOARD_PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in "$PROJECT_DIR/.venv/bin/python" "$HOME/vRMS/bin/python"; do
        if [ -x "$cand" ]; then
            PYTHON="$cand"
            break
        fi
    done
fi
PYTHON="${PYTHON:-python3}"

if ! is_up; then
    mkdir -p "$(dirname "$LOG")"
    cd "$PROJECT_DIR"
    nohup "$PYTHON" -m frames_dashboard --port "$PORT" >>"$LOG" 2>&1 &
    disown
    printf '%s\n' "$HEAD_REV" >"$REV_FILE"

    # Give it a moment to bind before pointing a browser at it.
    for _ in $(seq 30); do
        is_up && break
        sleep 0.2
    done

    if ! is_up; then
        notify "Server failed to start — see ${LOG}"
        exit 1
    fi
fi

xdg-open "$URL" >/dev/null 2>&1
