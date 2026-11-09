"""収集処理（Web / CLI 共通）。"""
from __future__ import annotations

import sqlite3

from .collectors import COLLECTORS
from .collectors.base import PoliteFetcher
from .db import now_iso, save_result

_fetcher: PoliteFetcher | None = None


def get_fetcher() -> PoliteFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = PoliteFetcher()
    return _fetcher


def collect(conn: sqlite3.Connection, platform: str, keyword: str, pages: int = 1,
            fetcher: PoliteFetcher | None = None) -> dict:
    if platform not in COLLECTORS:
        raise ValueError(f"未対応のプラットフォーム: {platform}")
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("キーワードを入力してください")
    collector = COLLECTORS[platform](fetcher or get_fetcher())
    res = collector.search(keyword, pages=pages)
    return save_result(conn, res)


def collect_watchlist(conn: sqlite3.Connection, fetcher: PoliteFetcher | None = None) -> list[dict]:
    results = []
    for w in conn.execute("SELECT * FROM watchlist ORDER BY id").fetchall():
        try:
            results.append(collect(conn, w["platform"], w["keyword"], w["pages"], fetcher))
        except Exception as e:  # 1件失敗しても残りは続ける
            results.append({"platform": w["platform"], "keyword": w["keyword"], "error": str(e)})
    return results


def add_watch(conn: sqlite3.Connection, platform: str, keyword: str, pages: int = 1) -> None:
    if platform not in COLLECTORS:
        raise ValueError(f"未対応のプラットフォーム: {platform}")
    conn.execute(
        "INSERT INTO watchlist (platform, keyword, pages, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(platform, keyword) DO UPDATE SET pages=excluded.pages",
        (platform, keyword.strip(), pages, now_iso()),
    )
    conn.commit()
