"""CSV の取り込み・書き出し（手動で集めたデータ用）。"""
from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
from dataclasses import fields

from .db import transaction, upsert_job, upsert_service
from .models import Job, Service

# 日本語ヘッダーでも取り込めるようにする
ALIASES = {
    "プラットフォーム": "platform", "ID": "external_id", "id": "external_id",
    "タイトル": "title", "URL": "url", "説明": "description", "カテゴリ": "category",
    "報酬形式": "payment_type", "予算下限": "budget_min", "予算上限": "budget_max",
    "発注者": "client_name", "掲載日": "posted_at", "締切": "expires_on",
    "価格": "price", "評価": "rating", "レビュー数": "review_count",
    "出品者": "seller_name", "ランク": "seller_level", "ラベル": "labels",
    "キーワード": "keyword",
}

NUMERIC = {"budget_min", "budget_max", "price", "rating"}
INTEGER = {"review_count", "num_contracts", "hope_contracts"}


def _clean(key: str, value: str):
    value = (value or "").strip()
    if key in NUMERIC or key in INTEGER:
        value = value.replace(",", "").replace("円", "").replace("¥", "")
        if not value:
            return None
        try:
            return int(float(value)) if key in INTEGER else float(value)
        except ValueError:
            return None
    return value


def import_csv(conn: sqlite3.Connection, text: str, kind: str, default_platform: str = "manual",
               default_keyword: str = "") -> dict:
    model = Job if kind == "job" else Service
    allowed = {f.name for f in fields(model)}
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    imported, skipped, errors = 0, 0, []
    with transaction(conn):
        for lineno, raw in enumerate(reader, start=2):
            row = {ALIASES.get(k.strip(), k.strip()): v for k, v in raw.items() if k}
            kw = (row.pop("keyword", "") or default_keyword).strip()
            data = {k: _clean(k, v) for k, v in row.items() if k in allowed}
            data["platform"] = data.get("platform") or default_platform
            if not data.get("title"):
                skipped += 1
                errors.append(f"{lineno}行目: タイトルがありません")
                continue
            data["external_id"] = data.get("external_id") or "manual-" + hashlib.sha1(
                (data["title"] + str(data.get("url") or "")).encode()).hexdigest()[:12]
            if kind == "service":
                labels = data.get("labels") or ""
                data["labels"] = [x for x in str(labels).split(",") if x] if labels else []
                upsert_service(conn, Service(**data), kw, source="import")
            else:
                upsert_job(conn, Job(**data), kw, source="import")
            imported += 1
    return {"imported": imported, "skipped": skipped, "errors": errors[:20]}


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return "﻿" + buf.getvalue()  # Excel で文字化けしないよう BOM 付き
