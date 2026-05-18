"""DBS Lens and AI hardware workflow service functions."""

from __future__ import annotations

from ode.core.repository import OpportunityRepository
from ode.services.result import fail, ok


async def clarify_goal(text: str, *, opp_id: str | None = None, save: bool = False) -> dict:
    from ode.heuristics.dbs import clarify_goal as _clarify_goal

    result = _clarify_goal(text).to_dict()
    saved_record = None
    opportunity = _load_optional_opportunity(opp_id)
    if opp_id and not opportunity:
        return fail(f"Opportunity not found: {opp_id}")
    if save:
        if not opportunity:
            return fail("Provide --opp-id when using --save")
        saved_record = append_dbs_diagnostic(opportunity, "goal_clarification", result)

    return ok({
        "result": result,
        "opportunity_id": opportunity.id if opportunity else "",
        "saved": bool(saved_record),
        "diagnostic_id": saved_record.get("id", "") if saved_record else "",
    }, message=result.get("next_action", ""))


async def deconstruct_concept(text: str, *, opp_id: str | None = None, save: bool = False) -> dict:
    from ode.heuristics.dbs import deconstruct_concept as _deconstruct_concept

    result = _deconstruct_concept(text).to_dict()
    saved_record = None
    opportunity = _load_optional_opportunity(opp_id)
    if opp_id and not opportunity:
        return fail(f"Opportunity not found: {opp_id}")
    if save:
        if not opportunity:
            return fail("Provide --opp-id when using --save")
        saved_record = append_dbs_diagnostic(opportunity, "concept_deconstruction", result)

    return ok({
        "result": result,
        "opportunity_id": opportunity.id if opportunity else "",
        "saved": bool(saved_record),
        "diagnostic_id": saved_record.get("id", "") if saved_record else "",
    }, message=result.get("next_action", ""))


async def diagnose_business(opp_id: str, *, facts: dict | None = None, save: bool = False) -> dict:
    from ode.heuristics.dbs import diagnose_business as _diagnose_business

    opportunity = OpportunityRepository().get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    result = _diagnose_business(opportunity.to_dict(), facts=facts or {}).to_dict()
    saved_record = append_dbs_diagnostic(opportunity, "business_diagnosis", result) if save else None

    return ok({
        "result": result,
        "opportunity_id": opportunity.id,
        "saved": bool(saved_record),
        "diagnostic_id": saved_record.get("id", "") if saved_record else "",
    }, message=result.get("tomorrow_action", ""))


async def run_dbs_session(text: str, *, opp_id: str | None = None,
                          facts: dict | None = None,
                          save: bool = False) -> dict:
    from ode.heuristics.dbs import run_dbs_session as _run_dbs_session

    opportunity = _load_optional_opportunity(opp_id)
    if opp_id and not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    result = _run_dbs_session(
        text,
        opportunity=opportunity.to_dict() if opportunity else None,
        facts=facts or None,
    ).to_dict()
    saved_record = None
    if save:
        if not opportunity:
            return fail("Provide --opp-id when using --save")
        saved_record = append_dbs_diagnostic(opportunity, "dbs_session", result)

    return ok({
        "result": result,
        "opportunity_id": opportunity.id if opportunity else "",
        "saved": bool(saved_record),
        "diagnostic_id": saved_record.get("id", "") if saved_record else "",
    }, message=result.get("next_action", ""))


async def build_ai_hardware_workflow(*, region: str = "shenzhen",
                                     team: str = "solo_or_2_3_person_team") -> dict:
    from ode.heuristics.ai_hardware_workflow import (
        build_ai_hardware_workflow as _build_workflow,
        format_ai_hardware_workflow,
    )

    workflow = _build_workflow(region=region, team=team)
    return ok({
        "workflow": workflow.to_dict(),
        "formatted": format_ai_hardware_workflow(workflow),
    }, message="AI hardware DBS workflow generated")


def append_dbs_diagnostic(opportunity, diagnostic_type: str, result: dict) -> dict:
    from ode.core.models import _new_id, _now_iso

    record = {
        "id": _new_id("diag-"),
        "source": "dbs_lens_v1",
        "type": diagnostic_type,
        "created_at": _now_iso(),
        "result": result,
    }
    if not hasattr(opportunity, "diagnostics") or opportunity.diagnostics is None:
        opportunity.diagnostics = []
    opportunity.diagnostics.append(record)
    opportunity.updated_at = _now_iso()
    OpportunityRepository().save(opportunity)
    return record


def _load_optional_opportunity(opp_id: str | None):
    return OpportunityRepository().get(opp_id) if opp_id else None
