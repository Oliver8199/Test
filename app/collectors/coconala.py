"""ココナラ：公開の検索ページから出品サービスを取得する。

サービスカード（div.c-serviceBlockItem）の HTML を読む。
サイト側の変更で壊れる可能性がある。
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import config
from ..models import SearchResult, Service
from .base import Collector

BASE_URL = "https://coconala.com"
SEARCH_URL = BASE_URL + "/search"

_num = re.compile(r"[\d,]+(?:\.\d+)?")


def _to_number(text: str | None) -> float | None:
    if not text:
        return None
    m = _num.search(text)
    return float(m.group().replace(",", "")) if m else None


def parse_search_html(html: str) -> tuple[list[Service], int | None]:
    """検索結果 HTML を解析し (サービスリスト, 総件数) を返す。"""
    soup = BeautifulSoup(html, "lxml")
    services: list[Service] = []
    for card in soup.select("div.c-serviceBlockItem"):
        link = card.select_one("a.c-serviceBlockItem_titleLink") or card.select_one('a[href*="/services/"]')
        if link is None:
            continue
        m = re.search(r"/services/(\d+)", link.get("href", ""))
        if not m:
            continue
        sid = m.group(1)
        name = card.select_one(".c-serviceBlockItemContent_name")
        price = card.select_one(".c-serviceBlockItemContentPrice_price")
        score = card.select_one(".c-serviceBlockItemContentPriceRating_score")
        count = card.select_one(".c-serviceBlockItemContentPriceRating_count")
        seller = card.select_one(".c-serviceBlockItemContentInfoUser_name")
        level_img = card.select_one(".c-serviceBlockItemContentInfoUser_level img")
        level = ""
        if level_img is not None:
            lm = re.search(r"icon_(\w+)\.svg", level_img.get("src", ""))
            level = lm.group(1) if lm else ""
        seller_name = seller.get_text(strip=True) if seller else ""
        seller_name = re.sub(r"\s*さん$", "", seller_name)
        labels = [x.get_text(strip=True) for x in card.select(".d-label") if x.get_text(strip=True)]
        rc = _to_number(count.get_text() if count else None)
        services.append(
            Service(
                platform="coconala",
                external_id=sid,
                title=name.get_text(strip=True) if name else link.get_text(strip=True),
                url=f"{BASE_URL}/services/{sid}",
                price=_to_number(price.get_text() if price else None),
                rating=_to_number(score.get_text() if score else None),
                review_count=int(rc) if rc is not None else 0,
                seller_name=seller_name,
                seller_level=level,
                labels=labels,
            )
        )
    total = None
    tm = re.search(r"([\d,]+)\s*件中", soup.get_text(" "))
    if tm:
        total = int(tm.group(1).replace(",", ""))
    return services, total


class CoconalaCollector(Collector):
    platform = "coconala"
    kind = "service"

    def search(self, keyword: str, pages: int = 1) -> SearchResult:
        pages = max(1, min(pages, config.MAX_PAGES))
        res = SearchResult(platform=self.platform, kind=self.kind, keyword=keyword)
        seen: set[str] = set()
        for page in range(1, pages + 1):
            params = {"keyword": keyword}
            if page > 1:
                params["page"] = page
            html = self.fetcher.get_text(SEARCH_URL, params=params)
            services, total = parse_search_html(html)
            res.pages_fetched += 1
            if total is not None:
                res.total_count = total
            new = [s for s in services if s.external_id not in seen]
            for s in new:
                seen.add(s.external_id)
                res.services.append(s)
            if not new:
                break
        return res
