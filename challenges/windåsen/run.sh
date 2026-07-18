#!/bin/bash
# Launch a relocatable DOSBox-X config from this repo.
#
# The tracked .dosbox configs use @ROOT@ in their host mount paths instead of a
# hardcoded absolute path (DOSBox-X's `mount` does not resolve relative host
# paths). This wrapper substitutes @ROOT@ with the repo location (this script's
# own directory), so the tree works from any checkout location.
#
# Usage:  ./run.sh <config.dosbox> [extra dosbox-x args...]
#   ./run.sh win1.01-vindaasen.dosbox      # main app (auto-launch)
#   ./run.sh win1.01-vdlev.dosbox          # fulfilment pair (auto-launch)
#   ./run.sh WIN1.01/win1.01.dosbox        # main Win 1.01 (manual start)
#   ./run.sh WIN3.0/win3.0.dosbox          # build environment
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$1"
if [ -z "$CFG" ] || [ ! -f "$ROOT/$CFG" ]; then
    echo "usage: $0 <config.dosbox> [extra dosbox-x args]" >&2
    echo "  configs: win1.01-vindaasen.dosbox  win1.01-vdlev.dosbox  WIN1.01/win1.01.dosbox  WIN3.0/win3.0.dosbox" >&2
    exit 1
fi
shift
TMP="$(mktemp --suffix=.dosbox)"
trap 'rm -f "$TMP"' EXIT
# @ROOT@ -> repo path (DOSBox-X reads the config only at startup, so removing the
# temp file on exit is safe).
sed "s|@ROOT@|$ROOT|g" "$ROOT/$CFG" > "$TMP"
dosbox-x -conf "$TMP" "$@"
