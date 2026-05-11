"""Tests for ode.service — the service layer."""

import asyncio
import os
import pytest


@pytest.fixture(autouse=True)
def isolated_test_root(tmp_path):
    """Use pytest tmp_path for proper test isolation."""
    os.environ["ODE_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("ODE_ROOT", None)


class TestServiceCreate:
    def test_create_opportunity(self):
        from ode.service import create_opportunity

        result = asyncio.run(create_opportunity(
            name="Test Opp",
            domain="devtools",
            keywords=["ai", "coding"],
        ))
        assert result["ok"] is True
        assert result["data"]["name"] == "Test Opp"
        assert result["data"]["domain"] == "devtools"
        assert result["data"]["keywords"] == ["ai", "coding"]
        assert "id" in result["data"]
        assert "path" in result["data"]

    def test_create_with_custom_id(self):
        from ode.service import create_opportunity

        result = asyncio.run(create_opportunity(
            name="Custom",
            custom_id="my-id",
        ))
        assert result["ok"] is True
        assert result["data"]["id"] == "my-id"


class TestServiceList:
    def test_list_empty(self):
        from ode.service import list_opportunities

        result = asyncio.run(list_opportunities())
        assert result["ok"] is True
        assert result["data"]["opportunities"] == []

    def test_list_after_create(self):
        from ode.service import create_opportunity, list_opportunities

        asyncio.run(create_opportunity(name="A"))
        asyncio.run(create_opportunity(name="B"))
        result = asyncio.run(list_opportunities())
        assert result["ok"] is True
        assert len(result["data"]["opportunities"]) == 2


class TestServiceShow:
    def test_show_not_found(self):
        from ode.service import show_opportunity

        result = asyncio.run(show_opportunity("nonexistent"))
        assert result["ok"] is False
        assert "not found" in result["message"].lower()

    def test_show_existing(self):
        from ode.service import create_opportunity, show_opportunity

        create_result = asyncio.run(create_opportunity(name="ShowMe", domain="health"))
        opp_id = create_result["data"]["id"]

        result = asyncio.run(show_opportunity(opp_id))
        assert result["ok"] is True
        assert result["data"]["name"] == "ShowMe"
        assert result["data"]["domain"] == "health"
        assert result["data"]["stage"] == "SENSE"


class TestServiceStatus:
    def test_status_empty(self):
        from ode.service import get_status

        result = asyncio.run(get_status())
        assert result["ok"] is True
        assert result["data"]["total"] == 0
        assert result["data"]["active_count"] == 0

    def test_status_with_opps(self):
        from ode.service import create_opportunity, get_status

        asyncio.run(create_opportunity(name="StatusTest"))
        result = asyncio.run(get_status())
        assert result["data"]["total"] == 1
        assert result["data"]["active_count"] == 1


class TestServicePortfolio:
    def test_portfolio_empty(self):
        from ode.service import get_portfolio

        result = asyncio.run(get_portfolio())
        assert result["ok"] is True
        assert "No opportunities" in result["data"]["formatted"]

    def test_portfolio_with_data(self):
        from ode.service import create_opportunity, get_portfolio

        asyncio.run(create_opportunity(name="PortfolioTest"))
        result = asyncio.run(get_portfolio())
        assert result["ok"] is True
        assert len(result["data"]["summaries"]) == 1


class TestServiceCompare:
    def test_compare_no_match(self):
        from ode.service import compare_opportunities

        result = asyncio.run(compare_opportunities(["nonexistent"]))
        assert result["ok"] is True
        assert "No matching" in result["data"]["formatted"]


class TestServiceExplore:
    def test_explore_returns_result(self):
        """Test explore_signals returns proper structure (no network)."""
        from ode.service import explore_signals
        from unittest.mock import patch

        # Mock the fetch to avoid network calls
        with patch("ode.tools.trend_scanner.scan_all", return_value=[]):
            result = asyncio.run(explore_signals(hn_top=1))
            assert result["ok"] is True
            assert "result" in result["data"]
            assert "formatted" in result["data"]


class TestServicePainListener:
    def test_listen_pains_returns_ranked_report(self):
        from ode.service import listen_pains
        from unittest.mock import patch

        fake_signals = [
            {
                "source_id": "reddit_hot_rss",
                "source": "reddit/r/SaaS",
                "title": "Looking for an AI tool to stop manually reconciling invoices, would pay for it",
                "url": "https://example.com/reddit",
            },
            {
                "source_id": "producthunt_feed",
                "source": "producthunt",
                "title": "InvoicePilot",
                "summary": "AI workflow automation for invoice operations",
                "url": "https://example.com/ph",
                "rank": 3,
            },
        ]

        with patch("ode.heuristics.pain_listener.fetch_pain_sources", return_value=fake_signals):
            result = asyncio.run(listen_pains(hn_top=1, min_grade="E"))

        assert result["ok"] is True
        assert result["data"]["result"]["kept_signals"] >= 1
        assert "Pain Listener Report" in result["data"]["formatted"]


class TestServiceInsights:
    def test_insights_not_found(self):
        from ode.service import get_insights

        result = asyncio.run(get_insights("nonexistent"))
        assert result["ok"] is False
        assert "not found" in result["message"].lower()

    def test_insights_basic(self):
        from ode.service import create_opportunity, get_insights

        create_result = asyncio.run(create_opportunity(name="InsightTest", domain="health"))
        opp_id = create_result["data"]["id"]

        result = asyncio.run(get_insights(opp_id))
        assert result["ok"] is True
        assert "synthesis" in result["data"]
        assert "quick_assess" in result["data"]
        assert "reframe" in result["data"]


class TestServiceEvaluate:
    def test_eval_not_found(self):
        from ode.service import evaluate

        result = asyncio.run(evaluate("nonexistent"))
        assert result["ok"] is False
        assert "not found" in result["message"].lower()


class TestServiceReport:
    def test_report_not_found(self):
        from ode.service import generate_report

        result = asyncio.run(generate_report("nonexistent"))
        assert result["ok"] is False
        assert "not found" in result["message"].lower()


class TestServiceScan:
    def test_scan_no_args(self):
        from ode.service import scan

        result = asyncio.run(scan())
        assert result["ok"] is False
        assert "provide" in result["message"].lower()
