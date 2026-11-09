"""SQLite による保存処理。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config
from .models import Job, SearchResult, Service

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT, description TEXT, category TEXT,
    payment_type TEXT, budget_min REAL, budget_max REAL,
    client_name TEXT, client_id TEXT,
    posted_at TEXT, expires_on TEXT,
    num_contracts INTEGER, hope_contracts INTEGER,
    source TEXT NOT NULL DEFAULT 'scrape',
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
    UNIQUE (platform, external_id)
);
CREATE TABLE IF NOT EXISTS job_keywords (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    UNIQUE (job_id, keyword)
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT, price REAL, rating REAL, review_count INTEGER,
    seller_name TEXT, seller_level TEXT, labels TEXT,
    source TEXT NOT NULL DEFAULT 'scrape',
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
    UNIQUE (platform, external_id)
);
CREATE TABLE IF NOT EXISTS service_keywords (
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    UNIQUE (service_id, keyword)
);
CREATE TABLE IF NOT EXISTS service_history (
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    price REAL, rating REAL, review_count INTEGER
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL, kind TEXT NOT NULL, keyword TEXT NOT NULL,
    total_count INTEGER, sample_size INTEGER,
    price_median REAL, price_mean REAL,
    collected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL, keyword TEXT NOT NULL,
    pages INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (platform, keyword)
);
CREATE INDEX IF NOT EXISTS idx_job_kw ON job_keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_service_kw ON service_keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_hist ON service_history(service_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_snap ON snapshots(keyword, platform, collected_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def upsert_job(conn: sqlite3.Connection, job: Job, keyword: str = "", source: str = "scrape",
               ts: str | None = None) -> int:
    ts = ts or now_iso()
    d = job.to_dict()
    cols = [k for k in d if k not in ("platform", "external_id")]
    conn.execute(
        f"""INSERT INTO jobs (platform, external_id, {", ".join(cols)}, source, first_seen, last_seen)
            VALUES (:platform, :external_id, {", ".join(":" + c for c in cols)}, :source, :ts, :ts)
            ON CONFLICT(platform, external_id) DO UPDATE SET
            {", ".join(f"{c}=excluded.{c}" for c in cols)}, last_seen=excluded.last_seen""",
        {**d, "source": source, "ts": ts},
    )
    job_id = conn.execute(
        "SELECT id FROM jobs WHERE platform=? AND external_id=?", (job.platform, job.external_id)
    ).fetchone()[0]
    if keyword:
        conn.execute("INSERT OR IGNORE INTO job_keywords VALUES (?, ?)", (job_id, keyword))
    return job_id


def upsert_service(conn: sqlite3.Connection, svc: Service, keyword: str = "", source: str = "scrape",
                   ts: str | None = None) -> int:
    ts = ts or now_iso()
    d = svc.to_dict()
    cols = [k for k in d if k not in ("platform", "external_id")]
    conn.execute(
        f"""INSERT INTO services (platform, external_id, {", ".join(cols)}, source, first_seen, last_seen)
            VALUES (:platform, :external_id, {", ".join(":" + c for c in cols)}, :source, :ts, :ts)
            ON CONFLICT(platform, external_id) DO UPDATE SET
            {", ".join(f"{c}=excluded.{c}" for c in cols)}, last_seen=excluded.last_seen""",
        {**d, "source": source, "ts": ts},
    )
    sid = conn.execute(
        "SELECT id FROM services WHERE platform=? AND external_id=?", (svc.platform, svc.external_id)
    ).fetchone()[0]
    if keyword:
        conn.execute("INSERT OR IGNORE INTO service_keywords VALUES (?, ?)", (sid, keyword))
    conn.execute(
        "INSERT INTO service_history VALUES (?, ?, ?, ?, ?)",
        (sid, ts, svc.price, svc.rating, svc.review_count),
    )
    return sid


def job_price(budget_min: float | None, budget_max: float | None) -> float | None:
    """案件の代表価格（予算の上下限の中央値）。"""
    vals = [v for v in (budget_min, budget_max) if v]
    return sum(vals) / len(vals) if vals else None


def save_result(conn: sqlite3.Connection, res: SearchResult, ts: str | None = None) -> dict:
    """検索結果を保存し、トレンド用スナップショットも記録する。"""
    from statistics import mean, median

    ts = ts or now_iso()
    with transaction(conn):
        if res.kind == "job":
            for j in res.jobs:
                upsert_job(conn, j, res.keyword, ts=ts)
            prices = [p for j in res.jobs if j.payment_type == "fixed"
                      and (p := job_price(j.budget_min, j.budget_max))]
            size = len(res.jobs)
        else:
            for s in res.services:
                upsert_service(conn, s, res.keyword, ts=ts)
            prices = [s.price for s in res.services if s.price]
            size = len(res.services)
        conn.execute(
            """INSERT INTO snapshots (platform, kind, keyword, total_count, sample_size,
               price_median, price_mean, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (res.platform, res.kind, res.keyword, res.total_count, size,
             median(prices) if prices else None, mean(prices) if prices else None, ts),
        )
    return {"platform": res.platform, "kind": res.kind, "keyword": res.keyword,
            "saved": size, "total_count": res.total_count, "pages_fetched": res.pages_fetched}
