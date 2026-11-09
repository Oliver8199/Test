from app.collectors import coconala, crowdworks


def test_crowdworks_parse(fixture_html):
    jobs, page = crowdworks.parse_search_html(fixture_html("crowdworks_search.html"))
    assert page["total_entries"] == 3
    assert [j.external_id for j in jobs] == ["111", "222", "333"]
    fixed, hourly, writing = jobs
    assert (fixed.payment_type, fixed.budget_min, fixed.budget_max) == ("fixed", 50000, 100000)
    assert fixed.client_name == "株式会社サンプル"
    assert fixed.url == "https://crowdworks.jp/public/jobs/111"
    assert (hourly.payment_type, hourly.num_contracts, hourly.hope_contracts) == ("hourly", 2, 3)
    assert (writing.payment_type, writing.budget_min) == ("writing", 3000)
    assert writing.num_contracts is None


def test_crowdworks_broken_page():
    import pytest
    with pytest.raises(ValueError):
        crowdworks.parse_search_html("<html></html>")


def test_coconala_parse(fixture_html):
    services, total = coconala.parse_search_html(fixture_html("coconala_search.html"))
    assert total == 3
    a, b, c = services
    assert (a.external_id, a.title, a.price, a.rating, a.review_count) == ("1001", "ロゴを作成します", 5000, 4.9, 1234)
    assert a.seller_name == "デザイナーA" and a.seller_level == "5"
    assert a.labels == ["見積り必須"]
    assert a.url == "https://coconala.com/services/1001"
    assert (c.rating, c.review_count, c.seller_level) == (None, 0, "1")
