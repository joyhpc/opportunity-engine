"""Insight, fit lens, experiment, actuals, and gate refresh services."""

from __future__ import annotations

from collections import Counter

from ode.core.repository import OpportunityRepository
from ode.services.result import fail, ok


async def get_insights(opp_id: str) -> dict:
    from ode.heuristics.bridge import quick_assess
    from ode.heuristics.dbs import latest_diagnostic
    from ode.heuristics.explore import classify_demand_pattern
    from ode.heuristics.reframe import generate_reframe
    from ode.heuristics.synthesize import synthesize

    repo = OpportunityRepository()
    opportunity = repo.get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    signals = repo.signals_for(opportunity.id)
    signal_dicts = [signal.to_dict() for signal in signals]
    opportunity_data = {
        "scores": opportunity.scores,
        "market": opportunity.market,
        "financials": opportunity.financials,
        "regulatory": opportunity.regulatory,
        "signals": signal_dicts,
        "gate_log": opportunity.gate_log,
        "stage": opportunity.stage,
        "domain": opportunity.domain,
        "experiments": getattr(opportunity, "experiments", []),
    }

    synthesis = synthesize(opportunity_data)

    assessment = None
    if opportunity.stage in ("SENSE", "SCREEN") and signal_dicts:
        assessment = quick_assess(signal_dicts, domain=opportunity.domain)

    demand_pattern = ""
    if signal_dicts:
        patterns = [classify_demand_pattern(signal) for signal in signal_dicts]
        pattern_counts = Counter(pattern for pattern in patterns if pattern != "unclassified")
        if pattern_counts:
            demand_pattern = pattern_counts.most_common(1)[0][0]

    reframe = None
    weighted_pct = opportunity.scores.get("_weighted_pct", 0) if opportunity.scores else 0
    if weighted_pct and weighted_pct < 70:
        verdict = "KILL" if weighted_pct < 50 else "MAYBE"
        weakest = ""
        dim_scores = {
            key: value
            for key, value in opportunity.scores.items()
            if not key.startswith("_") and not isinstance(value, (list, dict))
        }
        if dim_scores:
            weakest = min(dim_scores, key=lambda key: dim_scores[key])

        scoring_details = opportunity.scores.get("_scoring_details") if opportunity.scores else None
        reframe = generate_reframe(
            scores=opportunity.scores,
            verdict=verdict,
            weakest_dimension=weakest,
            scoring_details=scoring_details,
            domain=opportunity.domain,
            demand_pattern=demand_pattern,
        )

    return ok({
        "synthesis": synthesis,
        "quick_assess": assessment,
        "demand_pattern": demand_pattern,
        "reframe": reframe,
        "dbs": latest_diagnostic(opportunity.to_dict()),
    })


async def apply_lens(opp_id: str, *, profile: dict | None = None) -> dict:
    from ode.heuristics.fit_lens import FounderProfile, apply_fit_lens

    repo = OpportunityRepository()
    opportunity = repo.get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    founder = FounderProfile.from_dict(profile)
    signals = [signal.to_dict() for signal in repo.signals_for(opportunity.id)]
    result = apply_fit_lens(
        opportunity=opportunity.to_dict(),
        signals=signals,
        profile=founder,
    )

    return ok({
        "opportunity_id": opportunity.id,
        "opportunity_name": opportunity.name,
        "profile": founder.to_dict(),
        "lens": result.to_dict(),
    }, message=f"Lens recommendation: {result.recommendation}")


