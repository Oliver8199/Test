"""プラットフォーム共通のデータモデル。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Job:
    """案件（発注者が募集している仕事）。"""
    platform: str
    external_id: str
    title: str
    url: str = ""
    description: str = ""
    category: str = ""
    payment_type: str = ""          # fixed / hourly / writing / unknown
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    client_name: str = ""
    client_id: str = ""
    posted_at: str = ""
    expires_on: str = ""
    num_contracts: Optional[int] = None
    hope_contracts: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Service:
    """出品サービス（受注者が出品しているスキル商品）。"""
    platform: str
    external_id: str
    title: str
    url: str = ""
    price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    seller_name: str = ""
    seller_level: str = ""
    labels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["labels"] = ",".join(self.labels)
        return d


@dataclass
class SearchResult:
    """1回の検索（複数ページ）の結果。"""
    platform: str
    kind: str                       # "job" or "service"
    keyword: str
    total_count: Optional[int] = None
    jobs: list[Job] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    pages_fetched: int = 0
    total_pages: Optional[int] = None
