import asyncio


def test_source_catalog_loads_active_and_planned_sources():
    from ode.tools.source_registry import load_source_catalog

    sources = load_source_catalog()
    by_id = {source.id: source for source in sources}

    assert by_id["hackernews_topstories"].status == "active"
    assert by_id["reddit_hot_rss"].status == "active"
    assert by_id["producthunt_feed"].status == "active"
    assert by_id["google_trends"].status == "optional"
    assert by_id["arxiv_recent"].status == "planned"
    assert by_id["producthunt_feed"].contexts == ["pain_listener"]


def test_runtime_source_ids_only_include_scanner_sources():
    from ode.tools.source_registry import runtime_source_ids, sources_for_context

    assert runtime_source_ids() == {
        "google_trends",
        "hackernews_topstories",
        "reddit_hot_rss",
    }
    assert {source.id for source in sources_for_context("pain_listener")} == {
        "hackernews_topstories",
        "producthunt_feed",
        "reddit_hot_rss",
    }
    assert "producthunt_feed" not in runtime_source_ids("scan_worker")


def test_service_lists_data_sources():
    from ode import service

    result = asyncio.run(service.list_data_sources(status="active"))

    assert result["ok"] is True
    assert {source["id"] for source in result["data"]["sources"]} == {
        "hackernews_topstories",
        "producthunt_feed",
        "reddit_hot_rss",
    }
    by_id = {source["id"]: source for source in result["data"]["sources"]}
    assert by_id["producthunt_feed"]["used_by_scan_workers"] is False
    assert by_id["hackernews_topstories"]["used_by_scan_workers"] is True
    assert "Opportunity Data Sources" in result["data"]["formatted"]
    assert "pain_listener" in result["data"]["formatted"]


def test_region_filter_lists_china_sources():
    from ode.tools.source_registry import list_sources

    sources = list_sources(region="china")
    source_ids = {source.id for source in sources}

    assert len(sources) >= 40
    assert "cn_36kr_newsflash" in source_ids
    assert "cn_v2ex_hot" in source_ids
    assert "cn_gov_policy" in source_ids
    assert "cn_xiaohongshu_ark_order_api" in source_ids
    assert "cn_douyin_video_search_api" in source_ids
    assert "cn_wechat_channels_assistant_manual" in source_ids
    assert "cn_kuaishou_open_platform" in source_ids
    assert "cn_taobao_open_platform" in source_ids
    assert "cn_pdd_open_platform" in source_ids
    assert all(source.region == "china" for source in sources)


def test_service_region_filter_lists_china_sources():
    from ode import service

    result = asyncio.run(service.list_data_sources(region="china"))

    assert result["ok"] is True
    assert len(result["data"]["sources"]) >= 40
    assert all(source["region"] == "china" for source in result["data"]["sources"])


def test_restricted_social_platform_sources_are_not_runtime_sources():
    from ode.tools.source_registry import get_source, runtime_source_ids

    runtime_ids = runtime_source_ids()

    douyin_search = get_source("cn_douyin_video_search_api")
    xhs_orders = get_source("cn_xiaohongshu_ark_order_api")
    channels_manual = get_source("cn_wechat_channels_assistant_manual")

    assert douyin_search is not None
    assert douyin_search.status == "planned"
    assert douyin_search.access_method == "official_api_approved_scope"
    assert xhs_orders is not None
    assert xhs_orders.layer == "revenue_signal"
    assert channels_manual is not None
    assert channels_manual.status == "manual"
    assert "cn_douyin_video_search_api" not in runtime_ids
    assert "cn_xiaohongshu_ark_order_api" not in runtime_ids


def test_mainstream_global_sources_are_registered_but_not_runtime():
    from ode.tools.source_registry import get_source, runtime_source_ids

    runtime_ids = runtime_source_ids()
    mainstream_ids = {
        "youtube_data_api_search",
        "tiktok_research_api",
        "instagram_graph_hashtag_api",
        "meta_ads_library_api",
        "x_recent_search_api",
        "producthunt_graphql",
        "apple_itunes_search_api",
        "amazon_product_advertising_api",
    }

    for source_id in mainstream_ids:
        source = get_source(source_id)
        assert source is not None
        assert source.region == "global"
        assert source.status in {"manual", "planned"}
        assert source_id not in runtime_ids