async def add_experiment(opp_id: str, *, version: str, description: str = "",
                         cogs: float | None = None, outcome: str = "partial",
                         metrics: dict | None = None, result: str = "") -> dict:
    from ode.core.models import _now_iso

    repo = OpportunityRepository()
    opportunity = repo.get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    entry = {
        "version": version,
        "description": description,
        "cogs": cogs,
        "outcome": outcome,
        "result": result,
        "metrics": metrics or {},
        "ts": _now_iso(),
    }
    if not hasattr(opportunity, "experiments") or opportunity.experiments is None:
        opportunity.experiments = []
    opportunity.experiments.append(entry)
    opportunity.updated_at = _now_iso()

    if cogs is not None and outcome == "pass":
        opportunity.financials.setdefault("actuals", {})["cogs_per_unit"] = cogs
        opportunity.financials["actuals"]["recorded_at"] = _now_iso()

    repo.save(opportunity)
    return ok({
        "version": version,
        "outcome": outcome,
        "experiment_count": len(opportunity.experiments),
    }, message=f"Experiment {version} recorded ({outcome})")


async def record_actuals(opp_id: str, *, cogs: float | None = None,
                         arpu: float | None = None, units_sold: int | None = None,
                         notes: str = "") -> dict:
    from ode.core.models import _now_iso

    repo = OpportunityRepository()
    opportunity = repo.get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    actuals = opportunity.financials.setdefault("actuals", {})
    if cogs is not None:
        actuals["cogs_per_unit"] = cogs
        estimate = opportunity.financials.get("cogs_per_unit_estimated")
        if estimate and estimate > 0:
            actuals["cogs_variance_pct"] = round((cogs - estimate) / estimate * 100, 1)
    if arpu is not None:
        actuals["arpu_actual"] = arpu
    if units_sold is not None:
        actuals["units_sold"] = units_sold
    actuals["notes"] = notes
    actuals["recorded_at"] = _now_iso()
    opportunity.updated_at = _now_iso()
    repo.save(opportunity)

    return ok({"actuals": actuals}, message="Actuals recorded")


async def refresh_gate(opp_id: str) -> dict:
    from ode.core.models import _now_iso
    from ode.engine.gate import evaluate_gate

    repo = OpportunityRepository()
    opportunity = repo.get(opp_id)
    if not opportunity:
        return fail(f"Opportunity not found: {opp_id}")

    last_verdict = opportunity.gate_log[-1]["verdict"] if opportunity.gate_log else None
    experiments = getattr(opportunity, "experiments", [])
    passed_experiments = [experiment for experiment in experiments if experiment.get("outcome") == "pass"]

    if opportunity.stage == "SCREEN" and opportunity.scores:
        scoring_dict = {
            "percentage": opportunity.scores.get("_weighted_pct", 0),
            "redline_violations": [],
        }
        result = evaluate_gate("SCREEN", scoring_result=scoring_dict)

        if passed_experiments and result["verdict"] == "MAYBE":
            percentage = scoring_dict["percentage"]
            if percentage >= 45:
                result["verdict"] = "GO"
                result["detail"] = (
                    f"{len(passed_experiments)} prototype(s) passed; "
                    f"overriding borderline score ({percentage:.0f}/100)"
                )
    elif opportunity.stage == "ANALYZE":
        result = evaluate_gate(
            "ANALYZE",
            financials=opportunity.financials,
            regulatory=opportunity.regulatory,
        )
    else:
        result = {
            "gate": opportunity.stage,
            "verdict": "UNKNOWN",
            "detail": "No re-evaluation rule for this stage",
        }

    verdict_changed = result.get("verdict") != last_verdict
    if verdict_changed and result["verdict"] in ("GO", "MAYBE", "KILL"):
        opportunity.gate_log.append({
            "gate": opportunity.stage,
            "verdict": result["verdict"],
            "score": result.get("score", 0),
            "ts": _now_iso(),
            "trigger": "manual_refresh",
        })
        opportunity.updated_at = _now_iso()
        repo.save(opportunity)

    message = (
        f"Gate: {last_verdict} -> {result['verdict']}"
        if verdict_changed
        else f"Gate unchanged: {result['verdict']}"
    )
    return ok({
        "new_verdict": result["verdict"],
        "previous_verdict": last_verdict,
        "verdict_changed": verdict_changed,
        "detail": result.get("detail", ""),
        "passed_experiments": len(passed_experiments),
    }, message=message)
