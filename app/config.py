"""設定値（環境変数で上書き可能）。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("FRT_DB_PATH", BASE_DIR / "data" / "research.db"))

# 収集時の User-Agent。正直に名乗るのが基本。
USER_AGENT = os.environ.get(
    "FRT_USER_AGENT",
    "FreelanceResearchTool/0.1 (personal market research; low-frequency)",
)
# 同一ホストへのリクエスト間隔（秒）。短くしすぎないこと。
REQUEST_INTERVAL = float(os.environ.get("FRT_REQUEST_INTERVAL", "5"))
# 1回の収集で取得する最大ページ数
MAX_PAGES = int(os.environ.get("FRT_MAX_PAGES", "5"))
HTTP_TIMEOUT = float(os.environ.get("FRT_HTTP_TIMEOUT", "30"))
