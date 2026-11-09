"""集計・分析ロジック。"""
from __future__ import annotations

import math
import sqlite3
from statistics import mean, median, quantiles

from .db import job_price


def _where(clauses: list[str]) -> str:
    return ("WHERE " + " AND ".join(clauses)) if clauses else ""


def list_jobs(conn: sqlite3.Connection, keyword: str = "", platform: str = "", payment_type: str = "",
              min_budget: float | None = None, q: str = "", sort: str = "new", limit: int = 200) -> list[dict]:
    clauses, params = [], []
    if keyword:
        clauses.append("j.id IN (SELECT job_id FROM job_keywords WHERE keyword = ?)")
        params.append(keyword)
    if platform:
        clauses.append("j.platform = ?"); params.append(platform)
    if payment_type:
        clauses.append("j.payment_type = ?"); params.append(payment_type)
    if min_budget is not None:
        clauses.append("COALESCE(j.budget_max, j.budget_min) >= ?"); params.append(min_budget)
    if q:
        clauses.append("(j.title LIKE ? OR j.description LIKE ?)"); params += [f"%{q}%"] * 2
    order = {
        "new": "j.posted_at DESC, j.last_seen DESC",
        "budget": "COALESCE(j.budget_max, j.budget_min) DESC",
        "competition": "COALESCE(j.num_contracts, 0) ASC",
    }.get(sort, "j.posted_at DESC")
    rows = conn.execute(
        f"SELECT j.* FROM jobs j {_where(clauses)} ORDER BY {order} LIMIT ?", (*params, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def list_services(conn: sqlite3.Connection, keyword: str = "", platform: str = "", q: str = "",
                  seller: str = "", sort: str = "reviews", limit: int = 200) -> list[dict]:
    clauses, params = [], []
    if keyword:
        clauses.append("s.id IN (SELECT service_id FROM service_keywords WHERE keyword = ?)")
        params.append(keyword)
    if platform:
        clauses.append("s.platform = ?"); params.append(platform)
    if q:
        clauses.append("s.title LIKE ?"); params.append(f"%{q}%")
    if seller:
        clauses.append("s.seller_name = ?"); params.append(seller)
    order = {
        "reviews": "COALESCE(s.review_count, 0) DESC",
        "price_asc": "s.price ASC",
        "price_desc": "s.price DESC",
        "rating": "COALESCE(s.rating, 0) DESC, COALESCE(s.review_count, 0) DESC",
        "new": "s.first_seen DESC",
    }.get(sort, "COALESCE(s.review_count, 0) DESC")
    rows = conn.execute(
        f"SELECT s.* FROM services s {_where(clauses)} ORDER BY {order} LIMIT ?", (*params, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def _histogram(values: list[float], bins: int = 12) -> list[dict]:
    """価格は裾が長いので対数スケールで区切る。"""
    vals = [v for v in values if v and v > 0]
    if not vals:
        return []
    lo, hi = math.log10(min(vals)), math.log10(max(vals))
    if hi - lo < 1e-9:
        return [{"from": min(vals), "to": max(vals), "count": len(vals)}]
    step = (hi - lo) / bins
    edges = [10 ** (lo + step * i) for i in range(bins + 1)]
    counts = [0] * bins
    for v in vals:
        idx = min(int((math.log10(v) - lo) / step), bins - 1)
        counts[idx] += 1
    return [{"from": round(edges[i]), "to": round(edges[i + 1]), "count": counts[i]} for i in range(bins)]


def _summary(values: list[float]) -> dict:
    vals = sorted(v for v in values if v is not None and v > 0)
    if not vals:
        return {"count": 0}
    out = {"count": len(vals), "min": vals[0], "max": vals[-1],
           "mean": round(mean(vals)), "median": median(vals)}
    if len(vals) >= 4:
        q1, _, q3 = quantiles(vals, n=4)
        out.update(q1=q1, q3=q3)
    return out


def price_stats(conn: sqlite3.Connection, kind: str, keyword: str = "", platform: str = "",
                payment_type: str = "fixed") -> dict:
    if kind == "job":
        rows = list_jobs(conn, keyword=keyword, platform=platform, payment_type=payment_type, limit=100000)
        values = [job_price(r["budget_min"], r["budget_max"]) for r in rows]
    else:
        rows = list_services(conn, keyword=keyword, platform=platform, limit=100000)
        values = [r["price"] for r in rows]
    values = [v for v in values if v]
    return {"summary": _summary(values), "histogram": _histogram(values)}


def trends(conn: sqlite3.Connection, keyword: str = "", platform: str = "") -> list[dict]:
    clauses, params = [], []
    if keyword:
        clauses.append("keyword = ?"); params.append(keyword)
    if platform:
        clauses.append("platform = ?"); params.append(platform)
    rows = conn.execute(
        f"SELECT * FROM snapshots {_where(clauses)} ORDER BY collected_at", params
    ).fetchall()
    return [dict(r) for r in rows]


def seller_ranking(conn: sqlite3.Connection, keyword: str = "", platform: str = "", days: int = 30,
                   limit: int = 50) -> list[dict]:
    """出品者ごとの集計。レビュー増加数は販売数の目安（概算）として使う。"""
    clauses, params = ["s.seller_name <> ''"], []
    if keyword:
        clauses.append("s.id IN (SELECT service_id FROM service_keywords WHERE keyword = ?)")
        params.append(keyword)
    if platform:
        clauses.append("s.platform = ?"); params.append(platform)
    rows = conn.execute(
        f"""
        WITH growth AS (
            SELECT h.service_id,
                   MAX(h.review_count) - MIN(h.review_count) AS review_growth
            FROM service_history h
            WHERE h.observed_at >= datetime('now', ?)
            GROUP BY h.service_id
        )
        SELECT s.platform, s.seller_name, MAX(s.seller_level) AS seller_level,
               COUNT(*) AS services,
               ROUND(AVG(s.price)) AS avg_price,
               MIN(s.price) AS min_price, MAX(s.price) AS max_price,
               SUM(COALESCE(s.review_count, 0)) AS total_reviews,
               ROUND(SUM(s.rating * s.review_count) / NULLIF(SUM(CASE WHEN s.rating IS NOT NULL
                     THEN s.review_count END), 0), 2) AS avg_rating,
               SUM(COALESCE(g.review_growth, 0)) AS review_growth,
               ROUND(SUM(COALESCE(s.review_count, 0) * COALESCE(s.price, 0))) AS est_revenue
        FROM services s LEFT JOIN growth g ON g.service_id = s.id
        {_where(clauses)}
        GROUP BY s.platform, s.seller_name
        ORDER BY total_reviews DESC
        LIMIT ?""",
        (f"-{int(days)} days", *params, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def client_ranking(conn: sqlite3.Connection, keyword: str = "", platform: str = "", limit: int = 50) -> list[dict]:
    clauses, params = ["j.client_name <> ''"], []
    if keyword:
        clauses.append("j.id IN (SELECT job_id FROM job_keywords WHERE keyword = ?)")
        params.append(keyword)
    if platform:
        clauses.append("j.platform = ?"); params.append(platform)
    rows = conn.execute(
        f"""SELECT j.platform, j.client_name, j.client_id, COUNT(*) AS jobs,
                   ROUND(AVG(COALESCE(j.budget_max, j.budget_min))) AS avg_budget,
                   MAX(j.posted_at) AS latest_post
            FROM jobs j {_where(clauses)}
            GROUP BY j.platform, j.client_name, j.client_id
            ORDER BY jobs DESC LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def keywords(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """SELECT keyword FROM job_keywords UNION SELECT keyword FROM service_keywords
           UNION SELECT keyword FROM watchlist ORDER BY 1"""
    ).fetchall()
    return [r[0] for r in rows]


def overview(conn: sqlite3.Connection) -> dict:
    one = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "jobs": one("SELECT COUNT(*) FROM jobs"),
        "services": one("SELECT COUNT(*) FROM services"),
        "sellers": one("SELECT COUNT(DISTINCT seller_name) FROM services WHERE seller_name <> ''"),
        "snapshots": one("SELECT COUNT(*) FROM snapshots"),
        "last_collected": one("SELECT MAX(collected_at) FROM snapshots"),
    }
