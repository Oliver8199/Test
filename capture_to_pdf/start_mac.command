#!/bin/bash
# Launcher for capture.py (macOS). Double-click to run.
SRC="$0"
[ -L "$SRC" ] && SRC="$(readlink "$SRC")"   # started from the Desktop shortcut
DIR="$(cd "$(dirname "$SRC")" && pwd)"
cd "$DIR" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/"
  read -r -p "Press Enter to close..."; exit 1
fi
if [ ! -f .setup_done ]; then
  echo "First run: installing required packages. This takes a few minutes..."
  python3 -m pip install --user -r requirements.txt && python3 -m playwright install chromium \
    && touch .setup_done || { echo "Setup failed."; read -r -p "Press Enter to close..."; exit 1; }
fi
python3 capture.py "$@"
read -r -p "Press Enter to close..."
