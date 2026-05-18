"""Public async service facade for ODE surfaces.

All functions return ``{"ok": bool, "data": dict, "message": str}``.
Implementation lives in ``ode.services`` modules; this facade preserves the
historical ``ode.service`` import path used by CLI, Skills, MCP, and tests.
"""

from __future__ import annotations

from typing import Any

from ode.services.dbs import (
    build_ai_hardware_workflow,
    clarify_goal,
    deconstruct_concept,
    diagnose_business,
    run_dbs_session,
)
from ode.services.discovery import (
    analyze_revenue_cases,
    explore_signals,
    fetch_pain_source_result as _fetch_pain_source_result_impl,
    fetch_pain_sources as _fetch_pain_sources_impl,
    list_data_sources,
    listen_pains as _listen_pains_impl,
)
from ode.services.insights import (
    add_experiment,
    apply_lens,
    get_insights,
    record_actuals,
    refresh_gate,
)
from ode.services.opportunities import (
    compare_opportunities,
    create_opportunity,
    evaluate,
    generate_report,
    get_portfolio,
    get_status,
    list_opportunities,
    scan,
    show_opportunity,
)
from ode.services.result import fail as _fail
from ode.services.result import ok as _ok
from ode.services.warnings import (
    initialize_warning_system as _initialize_warning_system_impl,
    load_daily_watchlist as _load_daily_watchlist,
    run_daily_review as _run_daily_review_impl,
    save_daily_watchlist as _save_daily_watchlist,
)


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
    return await _run_daily_review_impl(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
        keywords=keywords,
        profile=profile,
        min_grade=min_grade,
        limit=limit,
        cases_path=cases_path,
        cases_region=cases_region,
        cases_min_grade=cases_min_grade,
        cases_top=cases_top,
        include_explore=include_explore,
        run_date=run_date,
        listen_pains_fn=listen_pains,
        analyze_revenue_cases_fn=analyze_revenue_cases,
        explore_signals_fn=explore_signals,
        get_portfolio_fn=get_portfolio,
    )


async def initialize_warning_system(*, cases_path: str | None = None,
                                    profile: dict | None = None,
                                    region: str | None = None,
                                    min_grade: str | None = "C",
                                    top: int | None = None,
                                    run_date: str | None = None,
                                    reset: bool = False) -> dict:
    return await _initialize_warning_system_impl(
        cases_path=cases_path,
        profile=profile,
        region=region,
        min_grade=min_grade,
        top=top,
        run_date=run_date,
        reset=reset,
        analyze_revenue_cases_fn=analyze_revenue_cases,
    )


async def listen_pains(*, hn_top: int = 50,
                       subreddits: list[str] | None = None,
                       reddit_limit: int = 15,
                       include_product_hunt: bool = True,
                       product_hunt_limit: int = 30,
                       keywords: list[str] | None = None,
                       profile: dict | None = None,
                       min_grade: str = "E",
                       limit: int = 20) -> dict:
    return await _listen_pains_impl(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
        keywords=keywords,
        profile=profile,
        min_grade=min_grade,
        limit=limit,
        fetch_pain_source_result_fn=_fetch_pain_source_result,
    )


def _fetch_pain_sources(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> list[dict[str, Any]]:
    return _fetch_pain_sources_impl(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )


def _fetch_pain_source_result(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> dict[str, Any]:
    return _fetch_pain_source_result_impl(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )


__all__ = [
    "_fail",
    "_fetch_pain_source_result",
    "_fetch_pain_sources",
    "_load_daily_watchlist",
    "_ok",
    "_save_daily_watchlist",
    "add_experiment",
    "analyze_revenue_cases",
    "apply_lens",
    "build_ai_hardware_workflow",
    "clarify_goal",
    "compare_opportunities",
    "create_opportunity",
    "deconstruct_concept",
    "diagnose_business",
    "evaluate",
    "explore_signals",
    "generate_report",
    "get_insights",
    "get_portfolio",
    "get_status",
    "initialize_warning_system",
    "list_data_sources",
    "list_opportunities",
    "listen_pains",
    "record_actuals",
    "refresh_gate",
    "run_daily_review",
    "run_dbs_session",
    "scan",
    "show_opportunity",
]