def test_active_and_optional_sources_declare_contexts_and_importable_adapters():
    from ode.tools.source_registry import list_sources, load_source_adapter

    for source in list_sources():
        if source.status not in {"active", "optional"}:
            continue

        assert source.contexts
        assert callable(load_source_adapter(source))


def test_scan_all_uses_scan_worker_context(monkeypatch):
    from ode.tools import trend_scanner
    from ode.tools.sources import google_trends, hackernews, producthunt, reddit

    def fake_google(keywords, timeframe="today 3-m", geo="", source_notes=None):
        return [{
            "source_id": "google_trends",
            "source": "google_trends",
            "title": keywords[0],
            "keyword": keywords[0],
            "strength": "强",
        }]

    def fake_hn(top_n=30, source_notes=None):
        return [{
            "source_id": "hackernews_topstories",
            "source": "hackernews",
            "title": "AI agent pain",
            "keyword": "",
            "strength": "强",
        }]

    def fake_reddit(subreddits, limit=10, source_notes=None):
        return [{
            "source_id": "reddit_hot_rss",
            "source": f"reddit/r/{subreddits[0]}",
            "title": "AI agent workflow pain",
            "keyword": "",
            "strength": "中",
        }]

    def fail_producthunt(limit=30, source_notes=None):
        raise AssertionError("scan_worker must not call Product Hunt")

    monkeypatch.setattr(google_trends, "scan", fake_google)
    monkeypatch.setattr(hackernews, "scan", fake_hn)
    monkeypatch.setattr(reddit, "scan", fake_reddit)
    monkeypatch.setattr(producthunt, "scan", fail_producthunt)

    signals = trend_scanner.scan_all(
        keywords=["AI"],
        hn_top=1,
        subreddits=["SaaS"],
    )

    assert {signal["source_id"] for signal in signals} == {
        "google_trends",
        "hackernews_topstories",
        "reddit_hot_rss",
    }


def test_pain_listener_context_dispatches_producthunt(monkeypatch):
    from ode.tools.sources import hackernews, producthunt, reddit
    from ode.tools.source_dispatch import scan_for_context

    def fake_hn(top_n=30, source_notes=None):
        return [{"source_id": "hackernews_topstories", "title": "HN"}]

    def fake_reddit(subreddits, limit=10, source_notes=None):
        return [{"source_id": "reddit_hot_rss", "title": "Reddit"}]

    def fake_producthunt(limit=30, source_notes=None):
        return [{"source_id": "producthunt_feed", "title": f"PH {limit}"}]

    monkeypatch.setattr(hackernews, "scan", fake_hn)
    monkeypatch.setattr(reddit, "scan", fake_reddit)
    monkeypatch.setattr(producthunt, "scan", fake_producthunt)

    signals = scan_for_context(
        "pain_listener",
        hn_top=1,
        subreddits=["SaaS"],
        product_hunt_limit=7,
    )

    assert [signal["source_id"] for signal in signals] == [
        "hackernews_topstories",
        "producthunt_feed",
        "reddit_hot_rss",
    ]
    assert signals[1]["title"] == "PH 7"


def test_pain_listener_context_can_disable_producthunt(monkeypatch):
    from ode.tools.sources import hackernews, producthunt, reddit
    from ode.tools.source_dispatch import scan_for_context_with_notes

    def fake_hn(top_n=30, source_notes=None):
        return [{"source_id": "hackernews_topstories", "title": "HN"}]

    def fake_reddit(subreddits, limit=10, source_notes=None):
        return [{"source_id": "reddit_hot_rss", "title": "Reddit"}]

    def fail_producthunt(limit=30, source_notes=None):
        raise AssertionError("Product Hunt should be disabled")

    monkeypatch.setattr(hackernews, "scan", fake_hn)
    monkeypatch.setattr(reddit, "scan", fake_reddit)
    monkeypatch.setattr(producthunt, "scan", fail_producthunt)

    result = scan_for_context_with_notes(
        "pain_listener",
        hn_top=1,
        subreddits=["SaaS"],
        include_product_hunt=False,
    )

    assert [signal["source_id"] for signal in result["signals"]] == [
        "hackernews_topstories",
        "reddit_hot_rss",
    ]
    assert {event["source_id"] for event in result["source_events"]} == {
        "hackernews_topstories",
        "reddit_hot_rss",
    }


