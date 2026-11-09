#!/bin/bash
cd "$(dirname "$0")"
python3 create_shortcut.py
read -n 1 -s -r -p "何かキーを押すと閉じます"
