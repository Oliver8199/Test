#!/bin/bash
# Creates a "Capture to PDF" shortcut on the Desktop (macOS)
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/start_mac.command" "$DIR/create_shortcut_mac.command"
ln -sf "$DIR/start_mac.command" "$HOME/Desktop/Capture to PDF.command"
echo "Created \"Capture to PDF\" on your Desktop."
read -r -p "Press Enter to close..."
