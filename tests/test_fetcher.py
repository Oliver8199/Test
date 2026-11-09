import httpx
import pytest

from app.collectors.base import DisallowedByRobots, PoliteFetcher

ROBOTS = "User-agent: *\nDisallow: /private/\n"


def make(handler):
    return PoliteFetcher(user_agent="TestBot", interval=0,
                         client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_robots_respected():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        return httpx.Response(200, text="ok")
    f = make(handler)
    assert f.get_text("https://example.com/public", params={"q": "あ"}) == "ok"
    with pytest.raises(DisallowedByRobots):
        f.get_text("https://example.com/private/x")


def test_robots_unreachable_is_disallowed():
    def handler(req):
        raise httpx.ConnectError("down")
    with pytest.raises(DisallowedByRobots):
        make(handler).get_text("https://example.com/a")
