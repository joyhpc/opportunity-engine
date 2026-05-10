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
