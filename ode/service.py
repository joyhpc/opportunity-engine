"""ODE Service Layer — pure Python async API, zero print / zero sys.exit.

All functions return ``{"ok": bool, "data": dict, "message": str}``.
This layer sits between surfaces (CLI, MCP, API, Skill) and the engine.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter

logger = logging.getLogger(__name__)


def _ok(data: dict, message: str = "") -> dict:
    return {"ok": True, "data": data, "message": message}


def _fail(message: str) -> dict:
    return {"ok": False, "data": {}, "message": message}


# ---------------------------------------------------------------------------
# Opportunity CRUD
# ---------------------------------------------------------------------------

async def create_opportunity(*, name: str, domain: str = "",
                             keywords: list[str] | None = None,
                             description: str = "",
                             custom_id: str = "") -> dict:
    from ode.core.models import Opportunity
    from ode.core.store import save_opportunity

    opp = Opportunity(
        name=name,
        domain=domain,
        description=description,
        keywords=keywords or [],
    )
    if custom_id:
        opp.id = custom_id

    path = save_opportunity(opp)
    return _ok({
        "id": opp.id,
        "name": opp.name,
        "domain": opp.domain,
        "keywords": opp.keywords,
        "path": str(path),
    })


async def list_opportunities() -> dict:
    from ode.core.store import list_opportunities as _list_opps

    opps = _list_opps()
    return _ok({
        "opportunities": [
            {"id": o.id, "name": o.name, "stage": o.stage, "status": o.status}
            for o in opps
        ],
    })


async def show_opportunity(opp_id: str) -> dict:
    from ode.core.store import load_opportunity, find_opportunity_by_name

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    return _ok({
        "id": opp.id,
        "name": opp.name,
        "domain": opp.domain,
        "stage": opp.stage,
        "status": opp.status,
        "keywords": opp.keywords,
        "created_at": opp.created_at,
        "updated_at": opp.updated_at,
        "scores": opp.scores,
        "market": opp.market,
        "financials": opp.financials,
        "gate_log": opp.gate_log,
        "signal_count": len(opp.signals),
    })


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

async def scan(*, opp_id: str | None = None, keywords: list[str] | None = None,
               domain: str = "", hn_top: int = 0,
               subreddits: list[str] | None = None,
               name: str | None = None) -> dict:
    from ode.core.models import Opportunity
    from ode.core.store import (
        load_opportunity, find_opportunity_by_name, save_opportunity,
    )
    from ode.engine.workers import run_scan

    opp = None
    if opp_id:
        opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)

    if not opp and keywords:
        opp = Opportunity(
            name=name or keywords[0],
            domain=domain,
            keywords=keywords,
        )
        save_opportunity(opp)

    if not opp:
        return _fail("Provide --keywords or --opp-id")

    kw_list = keywords or None
    result = await run_scan(
        opp.id,
        keywords=kw_list,
        domain=domain,
        hn_top=hn_top,
        subreddits=subreddits,
    )

    return _ok({
        "status": result.status,
        "signal_count": result.scores.get("signal_count", 0),
        "gate": result.scores.get("gate"),
        "next_action": result.next_action,
        "message": result.message,
        "opp_id": opp.id,
        "auto_created": opp_id is None and keywords is not None,
    }, message=result.message)


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------

async def evaluate(opp_id: str, *, depth: str = "screen",
                   tam: float | None = None,
                   segment_pct: float | None = None,
                   geo_pct: float | None = None,
                   arpu: float | None = None,
                   cac: float | None = None,
                   churn: float | None = None,
                   cogs_pct: float | None = None,
                   monthly_users: int | None = None,
                   growth_rate: float | None = None,
                   opex: float | None = None,
                   scores: dict | None = None) -> dict:
    from ode.core.store import load_opportunity, find_opportunity_by_name
    from ode.engine.workers import run_eval

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    market_params = None
    if tam is not None:
        market_params = {
            "market_size": tam,
            "segment_pct": segment_pct or 10,
            "geo_pct": geo_pct or 30,
        }

    financial_params = None
    if arpu is not None:
        financial_params = {
            "arpu": arpu,
            "cac": cac or 50,
            "churn_rate": churn or 5.0,
            "cogs_pct": cogs_pct or 20,
            "monthly_new_users": monthly_users or 100,
            "user_growth_rate": growth_rate or 10,
            "monthly_opex": opex or 5000,
        }

    result = await run_eval(
        opp.id,
        depth=depth,
        market_params=market_params,
        financial_params=financial_params,
        scores=scores,
    )

    return _ok({
        "status": result.status,
        "depth": depth,
        "gate": result.data.get("gate"),
        "scoring": result.data.get("scoring"),
        "next_action": result.next_action,
        "message": result.message,
    }, message=result.message)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

async def generate_report(opp_id: str, *, stage: str = "screen") -> dict:
    from ode.core.store import load_opportunity, find_opportunity_by_name
    from ode.engine.workers import run_report

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    result = await run_report(opp.id, stage=stage)

    if result.status != "ok":
        return _fail(result.message)

    return _ok({
        "report_path": result.data.get("report_path", ""),
        "report_text": result.data.get("report_text", ""),
    })


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

async def get_status() -> dict:
    from ode.core.store import list_opportunities as _list_opps
    from ode.data.cache import Cache

    opps = _list_opps()
    active = [o for o in opps if o.status == "active"]
    killed = [o for o in opps if o.status == "killed"]

    cache_stats = {}
    try:
        cache = Cache()
        cache_stats = cache.stats()
    except Exception:
        pass

    return _ok({
        "total": len(opps),
        "active_count": len(active),
        "killed_count": len(killed),
        "active": [
            {"id": o.id, "name": o.name, "stage": o.stage}
            for o in active
        ],
        "cache": cache_stats,
    })


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

async def get_portfolio() -> dict:
    from ode.engine.portfolio import get_portfolio_summary, format_portfolio

    summaries = get_portfolio_summary()
    return _ok({
        "summaries": summaries,
        "formatted": format_portfolio(summaries),
    })


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

async def compare_opportunities(ids: list[str]) -> dict:
    from ode.engine.portfolio import compare_opportunities as _compare

    text = _compare(ids)
    return _ok({"formatted": text})


# ---------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------

async def explore_signals(*, hn_top: int = 30,
                          subreddits: list[str] | None = None,
                          keywords: list[str] | None = None) -> dict:
    from ode.heuristics.explore import explore_with_fetch, format_exploration_report

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: explore_with_fetch(
            hn_top=hn_top,
            subreddits=subreddits,
            keywords=keywords,
        ),
    )

    return _ok({
        "result": result,
        "formatted": format_exploration_report(result),
    })


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

async def get_insights(opp_id: str) -> dict:
    from ode.core.store import load_opportunity, find_opportunity_by_name, list_signals
    from ode.heuristics.synthesize import synthesize
    from ode.heuristics.reframe import generate_reframe
    from ode.heuristics.explore import classify_demand_pattern
    from ode.heuristics.bridge import quick_assess

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    signals = list_signals(opp.id)
    signal_dicts = [s.to_dict() for s in signals]
    opp_data = {
        "scores": opp.scores,
        "market": opp.market,
        "financials": opp.financials,
        "regulatory": opp.regulatory,
        "signals": signal_dicts,
        "gate_log": opp.gate_log,
        "stage": opp.stage,
        "domain": opp.domain,
    }

    # Synthesis
    synthesis = synthesize(opp_data)

    # Quick assess for early-stage
    assessment = None
    if opp.stage in ("SENSE", "SCREEN") and signal_dicts:
        assessment = quick_assess(signal_dicts, domain=opp.domain)

    # Demand pattern
    demand_pattern = ""
    if signal_dicts:
        patterns = [classify_demand_pattern(s) for s in signal_dicts]
        pattern_counts = Counter(p for p in patterns if p != "unclassified")
        if pattern_counts:
            demand_pattern = pattern_counts.most_common(1)[0][0]

    # Reframe if borderline
    reframe = None
    weighted_pct = opp.scores.get("_weighted_pct", 0) if opp.scores else 0
    if weighted_pct and weighted_pct < 70:
        verdict = "KILL" if weighted_pct < 50 else "MAYBE"
        weakest = ""
        dim_scores = {k: v for k, v in opp.scores.items()
                      if not k.startswith("_") and not isinstance(v, (list, dict))}
        if dim_scores:
            weakest = min(dim_scores, key=lambda k: dim_scores[k])

        scoring_details = opp.scores.get("_scoring_details") if opp.scores else None

        reframe = generate_reframe(
            scores=opp.scores,
            verdict=verdict,
            weakest_dimension=weakest,
            scoring_details=scoring_details,
            domain=opp.domain,
            demand_pattern=demand_pattern,
        )

    return _ok({
        "synthesis": synthesis,
        "quick_assess": assessment,
        "demand_pattern": demand_pattern,
        "reframe": reframe,
    })
