import pytest
from fastapi.testclient import TestClient

from app import main, service


@pytest.fixture
def client(conn, fake_fetcher, monkeypatch):
    monkeypatch.setattr(main, "_conn", conn)
    monkeypatch.setattr(service, "_fetcher", fake_fetcher)
    return TestClient(main.app)


def test_api_flow(client):
    assert client.get("/").status_code == 200
    r = client.post("/api/collect", json={"platform": "coconala", "keyword": "ロゴ"})
    assert r.status_code == 200 and r.json()["saved"] == 3
    assert client.post("/api/collect", json={"platform": "x", "keyword": "a"}).status_code == 400
    assert client.post("/api/collect", json={"platform": "coconala", "keyword": " "}).status_code == 400

    assert client.get("/api/overview").json()["services"] == 3
    assert len(client.get("/api/services", params={"keyword": "ロゴ"}).json()) == 3
    assert client.get("/api/stats/prices", params={"kind": "service"}).json()["summary"]["count"] == 3
    assert client.get("/api/stats/sellers").json()[0]["seller_name"] == "デザイナーA"
    assert len(client.get("/api/stats/trends").json()) == 1

    r = client.post("/api/import", data={"kind": "job", "platform": "manual"},
                    files={"file": ("a.csv", "タイトル,予算上限\nテスト案件,10000\n".encode("cp932"), "text/csv")})
    assert r.json()["imported"] == 1

    exp = client.get("/api/export", params={"kind": "sellers"})
    assert exp.status_code == 200 and "デザイナーA" in exp.text

    assert client.post("/api/watchlist", json={"platform": "crowdworks", "keyword": "Python"}).status_code == 200
    wl = client.get("/api/watchlist").json()
    assert len(wl) == 1
    assert client.post("/api/watchlist/run").json()[0]["saved"] == 3
    client.delete(f"/api/watchlist/{wl[0]['id']}")
    assert client.get("/api/watchlist").json() == []
