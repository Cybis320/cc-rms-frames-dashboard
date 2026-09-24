#!/bin/bash
# Install the Frames Dashboard launcher onto the Desktop and into the app menu.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CC_TOOL=frames_dashboard
# shellcheck source=../cc-utils/lib.sh
. "$PROJECT_DIR/cc-utils/lib.sh"

chmod +x "$PROJECT_DIR/scripts/launch.sh"
cc_desktop_entry frames-dashboard.desktop "Frames Dashboard" \
    "$PROJECT_DIR/scripts/launch.sh" "$PROJECT_DIR/icon.png" \
    "Latest capture from every RMS station" \
    "System;Monitor;"
cc_info "Installed the Frames Dashboard launcher (Desktop + app menu)"
