"""Daily warning and initial alert bootstrap service functions."""

from __future__ import annotations

from typing import Awaitable, Callable

from ode.services.result import ok


ServiceFn = Callable[..., Awaitable[dict]]


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
                           run_date: str | None = None,
                           listen_pains_fn: ServiceFn | None = None,
                           analyze_revenue_cases_fn: ServiceFn | None = None,
                           explore_signals_fn: ServiceFn | None = None,
                           get_portfolio_fn: ServiceFn | None = None) -> dict:
    from ode.core.store import alerts_dir, reports_dir
    from ode.heuristics.daily_warning import (
        empty_watchlist,
        format_daily_report,
        normalize_daily_inputs,
        today_key,
        update_watchlist,
    )
    from ode.services.discovery import (
        analyze_revenue_cases as default_analyze_revenue_cases,
        explore_signals as default_explore_signals,
        listen_pains as default_listen_pains,
    )
    from ode.services.opportunities import get_portfolio as default_get_portfolio

    listen_pains_fn = listen_pains_fn or default_listen_pains
    analyze_revenue_cases_fn = analyze_revenue_cases_fn or default_analyze_revenue_cases
    explore_signals_fn = explore_signals_fn or default_explore_signals
    get_portfolio_fn = get_portfolio_fn or default_get_portfolio

    day = today_key(run_date)

    pain = await listen_pains_fn(
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
        cases_result = await analyze_revenue_cases_fn(
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
        exploration = await explore_signals_fn(
            hn_top=hn_top,
            subreddits=subreddits,
            keywords=keywords,
        )
        if exploration["ok"]:
            explore_result = exploration["data"]["result"]

    portfolio_result = await get_portfolio_fn()
    portfolio = portfolio_result["data"].get("summaries", []) if portfolio_result["ok"] else []

    candidates = normalize_daily_inputs(
        pain_result=pain_result,
        revenue_cases=cases_result["data"].get("cases", []),
        explore_result=explore_result,
    )

    state_path = alerts_dir() / "watchlist.yaml"
    previous_state = load_daily_watchlist(state_path) if state_path.exists() else empty_watchlist()
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

    save_daily_watchlist(state_path, warning_result["state"])
    daily_dir = reports_dir() / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    report_path = daily_dir / f"{day}.md"
    report_path.write_text(report_text, encoding="utf-8")

    return ok({
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
                                    reset: bool = False,
                                    analyze_revenue_cases_fn: ServiceFn | None = None) -> dict:
    from ode.core.store import alerts_dir, reports_dir
    from ode.heuristics.daily_warning import (
        build_initial_warning_system,
        empty_watchlist,
        format_initial_warning_report,
        today_key,
    )
    from ode.services.discovery import analyze_revenue_cases as default_analyze_revenue_cases

    analyze_revenue_cases_fn = analyze_revenue_cases_fn or default_analyze_revenue_cases
    day = today_key(run_date)
    case_result = await analyze_revenue_cases_fn(
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
        else load_daily_watchlist(state_path)
    )
    initial = build_initial_warning_system(
        previous_state,
        case_result["data"].get("cases", []),
        profile=profile,
        run_date=day,
        reset=reset,
    )

    priors_path = alerts_dir() / "case_priors.yaml"
    report_dir = reports_dir() / "initial"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{day}.md"
    report_text = format_initial_warning_report(initial)

    save_daily_watchlist(state_path, initial["state"])
    save_daily_watchlist(priors_path, {
        "schema_version": "1.0",
        "updated_at": initial["state"].get("updated_at", ""),
        "run_date": day,
        "priors": initial["priors"],
    })
    report_path.write_text(report_text, encoding="utf-8")

    return ok({
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


def load_daily_watchlist(path) -> dict:
    import yaml

    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_daily_watchlist(path, state: dict) -> None:
    import yaml

    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(state, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)
