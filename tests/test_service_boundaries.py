import asyncio
from pathlib import Path


def test_opportunity_repository_detects_keyword_duplicates(tmp_path, monkeypatch):
    from ode.core.models import Opportunity
    from ode.core.repository import OpportunityRepository

    monkeypatch.setenv("ODE_ROOT", str(tmp_path))
    repo = OpportunityRepository()
    repo.save(Opportunity(name="Invoice Ops", keywords=["AI", "automation", "invoice"]))

    duplicate = repo.find_duplicate("Different Name", ["ai", "automation"])

    assert duplicate is not None
    assert duplicate.opportunity.name == "Invoice Ops"
    assert duplicate.similar_keywords == ["ai", "automation"]


def test_opportunity_scorer_applies_weighted_scores():
    from ode.core.models import Opportunity
    from ode.core.scoring import OpportunityScorer

    opportunity = Opportunity(name="Score Me")
    result = OpportunityScorer().apply(opportunity, {"tam_size": 10, "growth": 8, "pain_evidence": 7})

    assert result.percentage == opportunity.scores["_weighted_pct"]
    assert opportunity.scores["_scoring_details"]
    assert "Market Attractiveness" in opportunity.scores


def test_service_facade_keeps_patchable_pain_fetcher(monkeypatch):
    from ode import service

    fake_fetch = {
        "signals": [{
            "source_id": "reddit_hot_rss",
            "source": "reddit/r/SaaS",
            "title": "Looking for an AI tool to stop manual invoice work, would pay for it",
        }],
        "source_events": [{"source_id": "test", "status": "ok", "count": 1}],
    }
    monkeypatch.setattr(service, "_fetch_pain_source_result", lambda **kwargs: fake_fetch)

    result = asyncio.run(service.listen_pains(hn_top=0, min_grade="E"))

    assert result["ok"] is True
    assert result["data"]["result"]["source_events"][0]["source_id"] == "test"


def test_service_file_is_a_facade():
    source = Path("ode/service.py").read_text(encoding="utf-8")

    assert "from ode.services.opportunities import" in source
    assert "async def create_opportunity" not in source
    assert "from ode.core.store import load_opportunity" not in source


def test_blocking_work_uses_named_async_adapter():
    offenders = [
        str(path)
        for path in Path("ode").rglob("*.py")
        if "run_in_executor" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_api_web_do_not_ship_empty_placeholder_modules():
    assert not Path("ode/api/server.py").exists()
    assert not Path("ode/api/routes.py").exists()
    assert not Path("ode/web/server.py").exists()


def test_mcp_registers_read_only_service_tools(tmp_path, monkeypatch):
    from ode.integrations.mcp_server import setup_tools

    monkeypatch.setenv("ODE_ROOT", str(tmp_path))

    class FakeMCP:
        def __init__(self):
            self.tools = {}

        def tool(self, *, name, description):
            def decorator(func):
                self.tools[name] = {"description": description, "func": func}
                return func

            return decorator

    target = FakeMCP()
    registered = setup_tools(target)

    assert "ode_status" in registered
    assert "ode_show" in target.tools
    assert callable(target.tools["ode_cases"]["func"])
    assert asyncio.run(target.tools["ode_status"]["func"]())["ok"] is True
