from app import analysis
from app.importer import import_csv, to_csv
from app.service import add_watch, collect, collect_watchlist


def test_collect_and_analyze(conn, fake_fetcher):
    r1 = collect(conn, "crowdworks", "Python", fetcher=fake_fetcher)
    r2 = collect(conn, "coconala", "ロゴ", fetcher=fake_fetcher)
    assert r1["saved"] == 3 and r1["total_count"] == 3
    assert r2["saved"] == 3
    # パラメータにキーワードが渡っている
    assert fake_fetcher.calls[0][1]["search[keywords]"] == "Python"

    jobs = analysis.list_jobs(conn, keyword="Python")
    assert len(jobs) == 3
    assert [j["external_id"] for j in analysis.list_jobs(conn, sort="budget")][0] == "111"
    assert len(analysis.list_jobs(conn, payment_type="hourly")) == 1

    stats = analysis.price_stats(conn, "service", keyword="ロゴ")
    assert stats["summary"]["count"] == 3 and stats["summary"]["median"] == 5000
    assert sum(h["count"] for h in stats["histogram"]) == 3
    job_stats = analysis.price_stats(conn, "job", payment_type="fixed")
    assert job_stats["summary"]["median"] == 75000

    sellers = analysis.seller_ranking(conn, keyword="ロゴ")
    assert sellers[0]["seller_name"] == "デザイナーA"
    assert sellers[0]["services"] == 2 and sellers[0]["total_reviews"] == 1244

    clients = analysis.client_ranking(conn)
    assert clients[0]["client_name"] == "株式会社サンプル" and clients[0]["jobs"] == 2

    trend = analysis.trends(conn, keyword="ロゴ")
    assert len(trend) == 1 and trend[0]["total_count"] == 3
    assert set(analysis.keywords(conn)) == {"Python", "ロゴ"}


def test_recollect_updates_without_duplicates(conn, fake_fetcher):
    collect(conn, "coconala", "ロゴ", fetcher=fake_fetcher)
    collect(conn, "coconala", "ロゴ", fetcher=fake_fetcher)
    assert conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM service_history").fetchone()[0] == 6
    assert len(analysis.trends(conn)) == 2


def test_review_growth(conn, fake_fetcher):
    from app.db import upsert_service
    from app.models import Service
    collect(conn, "coconala", "ロゴ", fetcher=fake_fetcher)
    upsert_service(conn, Service(platform="coconala", external_id="1001", title="ロゴを作成します",
                                 price=5000, rating=4.9, review_count=1250, seller_name="デザイナーA"), "ロゴ")
    conn.commit()
    top = analysis.seller_ranking(conn, keyword="ロゴ")[0]
    assert top["review_growth"] == 16


def test_watchlist(conn, fake_fetcher):
    add_watch(conn, "crowdworks", "Python")
    add_watch(conn, "coconala", "ロゴ", pages=2)
    add_watch(conn, "coconala", "ロゴ", pages=1)  # 重複は上書き
    res = collect_watchlist(conn, fetcher=fake_fetcher)
    assert [r["saved"] for r in res] == [3, 3]


def test_import_csv_japanese_headers(conn):
    text = "﻿タイトル,価格,評価,レビュー数,出品者,URL\n動画編集します,\"8,000円\",4.8,12,編集C,https://example.com/1\n,100,,,,\n"
    r = import_csv(conn, text, "service", "lancers", "動画")
    assert r["imported"] == 1 and r["skipped"] == 1
    rows = analysis.list_services(conn, keyword="動画")
    assert rows[0]["price"] == 8000 and rows[0]["platform"] == "lancers" and rows[0]["source"] == "import"
    # 同じ行を再取り込みしても重複しない
    import_csv(conn, text, "service", "lancers", "動画")
    assert len(analysis.list_services(conn)) == 1
    assert to_csv(rows).startswith("﻿id,")


def test_import_jobs(conn):
    text = "title,payment_type,budget_min,budget_max,client_name\nLP制作,fixed,30000,50000,A社\n"
    assert import_csv(conn, text, "job")["imported"] == 1
    assert analysis.price_stats(conn, "job")["summary"]["median"] == 40000