def test_reddit_http_failure_records_structured_note(monkeypatch):
    from ode.tools.sources import reddit

    class FakeResponse:
        status_code = 403
        text = ""

    calls = {"count": 0}

    def fake_get(url, headers=None, timeout=10, **kwargs):
        calls["count"] += 1
        return FakeResponse()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(reddit.time, "sleep", lambda seconds: None)
    notes = []

    signals = reddit.scan(["SaaS"], limit=1, source_notes=notes)

    assert signals == []
    assert calls["count"] == 2
    assert notes[0]["source_id"] == "reddit_hot_rss"
    assert notes[0]["status"] == "failed"
    assert notes[0]["http_status"] == 403
    assert notes[0]["attempts"] == 2


def test_producthunt_malformed_xml_records_structured_note(monkeypatch):
    from ode.tools.sources import producthunt

    class FakeResponse:
        status_code = 200
        text = "<not-xml"

    def fake_get(url, headers=None, timeout=10, **kwargs):
        return FakeResponse()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    notes = []

    signals = producthunt.scan(limit=1, source_notes=notes)

    assert signals == []
    assert notes[0]["source_id"] == "producthunt_feed"
    assert notes[0]["status"] == "failed"
    assert notes[0]["reason"] == "malformed_xml"


def test_hackernews_non_list_payload_records_structured_note(monkeypatch):
    from ode.tools.sources import hackernews

    class FakeResponse:
        def json(self):
            return {"error": "rate limited"}

    def fake_get(url, timeout=10, **kwargs):
        return FakeResponse()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    notes = []

    signals = hackernews.scan(top_n=1, source_notes=notes)

    assert signals == []
    assert notes[0]["source_id"] == "hackernews_topstories"
    assert notes[0]["status"] == "failed"
    assert notes[0]["reason"] == "unexpected_topstories_payload"


def test_scanner_signals_include_source_ids(monkeypatch):
    from ode.tools import trend_scanner

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, timeout=10, **kwargs):
        if url.endswith("topstories.json"):
            return FakeResponse([1])
        return FakeResponse({
            "title": "AI agent observability launch",
            "url": "https://example.com",
            "score": 250,
            "descendants": 42,
            "time": 1_700_000_000,
        })

    monkeypatch.setattr("requests.get", fake_get)

    signals = trend_scanner.scan_hackernews(top_n=1)

    assert signals[0]["source_id"] == "hackernews_topstories"
    assert signals[0]["source"] == "hackernews"


def test_producthunt_feed_scanner_includes_source_id(monkeypatch):
    from ode.tools import trend_scanner

    class FakeResponse:
        status_code = 200
        text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>tag:www.producthunt.com,2005:Post/1</id>
            <published>2026-05-10T00:00:00-07:00</published>
            <updated>2026-05-10T00:00:00-07:00</updated>
            <link rel="alternate" type="text/html" href="https://www.producthunt.com/products/test"/>
            <title>Agent Debugger</title>
            <content type="html"><p>Debug AI agent workflow failures</p></content>
          </entry>
        </feed>"""

    def fake_get(url, timeout=10, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    signals = trend_scanner.scan_producthunt(limit=1)

    assert signals[0]["source_id"] == "producthunt_feed"
    assert signals[0]["source"] == "producthunt"
    assert signals[0]["summary"] == "Debug AI agent workflow failures"
    assert signals[0]["strength"] == "强"


def test_reddit_scanner_keeps_feed_summary(monkeypatch):
    from ode.tools import trend_scanner

    class FakeResponse:
        status_code = 200
        text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>t3_test</id>
            <published>2026-05-10T00:00:00Z</published>
            <updated>2026-05-10T00:00:00Z</updated>
            <author><name>builder</name></author>
            <link href="https://www.reddit.com/r/SaaS/comments/test/post/"/>
            <title>Need a better AI workflow</title>
            <content type="html"><p>Manually copy paste invoices every week.</p></content>
          </entry>
        </feed>"""

    def fake_get(url, headers=None, timeout=10, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    signals = trend_scanner.scan_reddit(["SaaS"], limit=1)

    assert signals[0]["source_id"] == "reddit_hot_rss"
    assert signals[0]["summary"] == "Manually copy paste invoices every week."
    assert signals[0]["author"] == "builder"
