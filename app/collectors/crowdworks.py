"""クラウドワークス：公開の仕事検索ページから案件を取得する。

検索ページの HTML には `<div id="vue-container" data="...">` に JSON が
埋め込まれているので、それを読む。サイト側の変更で壊れる可能性がある。
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from .. import config
from ..models import Job, SearchResult
from .base import Collector

BASE_URL = "https://crowdworks.jp"
SEARCH_URL = BASE_URL + "/public/jobs/search"


def _payment(payment: dict) -> tuple[str, float | None, float | None]:
    if not payment:
        return "unknown", None, None
    if "fixed_price_payment" in payment:
        p = payment["fixed_price_payment"] or {}
        return "fixed", p.get("min_budget"), p.get("max_budget")
    if "hourly_payment" in payment:
        p = payment["hourly_payment"] or {}
        return "hourly", p.get("min_hourly_wage"), p.get("max_hourly_wage")
    if "fixed_price_writing_payment" in payment:
        p = payment["fixed_price_writing_payment"] or {}
        price = p.get("article_price")
        return "writing", price, price
    if "task_payment" in payment:
        p = payment["task_payment"] or {}
        price = p.get("task_price")
        return "task", price, price
    return "unknown", None, None


def parse_search_html(html: str) -> tuple[list[Job], dict]:
    """検索結果 HTML を解析し (案件リスト, ページ情報) を返す。"""
    soup = BeautifulSoup(html, "lxml")
    container = soup.find(id="vue-container")
    if container is None or not container.get("data"):
        raise ValueError("クラウドワークスの検索結果データが見つかりません（ページ構造が変わった可能性）")
    data = json.loads(container["data"])
    result = data.get("searchResult") or {}
    jobs: list[Job] = []
    for item in result.get("job_offers") or []:
        offer = item.get("job_offer") or {}
        if not offer.get("id"):
            continue
        ptype, bmin, bmax = _payment(item.get("payment") or {})
        entry = (item.get("entry") or {})
        entry = next(iter(entry.values()), {}) if entry else {}
        client = item.get("client") or {}
        jobs.append(
            Job(
                platform="crowdworks",
                external_id=str(offer["id"]),
                title=offer.get("title") or "",
                url=f"{BASE_URL}/public/jobs/{offer['id']}",
                description=offer.get("description_digest") or "",
                category=str(offer.get("category_id") or ""),
                payment_type=ptype,
                budget_min=bmin,
                budget_max=bmax,
                client_name=client.get("username") or "",
                client_id=str(client.get("user_id") or ""),
                posted_at=offer.get("last_released_at") or "",
                expires_on=offer.get("expired_on") or "",
                num_contracts=entry.get("num_contracts"),
                hope_contracts=entry.get("project_contract_hope_number"),
            )
        )
    return jobs, result.get("page") or {}


class CrowdWorksCollector(Collector):
    platform = "crowdworks"
    kind = "job"

    def search(self, keyword: str, pages: int = 1) -> SearchResult:
        pages = max(1, min(pages, config.MAX_PAGES))
        res = SearchResult(platform=self.platform, kind=self.kind, keyword=keyword)
        seen: set[str] = set()
        for page in range(1, pages + 1):
            html = self.fetcher.get_text(
                SEARCH_URL,
                params={
                    "search[keywords]": keyword,
                    "order": "new",
                    "hide_expired": "true",
                    "page": page,
                },
            )
            jobs, info = parse_search_html(html)
            res.pages_fetched += 1
            res.total_count = info.get("total_entries", res.total_count)
            res.total_pages = info.get("total_page", res.total_pages)
            for j in jobs:
                if j.external_id not in seen:
                    seen.add(j.external_id)
                    res.jobs.append(j)
            if not jobs or (res.total_pages and page >= res.total_pages):
                break
        return res
