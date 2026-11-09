"""デスクトップにアプリのショートカットを作成する（Windows / Mac / Linux）。

使い方: python create_shortcut.py
（Windows は「ショートカット作成.bat」、Mac は「ショートカット作成.command」をダブルクリックでも可）
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "クラウドソーシング調査"


def desktop_dir() -> Path:
    if os.name == "nt":
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
            capture_output=True, text=True,
        ).stdout.strip()
        if out:
            return Path(out)
    elif sys.platform.startswith("linux"):
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True).stdout.strip()
            if out:
                return Path(out)
        except FileNotFoundError:
            pass
    return Path.home() / "Desktop"


def python_for_launch() -> str:
    """コンソールに使う Python（Windows は py ランチャーがあればそれでもよい）。"""
    return sys.executable


def windows(desktop: Path) -> Path:
    bat = ROOT / "start.bat"
    lnk = desktop / f"{NAME}.lnk"
    q = lambda p: str(p).replace("'", "''")  # PowerShell の単一引用符エスケープ
    ps = f"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}')
$s.TargetPath = '{q(bat)}'
$s.WorkingDirectory = '{q(ROOT)}'
$s.IconLocation = '{q(ROOT / "assets" / "icon.ico")}'
$s.Description = 'CrowdWorks / Coconala research tool'
$s.Save()
"""
    subprocess.check_call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
    return lnk


def mac(desktop: Path) -> Path:
    target = desktop / f"{NAME}.command"
    target.write_text(f'#!/bin/bash\ncd "{ROOT}"\n"{python_for_launch()}" launch.py\n', encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # アイコン設定（失敗しても動作には影響しない）
    icon = ROOT / "assets" / "icon.png"
    script = (
        'use framework "AppKit"\n'
        f'set img to current application\'s NSImage\'s alloc()\'s initWithContentsOfFile:"{icon}"\n'
        f'current application\'s NSWorkspace\'s sharedWorkspace()\'s setIcon:img forFile:"{target}" options:0'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)
    return target


def linux(desktop: Path) -> Path:
    entry = f"""[Desktop Entry]
Type=Application
Name={NAME}
Comment=クラウドワークス・ココナラ調査ツール
Exec="{python_for_launch()}" "{ROOT / 'launch.py'}"
Path={ROOT}
Icon={ROOT / 'assets' / 'icon.png'}
Terminal=true
Categories=Office;
"""
    paths = []
    for d in (desktop, Path.home() / ".local/share/applications"):
        d.mkdir(parents=True, exist_ok=True)
        p = d / "crowdsourcing-research.desktop"
        p.write_text(entry, encoding="utf-8")
        p.chmod(0o755)
        paths.append(p)
    if shutil.which("gio"):  # GNOME で「起動を許可」にする
        subprocess.run(["gio", "set", str(paths[0]), "metadata::trusted", "true"], capture_output=True)
    return paths[0]


def main() -> None:
    desktop = desktop_dir()
    desktop.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path = windows(desktop)
    elif sys.platform == "darwin":
        path = mac(desktop)
    else:
        path = linux(desktop)
    print(f"ショートカットを作成しました: {path}")
    print("ダブルクリックするとアプリが起動し、ブラウザが開きます。")


if __name__ == "__main__":
    main()
