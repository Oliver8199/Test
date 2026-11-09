"""アプリをワンクリックで起動するためのランチャー（Windows / Mac / Linux 共通）。

初回は .venv を作って必要なライブラリを自動インストールします。
起動後、ブラウザが自動で開きます。このウィンドウを閉じるとアプリも終了します。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
DEFAULT_PORT = 8000


def in_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def ensure_venv() -> None:
    """専用の仮想環境を用意し、その Python で自分自身を起動し直す。"""
    if in_venv():
        return
    if not VENV_PY.exists():
        print("初回セットアップ中です（1〜2分かかります）…")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])
        (VENV / ".installed").write_text((ROOT / "requirements.txt").read_text())
    elif (VENV / ".installed").exists() is False or \
            (VENV / ".installed").read_text() != (ROOT / "requirements.txt").read_text():
        print("ライブラリを更新しています…")
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])
        (VENV / ".installed").write_text((ROOT / "requirements.txt").read_text())
    raise SystemExit(subprocess.call([str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]]))


def app_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/overview", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> None:
    ensure_venv()
    os.chdir(ROOT)
    port = DEFAULT_PORT
    if app_running(port):
        print("すでに起動しています。ブラウザを開きます。")
        webbrowser.open(f"http://127.0.0.1:{port}/")
        time.sleep(2)
        return
    while not port_free(port):
        port += 1
    url = f"http://127.0.0.1:{port}/"

    def open_browser() -> None:
        for _ in range(60):
            if app_running(port):
                webbrowser.open(url)
                return
            time.sleep(0.5)

    threading.Thread(target=open_browser, daemon=True).start()
    print(f"クラウドソーシング調査ツールを起動しました: {url}")
    print("終了するときはこのウィンドウを閉じてください。")
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
