"""ODE Service Layer — pure Python async API, zero print / zero sys.exit.

All functions return ``{"ok": bool, "data": dict, "message": str}``.
This layer sits between surfaces (CLI, MCP, API, Skill) and the engine.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from typing import Any

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
                             custom_id: str = "",
                             force: bool = False) -> dict:
    from ode.core.models import Opportunity
    from ode.core.store import save_opportunity, list_opportunities as _list_opps

    # Dedup check: skip if force=True
    if not force:
        for opp in _list_opps():
            if opp.name.lower() == name.lower():
                return _ok({
                    "id": opp.id, "name": opp.name, "domain": opp.domain,
                    "keywords": opp.keywords, "path": "", "deduplicated": True,
                }, message=f"Existing opportunity '{opp.name}' (id={opp.id})")
            if keywords:
                overlap = set(k.lower() for k in keywords) & set(k.lower() for k in opp.keywords)
                if len(overlap) / max(len(keywords), 1) >= 0.7:
                    return _ok({
                        "id": opp.id, "name": opp.name, "domain": opp.domain,
                        "keywords": opp.keywords, "path": "",
                        "deduplicated": True, "similar_keywords": list(overlap),
                    }, message=f"Similar opportunity '{opp.name}' found — use --force to create anyway")

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
        "experiments": getattr(opp, "experiments", []),
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
# Daily Review / Warning Layer
# ---------------------------------------------------------------------------

async def run_daily_review(*, hn_top: int = 50,
                           subreddits: list[str] | None = None,
                           reddit_limit: int = 15,
                           include_product_hunt: bool = True,
                           product_hunt_limit: int = 30,
                           keywords: list[str] | None = None,
                           profile: dict | None = None,
                           min_grade: str = "E",
                           limit: int = 20,
                           cases_path: str | None = None,
                           cases_region: str | None = None,
                           cases_min_grade: str | None = "B",
                           cases_top: int | None = 10,
                           include_explore: bool = True,
                           run_date: str | None = None) -> dict:
    """Run the daily opportunity review and update the warning watchlist."""

    from ode.core.store import alerts_dir, reports_dir
    from ode.heuristics.daily_warning import (
        empty_watchlist,
        format_daily_report,
        normalize_daily_inputs,
        today_key,
        update_watchlist,
    )

    day = today_key(run_date)

    pain = await listen_pains(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
        keywords=keywords,
        profile=profile,
        min_grade=min_grade,
        limit=limit,
    )
    if not pain["ok"]:
        return pain
    pain_result = pain["data"]["result"]

    cases_result = {"ok": True, "data": {"cases": [], "formatted": "", "count": 0}, "message": ""}
    if cases_top != 0:
        cases_result = await analyze_revenue_cases(
            path=cases_path,
            profile=profile,
            region=cases_region,
            min_grade=cases_min_grade,
            top=cases_top,
        )
        if not cases_result["ok"]:
            return cases_result

    explore_result = {"status": "skipped", "hypotheses": []}
    if include_explore:
        exploration = await explore_signals(
            hn_top=hn_top,
            subreddits=subreddits,
            keywords=keywords,
        )
        if exploration["ok"]:
            explore_result = exploration["data"]["result"]

    portfolio_result = await get_portfolio()
    portfolio = portfolio_result["data"].get("summaries", []) if portfolio_result["ok"] else []

    candidates = normalize_daily_inputs(
        pain_result=pain_result,
        revenue_cases=cases_result["data"].get("cases", []),
        explore_result=explore_result,
    )

    state_path = alerts_dir() / "watchlist.yaml"
    previous_state = _load_daily_watchlist(state_path) if state_path.exists() else empty_watchlist()
    warning_result = update_watchlist(
        previous_state,
        candidates,
        run_date=day,
    )

    source_events = pain_result.get("source_events", [])
    report_text = format_daily_report(
        warning_result,
        source_events=source_events,
        portfolio=portfolio,
    )

    _save_daily_watchlist(state_path, warning_result["state"])
    daily_dir = reports_dir() / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    report_path = daily_dir / f"{day}.md"
    report_path.write_text(report_text, encoding="utf-8")

    return _ok({
        "alerts": warning_result["alerts"],
        "watchlist_updates": warning_result["watchlist_updates"],
        "source_events": source_events,
        "report_path": str(report_path),
        "state_path": str(state_path),
        "report_text": report_text,
        "candidates": candidates,
        "portfolio": portfolio,
        "pain": pain_result,
        "revenue_cases": cases_result["data"].get("cases", []),
        "explore": explore_result,
    }, message=f"Daily review generated {len(warning_result['alerts'])} alert(s)")


async def initialize_warning_system(*, cases_path: str | None = None,
                                    profile: dict | None = None,
                                    region: str | None = None,
                                    min_grade: str | None = "C",
                                    top: int | None = None,
                                    run_date: str | None = None,
                                    reset: bool = False) -> dict:
    """Bootstrap the warning system from a broad revenue-case learning pass."""

    from ode.core.store import alerts_dir, reports_dir
    from ode.heuristics.daily_warning import (
        build_initial_warning_system,
        empty_watchlist,
        format_initial_warning_report,
        today_key,
    )

    day = today_key(run_date)
    case_result = await analyze_revenue_cases(
        path=cases_path,
        profile=profile,
        region=region,
        min_grade=min_grade,
        top=top,
    )
    if not case_result["ok"]:
        return case_result

    state_path = alerts_dir() / "watchlist.yaml"
    previous_state = (
        empty_watchlist()
        if reset or not state_path.exists()
        else _load_daily_watchlist(state_path)
    )
    initial = build_initial_warning_system(
        previous_state,
        case_result["data"].get("cases", []),
        run_date=day,
        reset=reset,
    )

    priors_path = alerts_dir() / "case_priors.yaml"
    report_dir = reports_dir() / "initial"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{day}.md"
    report_text = format_initial_warning_report(initial)

    _save_daily_watchlist(state_path, initial["state"])
    _save_daily_watchlist(priors_path, {
        "schema_version": "1.0",
        "updated_at": initial["state"].get("updated_at", ""),
        "run_date": day,
        "priors": initial["priors"],
    })
    report_path.write_text(report_text, encoding="utf-8")

    return _ok({
        "alerts": initial["alerts"],
        "watchlist_updates": initial["watchlist_updates"],
        "priors": initial["priors"],
        "case_count": initial["case_count"],
        "candidate_count": initial["candidate_count"],
        "report_path": str(report_path),
        "state_path": str(state_path),
        "priors_path": str(priors_path),
        "report_text": report_text,
        "cases": case_result["data"].get("cases", []),
    }, message=f"Initialized warning system from {initial['case_count']} case(s)")


def _load_daily_watchlist(path) -> dict:
    import yaml

    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _save_daily_watchlist(path, state: dict) -> None:
    import yaml

    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(state, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------

async def list_data_sources(status: str | None = None, region: str | None = None) -> dict:
    from ode.tools.source_registry import format_source_catalog, list_sources, runtime_source_ids

    sources = list_sources(status=status, region=region)
    runtime_ids = runtime_source_ids()
    return _ok({
        "sources": [
            {**source.to_dict(), "used_by_scan_workers": source.id in runtime_ids}
            for source in sources
        ],
        "formatted": format_source_catalog(sources),
        "runtime_source_ids": sorted(runtime_ids),
    })


# ---------------------------------------------------------------------------
# Revenue Cases
# ---------------------------------------------------------------------------

async def analyze_revenue_cases(*, path: str | None = None,
                                profile: dict | None = None,
                                region: str | None = None,
                                min_grade: str | None = None,
                                top: int | None = None) -> dict:
    """Analyze revenue-proven cases without mixing them into trend scans."""
    from ode.heuristics.revenue_cases import (
        analyze_revenue_cases as _analyze_cases,
        format_revenue_case_report,
    )

    analyses = _analyze_cases(
        path=path,
        profile=profile,
        region=region,
        min_grade=min_grade,
        top=top,
    )
    return _ok({
        "cases": [item.to_dict() for item in analyses],
        "formatted": format_revenue_case_report(analyses),
        "count": len(analyses),
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
# Pain Listener
# ---------------------------------------------------------------------------

async def listen_pains(*, hn_top: int = 50,
                       subreddits: list[str] | None = None,
                       reddit_limit: int = 15,
                       include_product_hunt: bool = True,
                       product_hunt_limit: int = 30,
                       keywords: list[str] | None = None,
                       profile: dict | None = None,
                       min_grade: str = "E",
                       limit: int = 20) -> dict:
    from ode.heuristics.pain_listener import (
        VALID_EVIDENCE_GRADES,
        format_pain_report,
        listen,
    )

    normalized_grade = (min_grade or "E").upper()
    if normalized_grade not in VALID_EVIDENCE_GRADES:
        return _fail(
            "Unsupported pain evidence grade "
            f"'{normalized_grade}'. Use one of: {', '.join(VALID_EVIDENCE_GRADES)}."
        )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _listen_pains_sync(
            listen=listen,
            hn_top=hn_top,
            subreddits=subreddits,
            reddit_limit=reddit_limit,
            include_product_hunt=include_product_hunt,
            product_hunt_limit=product_hunt_limit,
            profile=profile,
            keywords=keywords,
            min_grade=normalized_grade,
            limit=limit,
        ),
    )

    return _ok({
        "result": result,
        "formatted": format_pain_report(result),
    })


def _listen_pains_sync(
    *,
    listen,
    hn_top: int,
    subreddits: list[str] | None,
    reddit_limit: int,
    include_product_hunt: bool,
    product_hunt_limit: int,
    profile: dict | None,
    keywords: list[str] | None,
    min_grade: str,
    limit: int,
) -> dict:
    fetch_result = _fetch_pain_source_result(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )
    return listen(
        fetch_result["signals"],
        profile=profile,
        keywords=keywords,
        min_grade=min_grade,
        limit=limit,
        source_events=fetch_result["source_events"],
    )


def _fetch_pain_sources(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> list[dict[str, Any]]:
    """Fetch raw signals for the pain-listener service entrypoint."""

    return _fetch_pain_source_result(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )["signals"]


def _fetch_pain_source_result(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> dict[str, Any]:
    """Fetch raw signals and structured source events for pain listener."""

    from ode.heuristics.pain_listener import DEFAULT_REDDIT_SUBS
    from ode.tools.source_dispatch import scan_for_context_with_notes

    subs = DEFAULT_REDDIT_SUBS if subreddits is None else subreddits
    return scan_for_context_with_notes(
        "pain_listener",
        hn_top=hn_top,
        subreddits=subs,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )


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
        "experiments": getattr(opp, "experiments", []),
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


# ---------------------------------------------------------------------------
# Founder Fit Lens
# ---------------------------------------------------------------------------

async def apply_lens(opp_id: str, *, profile: dict | None = None) -> dict:
    """Apply the Founder Fit Lens without mutating the opportunity."""
    from ode.core.store import load_opportunity, find_opportunity_by_name, list_signals
    from ode.heuristics.fit_lens import FounderProfile, apply_fit_lens

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    founder = FounderProfile.from_dict(profile)
    signals = [signal.to_dict() for signal in list_signals(opp.id)]
    result = apply_fit_lens(
        opportunity=opp.to_dict(),
        signals=signals,
        profile=founder,
    )

    return _ok({
        "opportunity_id": opp.id,
        "opportunity_name": opp.name,
        "profile": founder.to_dict(),
        "lens": result.to_dict(),
    }, message=f"Lens recommendation: {result.recommendation}")


# ---------------------------------------------------------------------------
# Experiment tracking
# ---------------------------------------------------------------------------

async def add_experiment(opp_id: str, *, version: str, description: str = "",
                         cogs: float | None = None, outcome: str = "partial",
                         metrics: dict | None = None, result: str = "") -> dict:
    """Record a prototype iteration / validation experiment."""
    from ode.core.models import _now_iso
    from ode.core.store import load_opportunity, find_opportunity_by_name, save_opportunity

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    entry = {
        "version": version,
        "description": description,
        "cogs": cogs,
        "outcome": outcome,
        "result": result,
        "metrics": metrics or {},
        "ts": _now_iso(),
    }
    if not hasattr(opp, "experiments") or opp.experiments is None:
        opp.experiments = []
    opp.experiments.append(entry)
    opp.updated_at = _now_iso()

    # Auto-update actuals if outcome=pass and cogs provided
    if cogs is not None and outcome == "pass":
        opp.financials.setdefault("actuals", {})["cogs_per_unit"] = cogs
        opp.financials["actuals"]["recorded_at"] = _now_iso()

    save_opportunity(opp)
    return _ok({
        "version": version,
        "outcome": outcome,
        "experiment_count": len(opp.experiments),
    }, message=f"Experiment {version} recorded ({outcome})")


# ---------------------------------------------------------------------------
# Record actuals (estimated vs measured)
# ---------------------------------------------------------------------------

async def record_actuals(opp_id: str, *, cogs: float | None = None,
                         arpu: float | None = None, units_sold: int | None = None,
                         notes: str = "") -> dict:
    """Record actual financial data from real-world validation."""
    from ode.core.models import _now_iso
    from ode.core.store import load_opportunity, find_opportunity_by_name, save_opportunity

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    actuals = opp.financials.setdefault("actuals", {})
    if cogs is not None:
        actuals["cogs_per_unit"] = cogs
        # Compute variance vs estimate
        est = opp.financials.get("cogs_per_unit_estimated")
        if est and est > 0:
            actuals["cogs_variance_pct"] = round((cogs - est) / est * 100, 1)
    if arpu is not None:
        actuals["arpu_actual"] = arpu
    if units_sold is not None:
        actuals["units_sold"] = units_sold
    actuals["notes"] = notes
    actuals["recorded_at"] = _now_iso()
    opp.updated_at = _now_iso()
    save_opportunity(opp)

    return _ok({"actuals": actuals}, message="Actuals recorded")


# ---------------------------------------------------------------------------
# Refresh gate (re-evaluate with current state)
# ---------------------------------------------------------------------------

async def refresh_gate(opp_id: str) -> dict:
    """Re-evaluate the current gate with latest data including experiments."""
    from ode.core.models import _now_iso
    from ode.core.store import load_opportunity, find_opportunity_by_name, save_opportunity
    from ode.engine.gate import evaluate_gate

    opp = load_opportunity(opp_id) or find_opportunity_by_name(opp_id)
    if not opp:
        return _fail(f"Opportunity not found: {opp_id}")

    last_verdict = opp.gate_log[-1]["verdict"] if opp.gate_log else None
    experiments = getattr(opp, "experiments", [])
    passed_experiments = [e for e in experiments if e.get("outcome") == "pass"]

    if opp.stage == "SCREEN" and opp.scores:
        scoring_dict = {
            "percentage": opp.scores.get("_weighted_pct", 0),
            "redline_violations": [],
        }
        result = evaluate_gate("SCREEN", scoring_result=scoring_dict)

        # Prototype evidence override: if experiments passed and score >= 45
        if passed_experiments and result["verdict"] == "MAYBE":
            pct = scoring_dict["percentage"]
            if pct >= 45:
                result["verdict"] = "GO"
                result["detail"] = (
                    f"{len(passed_experiments)} prototype(s) passed — "
                    f"overriding borderline score ({pct:.0f}/100)"
                )
    elif opp.stage == "ANALYZE":
        result = evaluate_gate("ANALYZE",
                               financials=opp.financials,
                               regulatory=opp.regulatory)
    else:
        result = {"gate": opp.stage, "verdict": "UNKNOWN",
                  "detail": "No re-evaluation rule for this stage"}

    verdict_changed = result.get("verdict") != last_verdict
    if verdict_changed and result["verdict"] in ("GO", "MAYBE", "KILL"):
        opp.gate_log.append({
            "gate": opp.stage,
            "verdict": result["verdict"],
            "score": result.get("score", 0),
            "ts": _now_iso(),
            "trigger": "manual_refresh",
        })
        opp.updated_at = _now_iso()
        save_opportunity(opp)

    return _ok({
        "new_verdict": result["verdict"],
        "previous_verdict": last_verdict,
        "verdict_changed": verdict_changed,
        "detail": result.get("detail", ""),
        "passed_experiments": len(passed_experiments),
    }, message=f"Gate: {last_verdict} → {result['verdict']}"
       if verdict_changed else f"Gate unchanged: {result['verdict']}")
