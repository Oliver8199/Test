"""行儀のよい HTTP 取得（robots.txt 遵守・リクエスト間隔の確保）。"""
from __future__ import annotations

import threading
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .. import config


class FetchError(RuntimeError):
    pass


class DisallowedByRobots(FetchError):
    pass


class PoliteFetcher:
    """ホストごとに robots.txt を確認し、最低間隔を空けて GET する。"""

    def __init__(
        self,
        user_agent: str | None = None,
        interval: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_agent = user_agent or config.USER_AGENT
        self.interval = config.REQUEST_INTERVAL if interval is None else interval
        self.client = client or httpx.Client(
            headers={"User-Agent": self.user_agent, "Accept-Language": "ja"},
            timeout=config.HTTP_TIMEOUT,
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

    # --- robots.txt -------------------------------------------------------
    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = RobotFileParser()
            try:
                self._wait(parts.netloc)
                resp = self.client.get(origin + "/robots.txt")
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    rp.disallow_all = True
                else:
                    rp.allow_all = True
            except httpx.HTTPError:
                # robots.txt が取れない場合は安全側（取得しない）に倒す
                rp.disallow_all = True
            self._robots[origin] = rp
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.user_agent, url)

    # --- rate limit -------------------------------------------------------
    def _wait(self, host: str) -> None:
        with self._lock:
            last = self._last_request.get(host)
            now = time.monotonic()
            if last is not None and now - last < self.interval:
                time.sleep(self.interval - (now - last))
            self._last_request[host] = time.monotonic()

    # --- public -----------------------------------------------------------
    def get_text(self, url: str, params: dict | None = None) -> str:
        full = str(httpx.URL(url, params=params)) if params else url
        if not self.allowed(full):
            raise DisallowedByRobots(f"robots.txt により取得が許可されていません: {full}")
        self._wait(urlsplit(full).netloc)
        try:
            resp = self.client.get(full)
        except httpx.HTTPError as e:
            raise FetchError(f"取得に失敗しました: {full} ({e})") from e
        if resp.status_code == 429:
            raise FetchError("アクセス過多(429)と判定されました。時間をおいて再実行してください。")
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code}: {full}")
        return resp.text


class Collector:
    """各プラットフォームのコレクタの基底クラス。"""

    platform: str = ""
    kind: str = ""

    def __init__(self, fetcher: PoliteFetcher | None = None) -> None:
        self.fetcher = fetcher or PoliteFetcher()

    def search(self, keyword: str, pages: int = 1):  # pragma: no cover - interface
        raise NotImplementedError
