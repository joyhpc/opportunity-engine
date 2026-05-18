"""Opportunity CRUD, pipeline, and portfolio service functions."""

from __future__ import annotations

from ode.core.repository import OpportunityRepository
from ode.services.result import fail, ok


async def create_opportunity(*, name: str, domain: str = "",
                             keywords: list[str] | None = None,
                             description: str = "",
                             custom_id: str = "",
                             force: bool = False) -> dict:
    from ode.core.models import Opportunity

    repo = OpportunityRepository()
    keywords = keywords or []
    if not force:
        duplicate = repo.find_duplicate(name, keywords)
        if duplicate:
            data = {
                "id": duplicate.opportunity.id,
                "name": duplicate.opportunity.name,
                "domain": duplicate.opportunity.domain,
                "keywords": duplicate.opportunity.keywords,
                "path": "",
                "deduplicated": True,
            }
            if duplicate.similar_keywords:
                data["similar_keywords"] = duplicate.similar_keywords
            return ok(data, message=duplicate.message)

    opportunity = Opportunity(
        name=name,
        domain=domain,
        description=description,
        keywords=keywords,
    )
    if custom_id:
        opportunity.id = custom_id

    path = repo.save(opportunity)
    return ok({
        "id": opportunity.id,
        "name": opportunity.name,
        "domain": opportunity.domain,
        "keywords": opportunity.keywords,
        "path": str(path),
    })


async def list_opportunities() -> dict:
    opportunities = OpportunityRepository().list()
    return ok({
        "opportunities": [
            {"id": item.id, "name": item.name, "stage": item.stage, "status": item.status}
            for item in opportunities
        ],
    })


async def show_opportunity(opp_id: str) -> dict:
    from ode.heuristics.dbs import latest_diagnostic

    opportunity = OpportunityRepository().get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    diagnostics = getattr(opportunity, "diagnostics", []) or []
    return ok({
        "id": opportunity.id,
        "name": opportunity.name,
        "domain": opportunity.domain,
        "stage": opportunity.stage,
        "status": opportunity.status,
        "keywords": opportunity.keywords,
        "created_at": opportunity.created_at,
        "updated_at": opportunity.updated_at,
        "scores": opportunity.scores,
        "market": opportunity.market,
        "financials": opportunity.financials,
        "gate_log": opportunity.gate_log,
        "signal_count": len(opportunity.signals),
        "experiments": getattr(opportunity, "experiments", []),
        "diagnostics": diagnostics,
        "latest_dbs_diagnostic": latest_diagnostic(opportunity.to_dict()),
    })


async def scan(*, opp_id: str | None = None, keywords: list[str] | None = None,
               domain: str = "", hn_top: int = 0,
               subreddits: list[str] | None = None,
               name: str | None = None) -> dict:
    from ode.core.models import Opportunity
    from ode.engine.workers import run_scan

    repo = OpportunityRepository()
    opportunity = repo.get(opp_id) if opp_id else None

    if not opportunity and keywords:
        opportunity = Opportunity(
            name=name or keywords[0],
            domain=domain,
            keywords=keywords,
        )
        repo.save(opportunity)

    if not opportunity:
        return fail("Provide --keywords or --opp-id")

    result = await run_scan(
        opportunity.id,
        keywords=keywords or None,
        domain=domain,
        hn_top=hn_top,
        subreddits=subreddits,
    )

    return ok({
        "status": result.status,
        "signal_count": result.scores.get("signal_count", 0),
        "gate": result.scores.get("gate"),
        "next_action": result.next_action,
        "message": result.message,
        "opp_id": opportunity.id,
        "auto_created": opp_id is None and keywords is not None,
    }, message=result.message)


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
    from ode.engine.workers import run_eval

    opportunity = OpportunityRepository().get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

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
        opportunity.id,
        depth=depth,
        market_params=market_params,
        financial_params=financial_params,
        scores=scores,
    )

    return ok({
        "status": result.status,
        "depth": depth,
        "gate": result.data.get("gate"),
        "scoring": result.data.get("scoring"),
        "next_action": result.next_action,
        "message": result.message,
    }, message=result.message)


async def generate_report(opp_id: str, *, stage: str = "screen") -> dict:
    from ode.engine.workers import run_report

    opportunity = OpportunityRepository().get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    result = await run_report(opportunity.id, stage=stage)
    if result.status != "ok":
        return fail(result.message)

    return ok({
        "report_path": result.data.get("report_path", ""),
        "report_text": result.data.get("report_text", ""),
    })


async def get_status() -> dict:
    from ode.data.cache import Cache

    opportunities = OpportunityRepository().list()
    active = [item for item in opportunities if item.status == "active"]
    killed = [item for item in opportunities if item.status == "killed"]

    cache_stats = {}
    try:
        cache_stats = Cache().stats()
    except Exception:
        pass

    return ok({
        "total": len(opportunities),
        "active_count": len(active),
        "killed_count": len(killed),
        "active": [
            {"id": item.id, "name": item.name, "stage": item.stage}
            for item in active
        ],
        "cache": cache_stats,
    })


async def get_portfolio() -> dict:
    from ode.engine.portfolio import format_portfolio, get_portfolio_summary

    summaries = get_portfolio_summary()
    return ok({
        "summaries": summaries,
        "formatted": format_portfolio(summaries),
    })


async def compare_opportunities(ids: list[str]) -> dict:
    from ode.engine.portfolio import compare_opportunities as _compare

    return ok({"formatted": _compare(ids)})
