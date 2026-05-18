"""Discovery, source catalog, revenue cases, and pain-listener services."""

from __future__ import annotations

from typing import Any, Callable

from ode.core.async_utils import run_blocking
from ode.services.result import ok


FetchPainSourceResult = Callable[..., dict[str, Any]]


async def list_data_sources(status: str | None = None, region: str | None = None) -> dict:
    from ode.tools.source_registry import format_source_catalog, list_sources, runtime_source_ids

    sources = list_sources(status=status, region=region)
    runtime_ids = runtime_source_ids()
    return ok({
        "sources": [
            {**source.to_dict(), "used_by_scan_workers": source.id in runtime_ids}
            for source in sources
        ],
        "formatted": format_source_catalog(sources),
        "runtime_source_ids": sorted(runtime_ids),
    })


async def analyze_revenue_cases(*, path: str | None = None,
                                profile: dict | None = None,
                                region: str | None = None,
                                min_grade: str | None = None,
                                top: int | None = None) -> dict:
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
    return ok({
        "cases": [item.to_dict() for item in analyses],
        "formatted": format_revenue_case_report(analyses),
        "count": len(analyses),
    })


async def explore_signals(*, hn_top: int = 30,
                          subreddits: list[str] | None = None,
                          keywords: list[str] | None = None) -> dict:
    from ode.heuristics.explore import explore_with_fetch, format_exploration_report

    result = await run_blocking(
        explore_with_fetch,
        hn_top=hn_top,
        subreddits=subreddits,
        keywords=keywords,
    )

    return ok({
        "result": result,
        "formatted": format_exploration_report(result),
    })


async def listen_pains(*, hn_top: int = 50,
                       subreddits: list[str] | None = None,
                       reddit_limit: int = 15,
                       include_product_hunt: bool = True,
                       product_hunt_limit: int = 30,
                       keywords: list[str] | None = None,
                       profile: dict | None = None,
                       min_grade: str = "E",
                       limit: int = 20,
                       fetch_pain_source_result_fn: FetchPainSourceResult | None = None) -> dict:
    from ode.heuristics.pain_listener import (
        VALID_EVIDENCE_GRADES,
        format_pain_report,
        listen,
    )

    normalized_grade = (min_grade or "E").upper()
    if normalized_grade not in VALID_EVIDENCE_GRADES:
        from ode.services.result import fail

        return fail(
            "Unsupported pain evidence grade "
            f"'{normalized_grade}'. Use one of: {', '.join(VALID_EVIDENCE_GRADES)}."
        )

    fetcher = fetch_pain_source_result_fn or fetch_pain_source_result
    result = await run_blocking(
        _listen_pains_sync,
        listen=listen,
        fetch_pain_source_result_fn=fetcher,
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
        profile=profile,
        keywords=keywords,
        min_grade=normalized_grade,
        limit=limit,
    )

    return ok({
        "result": result,
        "formatted": format_pain_report(result),
    })


def _listen_pains_sync(
    *,
    listen,
    fetch_pain_source_result_fn: FetchPainSourceResult,
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
    fetch_result = fetch_pain_source_result_fn(
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


def fetch_pain_sources(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> list[dict[str, Any]]:
    return fetch_pain_source_result(
        hn_top=hn_top,
        subreddits=subreddits,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )["signals"]


def fetch_pain_source_result(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> dict[str, Any]:
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
