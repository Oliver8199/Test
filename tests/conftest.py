import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_html():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


class FakeFetcher:
    """ネットワークを使わず固定 HTML を返す。"""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.calls = []

    def get_text(self, url, params=None):
        self.calls.append((url, params))
        for key, html in self.pages.items():
            if key in url:
                return html
        raise AssertionError(f"unexpected url {url}")


@pytest.fixture
def fake_fetcher(fixture_html):
    return FakeFetcher({
        "crowdworks.jp": fixture_html("crowdworks_search.html"),
        "coconala.com": fixture_html("coconala_search.html"),
    })


@pytest.fixture
def conn(tmp_path):
    from app import db
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()
