import asyncio


def test_source_catalog_loads_active_and_planned_sources():
    from ode.tools.source_registry import load_source_catalog

    sources = load_source_catalog()
    by_id = {source.id: source for source in sources}

    assert by_id["hackernews_topstories"].status == "active"
    assert by_id["reddit_hot_rss"].status == "active"
    assert by_id["google_trends"].status == "optional"
    assert by_id["arxiv_recent"].status == "planned"


def test_runtime_source_ids_only_include_scanner_sources():
    from ode.tools.source_registry import runtime_source_ids

    assert runtime_source_ids() == {
        "google_trends",
        "hackernews_topstories",
        "reddit_hot_rss",
    }


def test_service_lists_data_sources():
    from ode import service

    result = asyncio.run(service.list_data_sources(status="active"))

    assert result["ok"] is True
    assert {source["id"] for source in result["data"]["sources"]} == {
        "hackernews_topstories",
        "reddit_hot_rss",
    }
    assert "Opportunity Data Sources" in result["data"]["formatted"]


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
