import asyncio
import os

import pytest


@pytest.fixture(autouse=True)
def isolated_test_root(tmp_path):
    os.environ["ODE_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("ODE_ROOT", None)


def test_fit_lens_recommends_build_now_for_high_score_and_high_fit():
    from ode.heuristics.fit_lens import BUILD_NOW, apply_fit_lens, default_profile

    opportunity = {
        "name": "AI Agent Devtool",
        "domain": "developer tools",
        "description": "Software engineering AI workflows for rapid prototyping.",
        "keywords": ["AI agents", "developer tools", "automation"],
        "scores": {
            "_weighted_pct": 74,
            "Capability Fit": 8,
            "Market Attractiveness": 8,
            "AI-Native Potential (a16z)": 8,
        },
    }
    signals = [
        {"title": "AI agent automation demand", "source": "HN", "strength": "强"},
        {"title": "Developer tools team pays for agent workflow", "source": "GitHub", "strength": "中"},
        {"title": "Founder community asks for agent debugging", "source": "Forum", "strength": "中"},
    ]

    result = apply_fit_lens(opportunity, signals, default_profile())

    assert result.recommendation == BUILD_NOW
    assert result.founder_fit >= 70
    assert result.discovery_value >= 70


def test_fit_lens_protects_high_discovery_low_fit_as_watch():
    from ode.heuristics.fit_lens import WATCH, apply_fit_lens, default_profile

    opportunity = {
        "name": "Autonomous Lab Hardware",
        "domain": "biotech",
        "description": "Autonomous clinical trial hardware manufacturing platform.",
        "keywords": ["autonomous lab", "clinical trial", "hardware"],
        "scores": {
            "_weighted_pct": 76,
            "Capability Fit": 2,
            "Market Attractiveness": 9,
            "AI-Native Potential (a16z)": 8,
        },
    }
    signals = [
        {"title": "New autonomous lab infrastructure funding", "source": "News", "strength": "强"},
        {"title": "Clinical automation papers surge", "source": "arXiv", "strength": "强"},
        {"title": "Manufacturing bottleneck for lab robotics", "source": "Forum", "strength": "中"},
        {"title": "Biotech operators need autonomous workflows", "source": "Interview", "strength": "中"},
    ]

    result = apply_fit_lens(opportunity, signals, default_profile())

    assert result.recommendation == WATCH
    assert result.protected_as_wildcard is True
    assert result.discovery_value > result.founder_fit


def test_fit_lens_hard_exclusion_can_ignore():
    from ode.heuristics.fit_lens import IGNORE, apply_fit_lens, default_profile

    opportunity = {
        "name": "Fraud Automation",
        "domain": "growth",
        "description": "Fraud automation for fake signups.",
        "keywords": ["fraud"],
        "scores": {"_weighted_pct": 80},
    }

    result = apply_fit_lens(opportunity, [], default_profile())

    assert result.recommendation == IGNORE
    assert any("Hard exclusion" in risk for risk in result.risks)


def test_service_apply_lens_returns_soft_recommendation():
    from ode import service

    created = asyncio.run(service.create_opportunity(
        name="Agent Workflow Debugger",
        domain="developer tools",
        keywords=["AI agents", "developer tools"],
        description="Software engineering AI workflows for rapid prototyping.",
    ))

    result = asyncio.run(service.apply_lens(created["data"]["id"]))

    assert result["ok"] is True
    assert result["data"]["lens"]["recommendation"] in {
        "Build Now",
        "Validate Soon",
        "Watch",
        "Research",
        "Ignore",
    }
    assert "profile" in result["data"]
