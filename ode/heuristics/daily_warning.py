"""Daily opportunity warning heuristics.

The daily warning layer is intentionally conservative about side effects.  It
normalizes outputs from existing discovery workflows, compares them with the
previous watchlist state, and returns a new auditable state plus a report.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from ode.core.constants import EVIDENCE_GRADE_STRENGTH as GRADE_STRENGTH


NEW_SPARK = "New Spark"
WATCH = "Watch"
VALIDATE_SOON = "Validate Soon"
ACT_NOW = "Act Now"

ACTIVE_LABELS = [NEW_SPARK, WATCH, VALIDATE_SOON, ACT_NOW]
STALE_AFTER_DAYS = 3

STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "around",
    "build",
    "could",
    "from",
    "into",
    "looking",
    "need",
    "needs",
    "new",
    "that",
    "this",
    "tool",
    "tools",
    "using",
    "with",
    "would",
}


def today_key(value: str | None = None) -> str:
    """Return a YYYY-MM-DD key for a supplied value or today."""

    if value:
        return value[:10]
    return date.today().isoformat()


def empty_watchlist() -> dict[str, Any]:
    """Return an empty watchlist state."""

    return {
        "schema_version": "1.0",
        "updated_at": "",
        "items": {},
    }


def normalize_daily_inputs(
    *,
    pain_result: dict[str, Any] | None = None,
    revenue_cases: list[dict[str, Any]] | None = None,
    explore_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Normalize pain, revenue, and explore outputs into warning candidates."""

    candidates: list[dict[str, Any]] = []

    pain_result = pain_result or {}
    for signal in pain_result.get("all_signals") or pain_result.get("top_signals") or []:
        candidates.append(_candidate_from_pain(signal))

    for analysis in revenue_cases or []:
        candidates.append(_candidate_from_revenue_case(analysis))

    explore_result = explore_result or {}
    for hypothesis in explore_result.get("hypotheses") or []:
        candidates.append(_candidate_from_hypothesis(hypothesis))

    return merge_candidates([candidate for candidate in candidates if candidate])


def merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate candidates by topic and combine source/evidence fields."""

    merged: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        topic_key = candidate.get("topic_key") or _topic_key(candidate.get("title", ""))
        alert_id = _alert_id(topic_key)
        item = merged.setdefault(alert_id, {
            "id": alert_id,
            "topic_key": topic_key,
            "title": candidate.get("title", topic_key),
            "summary": candidate.get("summary", ""),
            "candidate_types": [],
            "tags": [],
            "source_ids": [],
            "source_titles": [],
            "source_diversity": 0,
            "best_grade": "E",
            "priority": 0.0,
            "founder_fit": 0.0,
            "risk_flags": [],
            "case_ids": [],
            "archetypes": [],
            "suitabilities": [],
            "case_roles": [],
            "evidence_independence": "",
            "composite_components": {},
            "evidence_refs": [],
            "reasons": [],
            "next_actions": [],
            "metrics": {},
        })
        item["candidate_types"] = _unique(item["candidate_types"] + candidate.get("candidate_types", []))
        item["tags"] = _unique(item["tags"] + candidate.get("tags", []))
        item["source_ids"] = _unique(item["source_ids"] + candidate.get("source_ids", []))
        item["source_titles"] = _unique(item["source_titles"] + candidate.get("source_titles", []))
        item["risk_flags"] = _unique(item["risk_flags"] + candidate.get("risk_flags", []))
        item["case_ids"] = _unique(item["case_ids"] + candidate.get("case_ids", []))
        item["archetypes"] = _unique(item["archetypes"] + candidate.get("archetypes", []))
        item["suitabilities"] = _unique(item["suitabilities"] + candidate.get("suitabilities", []))
        item["case_roles"] = _unique(item["case_roles"] + candidate.get("case_roles", []))
        item["evidence_refs"] = _unique_dicts(item["evidence_refs"] + candidate.get("evidence_refs", []))
        item["reasons"] = _unique(item["reasons"] + candidate.get("reasons", []))
        item["next_actions"] = _unique(item["next_actions"] + candidate.get("next_actions", []))
        item["best_grade"] = _best_grade(item["best_grade"], candidate.get("best_grade", "E"))
        item["priority"] = max(float(item["priority"]), float(candidate.get("priority", 0) or 0))
        item["founder_fit"] = max(float(item["founder_fit"]), float(candidate.get("founder_fit", 0) or 0))
        item["source_diversity"] = len({source for source in item["source_ids"] if source})
        item["evidence_independence"] = _strongest_independence(
            item.get("evidence_independence", ""),
            candidate.get("evidence_independence", ""),
        )
        item["composite_components"].update(candidate.get("composite_components", {}))
        item["metrics"].update(candidate.get("metrics", {}))

    return sorted(
        merged.values(),
        key=lambda item: (
            -_status_rank(_initial_status(item)),
            -float(item.get("priority", 0) or 0),
            item.get("title", ""),
        ),
    )


def update_watchlist(
    previous_state: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    *,
    run_date: str | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Compare today's candidates with prior state and return alerts + state."""

    day = today_key(run_date)
    state = previous_state or empty_watchlist()
    previous_items = dict(state.get("items") or {})
    next_items: dict[str, dict[str, Any]] = {}
    alerts: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for candidate in candidates:
        alert_id = candidate["id"]
        seen_ids.add(alert_id)
        previous = previous_items.get(alert_id)
        item = _merge_state_item(previous, candidate, day)
        evaluation = evaluate_alert_level(candidate, previous_item=previous, state_item=item)
        status = evaluation["status"]
        item["status"] = status
        item["why"] = evaluation["why"]
        item["gates_applied"] = evaluation["gates_applied"]
        item["lifecycle"] = "active"
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
        next_items[alert_id] = item

        alert = {
            **candidate,
            "status": status,
            "first_seen": item["first_seen"],
            "last_seen": item["last_seen"],
            "days_seen": item["days_seen"],
            "priority_delta": item["priority_delta"],
            "previous_status": previous.get("status") if previous else "",
            "lifecycle": item["lifecycle"],
            "why": evaluation["why"],
            "gates_applied": evaluation["gates_applied"],
        }
        alerts.append(alert)
        updates.append({
            "id": alert_id,
            "title": item["title"],
            "change": _change_label(previous, item),
            "status": status,
            "priority_delta": item["priority_delta"],
        })

    for alert_id, previous in previous_items.items():
        if alert_id in seen_ids:
            continue
        item = dict(previous)
        item["absent_days"] = int(item.get("absent_days", 0) or 0) + 1
        item["lifecycle"] = "stale" if item["absent_days"] >= stale_after_days else "missing"
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
        next_items[alert_id] = item
        updates.append({
            "id": alert_id,
            "title": item.get("title", alert_id),
            "change": item["lifecycle"],
            "status": item.get("status", WATCH),
            "priority_delta": 0,
        })

    alerts.sort(key=lambda item: (
        -_status_rank(item.get("status", NEW_SPARK)),
        -float(item.get("priority", 0) or 0),
        item.get("title", ""),
    ))

    new_state = {
        "schema_version": state.get("schema_version", "1.0"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "items": dict(sorted(next_items.items())),
    }
    return {
        "alerts": alerts,
        "watchlist_updates": updates,
        "state": new_state,
        "run_date": day,
    }


def build_initial_warning_system(
    previous_state: dict[str, Any] | None,
    revenue_cases: list[dict[str, Any]],
    *,
    profile: dict[str, Any] | None = None,
    run_date: str | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    """Create initial warning state and case-derived priors from revenue cases."""

    base_state = empty_watchlist() if reset else (previous_state or empty_watchlist())
    candidates = normalize_daily_inputs(revenue_cases=revenue_cases)
    warning_result = update_watchlist(base_state, candidates, run_date=run_date)
    priors = learn_case_priors(revenue_cases)
    return {
        **warning_result,
        "priors": priors,
        "case_count": len(revenue_cases),
        "candidate_count": len(candidates),
        "profile": profile or {},
        "reset": reset,
    }


def learn_case_priors(revenue_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Learn reusable warning priors from analyzed revenue cases."""

    groups: dict[str, dict[str, Any]] = {}
    for analysis in revenue_cases:
        case = analysis.get("case", {})
        tags = [str(tag) for tag in case.get("fit_tags", []) if tag]
        category = str(case.get("category") or "uncategorized")
        archetype = str(analysis.get("archetype") or case.get("archetype") or _infer_case_archetype_from_analysis(analysis))
        pattern = archetype or _case_pattern_name(category, tags)
        prior_id = f"prior-{hashlib.sha1(pattern.lower().encode('utf-8')).hexdigest()[:10]}"
        group = groups.setdefault(prior_id, {
            "id": prior_id,
            "pattern": pattern,
            "case_count": 0,
            "case_names": [],
            "categories": [],
            "common_tags": [],
            "risk_flags": [],
            "case_roles": [],
            "suitabilities": [],
            "evidence_independence": [],
            "archetype": archetype,
            "best_grade": "E",
            "_founder_fit": [],
            "_entry_fit": [],
            "_quiet_money": [],
            "_confidence": [],
        })
        group["case_count"] += 1
        group["case_names"].append(case.get("name", "Untitled case"))
        group["categories"].append(category)
        group["common_tags"].extend(tags)
        group["risk_flags"].extend(case.get("risk_flags", []))
        group["case_roles"].append(analysis.get("case_role", ""))
        group["suitabilities"].append(analysis.get("suitability", ""))
        group["evidence_independence"].append(analysis.get("evidence_independence", ""))
        group["best_grade"] = _best_grade(group["best_grade"], analysis.get("evidence_grade", "E"))
        group["_founder_fit"].append(float(analysis.get("founder_fit", 0) or 0))
        group["_entry_fit"].append(float(analysis.get("entry_fit", 0) or 0))
        group["_quiet_money"].append(float(analysis.get("quiet_money_score", 0) or 0))
        group["_confidence"].append(float(analysis.get("confidence", 0) or 0))

    priors = []
    for group in groups.values():
        common_tags = [tag for tag, _ in Counter(group["common_tags"]).most_common(6)]
        risk_flags = [flag for flag, _ in Counter(group["risk_flags"]).most_common(5)]
        prior = {
            "id": group["id"],
            "pattern": group["pattern"],
            "case_count": group["case_count"],
            "case_names": _unique(group["case_names"]),
            "categories": _unique(group["categories"]),
            "common_tags": common_tags,
            "risk_flags": risk_flags,
            "case_roles": _unique(group["case_roles"]),
            "suitabilities": _unique(group["suitabilities"]),
            "evidence_independence": _unique(group["evidence_independence"]),
            "archetype": group["archetype"],
            "best_grade": group["best_grade"],
            "avg_founder_fit": _avg(group["_founder_fit"]),
            "avg_entry_fit": _avg(group["_entry_fit"]),
            "avg_quiet_money_score": _avg(group["_quiet_money"]),
            "avg_confidence": _avg(group["_confidence"]),
        }
        prior["status_bias"] = _prior_status_bias(prior)
        prior["warning_triggers"] = _prior_warning_triggers(prior)
        prior["default_action"] = _prior_default_action(prior)
        priors.append(prior)

    return sorted(
        priors,
        key=lambda item: (
            -_status_rank(item["status_bias"]),
            -item["avg_quiet_money_score"],
            -item["avg_entry_fit"],
            item["pattern"],
        ),
    )


def classify_alert(
    candidate: dict[str, Any],
    *,
    previous_item: dict[str, Any] | None = None,
    state_item: dict[str, Any] | None = None,
) -> str:
    """Classify a warning candidate into the fixed daily alert levels."""

    return evaluate_alert_level(
        candidate,
        previous_item=previous_item,
        state_item=state_item,
    )["status"]


def evaluate_alert_level(
    candidate: dict[str, Any],
    *,
    previous_item: dict[str, Any] | None = None,
    state_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify a candidate and return structured explanation metadata."""

    source_ids = {source for source in candidate.get("source_ids", []) if source}
    only_product_hunt = source_ids == {"producthunt_feed"}
    candidate_types = set(candidate.get("candidate_types", []))
    grade = candidate.get("best_grade", "E")
    grade_strength = GRADE_STRENGTH.get(grade, 1)
    founder_fit = float(candidate.get("founder_fit", 0) or 0)
    priority = float(candidate.get("priority", 0) or 0)
    source_diversity = int(candidate.get("source_diversity", 0) or len(source_ids))
    days_seen = int((state_item or {}).get("days_seen", 1) or 1)
    priority_delta = float((state_item or {}).get("priority_delta", 0) or 0)
    suitability = _first(candidate.get("suitabilities", [])) or str(candidate.get("suitability", ""))
    case_role = _first(candidate.get("case_roles", [])) or str(candidate.get("case_role", ""))
    evidence_independence = candidate.get("evidence_independence", "")
    archetypes = set(candidate.get("archetypes", []))
    risk_flags = set(candidate.get("risk_flags", []))
    entry_fit = float(candidate.get("metrics", {}).get("entry_fit", 0) or 0)
    gates: list[str] = []

    previous_grade = (previous_item or {}).get("best_grade", "E")
    grade_upgraded = grade_strength > GRADE_STRENGTH.get(previous_grade, 1)
    status_upgraded = previous_item and (
        grade_upgraded or priority_delta >= 15 or source_diversity > int(previous_item.get("source_diversity", 0) or 0)
    )

    status = NEW_SPARK
    if (
        previous_item
        and status_upgraded
        and founder_fit >= 70
        and (grade_strength >= GRADE_STRENGTH["B"] or priority >= 82)
        and not only_product_hunt
    ):
        status = ACT_NOW

    if status != ACT_NOW and not only_product_hunt:
        if "revenue_case" in candidate_types and grade_strength >= GRADE_STRENGTH["B"]:
            status = VALIDATE_SOON
        if "pain_signal" in candidate_types and grade_strength >= GRADE_STRENGTH["C"]:
            status = VALIDATE_SOON
        if priority >= 84 and founder_fit >= 70 and source_diversity >= 2:
            status = VALIDATE_SOON

    if status == NEW_SPARK and (days_seen >= 2 or source_diversity >= 2 or priority >= 65):
        status = WATCH

    if only_product_hunt:
        status = _cap_status(status, WATCH)
        gates.append("product_hunt_solution_proxy_cap")
    if evidence_independence in {"single_ultimate", "media_only"} and "revenue_case" in candidate_types:
        status = _cap_status(status, WATCH)
        gates.append(f"verifiability_cap:{evidence_independence}")
    if suitability in {"Market Map", "Watchlist", "Verify First"}:
        status = _cap_status(status, WATCH)
        gates.append(f"suitability_cap:{suitability}")
    if archetypes & {"public_pr_mega_arr", "incumbent_market_map"}:
        status = _cap_status(status, WATCH)
        gates.append("archetype_cap:market_map_or_pr_arr")
    if case_role == "market_map":
        status = _cap_status(status, WATCH)
        gates.append("market_map_cap")
    if "heavy_capital" in risk_flags and entry_fit < 62:
        status = _cap_status(status, WATCH)
        gates.append("risk_cap:heavy_capital_low_entry_fit")
    if "enterprise_procurement" in risk_flags and entry_fit < 62:
        status = _cap_status(status, WATCH)
        gates.append("risk_cap:enterprise_procurement_slow_validation")

    why = _explain_alert(candidate, status, gates)
    return {"status": status, "gates_applied": gates, "why": why}


def format_daily_report(
    result: dict[str, Any],
    *,
    source_events: list[dict[str, Any]] | None = None,
    portfolio: list[dict[str, Any]] | None = None,
) -> str:
    """Format a daily warning report."""

    alerts = result.get("alerts", [])
    updates = result.get("watchlist_updates", [])
    source_events = source_events or []
    portfolio = portfolio or []
    counts = Counter(alert.get("status", NEW_SPARK) for alert in alerts)

    lines = [
        "# Daily Opportunity Warning Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Run date: {result.get('run_date', today_key())}",
        "",
        "## Alert Summary",
        "",
        "| Level | Count |",
        "|-------|-------|",
    ]
    for label in ACTIVE_LABELS:
        lines.append(f"| {label} | {counts.get(label, 0)} |")
    lines.append("")

    if alerts:
        lines.extend([
            "## Alerts",
            "",
            "| Level | Topic | Evidence | Fit | Sources | Delta | Why |",
            "|-------|-------|----------|-----|---------|-------|-----|",
        ])
        for alert in alerts:
            why = alert.get("why", {})
            lines.append(
                f"| {alert.get('status', NEW_SPARK)} | "
                f"{_cell(alert.get('title', ''))} | "
                f"{alert.get('best_grade', 'E')} | "
                f"{float(alert.get('founder_fit', 0) or 0):.1f} | "
                f"{alert.get('source_diversity', 0)} | "
                f"{float(alert.get('priority_delta', 0) or 0):+.1f} | "
                f"{_cell(why.get('level_reason') or _first(alert.get('reasons', [])))} |"
            )
        lines.append("")

        lines.extend(["### Evidence Gaps And Next Validation", ""])
        for alert in alerts[:8]:
            why = alert.get("why", {})
            gaps = "; ".join(why.get("evidence_gaps", [])) or "No major gap recorded."
            validation = why.get("next_validation") or _first(alert.get("next_actions", []))
            lines.extend([
                f"**{alert.get('title', '')}**",
                f"- Gaps: {gaps}",
                f"- Next validation: {validation}",
            ])
        lines.append("")
    else:
        lines.extend(["## Alerts", "", "No active alerts today.", ""])

    if updates:
        lines.extend([
            "## Watchlist Updates",
            "",
            "| Change | Status | Topic | Delta |",
            "|--------|--------|-------|-------|",
        ])
        for update in updates:
            lines.append(
                f"| {update.get('change', '')} | "
                f"{update.get('status', '')} | "
                f"{_cell(update.get('title', ''))} | "
                f"{float(update.get('priority_delta', 0) or 0):+.1f} |"
            )
        lines.append("")

    if portfolio:
        lines.extend([
            "## Portfolio Snapshot",
            "",
            "| Opportunity | Stage | Score | Signals | Status |",
            "|-------------|-------|-------|---------|--------|",
        ])
        for item in portfolio[:8]:
            lines.append(
                f"| {_cell(item.get('name', ''))} | {item.get('stage', '')} | "
                f"{float(item.get('score', 0) or 0):.1f} | "
                f"{item.get('signal_count', 0)} | {item.get('status', '')} |"
            )
        lines.append("")

    if source_events:
        lines.extend(["## Source Events", ""])
        for event in source_events:
            source = event.get("source_id", "unknown")
            status = event.get("status", "")
            detail = event.get("reason") or event.get("error") or event.get("count", "")
            lines.append(f"- {source}: {status} {detail}".rstrip())

    return "\n".join(lines)


def format_initial_warning_report(result: dict[str, Any]) -> str:
    """Format the initial warning-system bootstrap report."""

    priors = result.get("priors", [])
    alerts = result.get("alerts", [])
    lines = [
        "# Initial Opportunity Warning System",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Run date: {result.get('run_date', today_key())}",
        "",
        "## Learning Summary",
        "",
        f"- Cases learned: {result.get('case_count', 0)}",
        f"- Case-derived warning candidates: {result.get('candidate_count', 0)}",
        f"- Learned priors: {len(priors)}",
        f"- Initial active alerts: {len(alerts)}",
        "",
    ]

    if priors:
        lines.extend([
            "## Learned Priors",
            "",
            "| Bias | Pattern | Cases | Best Grade | Entry Fit | Quiet Money | Triggers |",
            "|------|---------|-------|------------|-----------|-------------|----------|",
        ])
        for prior in priors:
            lines.append(
                f"| {prior['status_bias']} | {_cell(prior['pattern'])} | "
                f"{prior['case_count']} | {prior['best_grade']} | "
                f"{prior['avg_entry_fit']:.1f} | {prior['avg_quiet_money_score']:.1f} | "
                f"{_cell('; '.join(prior['warning_triggers'][:2]))} |"
            )
        lines.append("")

    if alerts:
        lines.extend([
            "## Initial Watchlist",
            "",
            "| Level | Topic | Evidence | Composite | Fit | Sources | Next Action |",
            "|-------|-------|----------|-----------|-----|---------|-------------|",
        ])
        for alert in alerts:
            lines.append(
                f"| {alert.get('status', NEW_SPARK)} | {_cell(alert.get('title', ''))} | "
                f"{alert.get('best_grade', 'E')} | "
                f"{float(alert.get('priority', 0) or 0):.1f} | "
                f"{float(alert.get('founder_fit', 0) or 0):.1f} | "
                f"{alert.get('source_diversity', 0)} | "
                f"{_cell((alert.get('why') or {}).get('next_validation') or _first(alert.get('next_actions', [])))} |"
            )
        lines.append("")

    lines.extend([
        "## Operating Rule",
        "",
        "This bootstrap does not create or advance opportunities automatically. It seeds the warning state and priors so daily reviews can detect upgrades, repeats, and missing evidence against an initial case-informed baseline.",
    ])
    return "\n".join(lines)


def _candidate_from_pain(signal: dict[str, Any]) -> dict[str, Any]:
    title = str(signal.get("title") or "Untitled pain signal")
    tags = [str(tag) for tag in signal.get("tags", [])]
    source_id = str(signal.get("source_id") or signal.get("source") or "pain_signal")
    grade = str(signal.get("evidence_grade") or "E").upper()
    priority = float(signal.get("priority_score", signal.get("pain_score", 0)) or 0)
    founder_fit = float(signal.get("founder_fit", 0) or 0)
    topic_key = _topic_key(" ".join(tags) or title)
    reasons = list(signal.get("reasons") or [])
    if not reasons:
        reasons = [f"Pain signal grade {grade} from {source_id}."]
    return {
        "topic_key": topic_key,
        "title": title,
        "summary": signal.get("snippet", ""),
        "candidate_types": ["pain_signal"],
        "tags": tags,
        "source_ids": [source_id],
        "source_titles": [signal.get("source", source_id)],
        "source_diversity": 1,
        "best_grade": grade,
        "priority": priority,
        "founder_fit": founder_fit,
        "risk_flags": [],
        "case_ids": [],
        "archetypes": [],
        "suitabilities": [],
        "case_roles": [],
        "evidence_independence": "",
        "composite_components": {"pain_priority": priority, "founder_fit": founder_fit},
        "evidence_refs": [{
            "type": "pain_signal",
            "title": title,
            "url": signal.get("url", ""),
            "source_id": source_id,
            "grade": grade,
        }],
        "reasons": reasons,
        "next_actions": list(signal.get("next_actions") or []),
        "metrics": {
            "pain_score": signal.get("pain_score", 0),
            "cluster_size": signal.get("cluster_size", 1),
        },
    }


def _candidate_from_revenue_case(analysis: dict[str, Any]) -> dict[str, Any]:
    case = analysis.get("case", {})
    title = str(case.get("name") or "Untitled revenue case")
    tags = [str(tag) for tag in case.get("fit_tags", [])]
    grade = str(analysis.get("evidence_grade") or "E").upper()
    source_ids = [str(item) for item in case.get("source_ids", [])]
    if not source_ids:
        source_ids = [
            str(item.get("source_name") or item.get("type") or "revenue_case")
            for item in case.get("evidence", [])
            if isinstance(item, dict)
        ] or ["revenue_case"]
    composite = _revenue_composite(analysis)
    priority = composite["score"]
    founder_fit = float(analysis.get("founder_fit", 0) or 0)
    topic_key = _topic_key(" ".join(tags) or f"{case.get('category', '')} {title}")
    archetype = str(analysis.get("archetype") or case.get("archetype") or _infer_case_archetype_from_analysis(analysis))
    evidence_independence = str(
        analysis.get("evidence_independence")
        or _infer_evidence_independence(case)
    )
    suitability = str(analysis.get("suitability", ""))
    case_role = str(analysis.get("case_role", ""))
    return {
        "topic_key": topic_key,
        "title": title,
        "summary": case.get("claim", ""),
        "candidate_types": ["revenue_case"],
        "tags": tags + [str(case.get("category", ""))],
        "source_ids": source_ids,
        "source_titles": source_ids,
        "source_diversity": len(set(source_ids)),
        "best_grade": grade,
        "priority": priority,
        "founder_fit": founder_fit,
        "risk_flags": list(case.get("risk_flags", [])),
        "case_ids": [str(case.get("id", ""))],
        "archetypes": [archetype],
        "suitabilities": [suitability] if suitability else [],
        "case_roles": [case_role] if case_role else [],
        "evidence_independence": evidence_independence,
        "composite_components": composite,
        "evidence_refs": [{
            "type": "revenue_case",
            "title": title,
            "url": _first_url(case.get("evidence", [])),
            "source_id": ",".join(source_ids),
            "grade": grade,
        }],
        "reasons": [
            f"Revenue evidence grade {grade}; suitability {suitability or 'unknown'}; archetype {archetype}."
        ],
        "next_actions": list(analysis.get("next_actions") or []),
        "metrics": {
            "confidence": analysis.get("confidence", 0),
            "entry_fit": analysis.get("entry_fit", 0),
            "quiet_money_score": analysis.get("quiet_money_score", 0),
            "suitability": suitability,
            "case_role": case_role,
            "revenue_quality": analysis.get("revenue_quality", ""),
        },
    }


def _candidate_from_hypothesis(hypothesis: dict[str, Any]) -> dict[str, Any]:
    title = str(hypothesis.get("hypothesis") or "Untitled opportunity hypothesis")
    themes = [str(theme) for theme in hypothesis.get("themes", [])]
    sources = [str(source) for source in hypothesis.get("sources", [])] or ["explore"]
    confidence = float(hypothesis.get("confidence", 0) or 0)
    priority = min(confidence * 10, 100)
    topic_key = _topic_key(" ".join(themes) or title)
    return {
        "topic_key": topic_key,
        "title": title,
        "summary": "",
        "candidate_types": ["explore_hypothesis"],
        "tags": themes + [str(hypothesis.get("domain", ""))],
        "source_ids": sources,
        "source_titles": sources,
        "source_diversity": len(set(sources)),
        "best_grade": "E",
        "priority": priority,
        "founder_fit": 0.0,
        "risk_flags": [],
        "case_ids": [],
        "archetypes": ["explore_hypothesis"],
        "suitabilities": [],
        "case_roles": [],
        "evidence_independence": "",
        "composite_components": {"confidence": confidence, "score": priority},
        "evidence_refs": [{
            "type": "explore_hypothesis",
            "title": title,
            "url": "",
            "source_id": ",".join(sources),
            "grade": "E",
        }],
        "reasons": [f"Exploration hypothesis confidence {confidence:.1f}/10."],
        "next_actions": list(hypothesis.get("next_steps") or []),
        "metrics": {
            "confidence": confidence,
            "signal_count": hypothesis.get("signal_count", 0),
        },
    }


def _merge_state_item(previous: dict[str, Any] | None, candidate: dict[str, Any], day: str) -> dict[str, Any]:
    previous = previous or {}
    previous_priority = float(previous.get("priority", 0) or 0)
    priority = round(float(candidate.get("priority", 0) or 0), 1)
    previous_last_seen = previous.get("last_seen")
    days_seen = int(previous.get("days_seen", 0) or 0)
    if previous_last_seen != day:
        days_seen += 1
    if not days_seen:
        days_seen = 1

    return {
        "id": candidate["id"],
        "topic_key": candidate.get("topic_key", ""),
        "title": candidate.get("title", previous.get("title", "")),
        "summary": candidate.get("summary", previous.get("summary", "")),
        "first_seen": previous.get("first_seen") or day,
        "last_seen": day,
        "days_seen": days_seen,
        "absent_days": 0,
        "candidate_types": _unique(previous.get("candidate_types", []) + candidate.get("candidate_types", [])),
        "tags": _unique(previous.get("tags", []) + candidate.get("tags", [])),
        "source_ids": _unique(previous.get("source_ids", []) + candidate.get("source_ids", [])),
        "risk_flags": _unique(previous.get("risk_flags", []) + candidate.get("risk_flags", [])),
        "case_ids": _unique(previous.get("case_ids", []) + candidate.get("case_ids", [])),
        "archetypes": _unique(previous.get("archetypes", []) + candidate.get("archetypes", [])),
        "suitabilities": _unique(previous.get("suitabilities", []) + candidate.get("suitabilities", [])),
        "case_roles": _unique(previous.get("case_roles", []) + candidate.get("case_roles", [])),
        "source_diversity": max(
            int(previous.get("source_diversity", 0) or 0),
            int(candidate.get("source_diversity", 0) or 0),
        ),
        "best_grade": _best_grade(previous.get("best_grade", "E"), candidate.get("best_grade", "E")),
        "evidence_independence": _strongest_independence(
            previous.get("evidence_independence", ""),
            candidate.get("evidence_independence", ""),
        ),
        "priority": priority,
        "previous_priority": previous_priority,
        "priority_delta": round(priority - previous_priority, 1),
        "founder_fit": max(float(previous.get("founder_fit", 0) or 0), float(candidate.get("founder_fit", 0) or 0)),
        "composite_components": candidate.get("composite_components", previous.get("composite_components", {})),
        "evidence_refs": _unique_dicts(previous.get("evidence_refs", []) + candidate.get("evidence_refs", []))[-12:],
        "last_reasons": candidate.get("reasons", []),
        "next_actions": candidate.get("next_actions", []),
        "why": previous.get("why", {}),
        "gates_applied": previous.get("gates_applied", []),
        "status": previous.get("status", NEW_SPARK),
        "lifecycle": "active",
    }


def _change_label(previous: dict[str, Any] | None, item: dict[str, Any]) -> str:
    if not previous:
        return "new"
    if item.get("status") != previous.get("status"):
        return "upgraded" if _status_rank(item.get("status", "")) > _status_rank(previous.get("status", "")) else "changed"
    if float(item.get("priority_delta", 0) or 0) >= 10:
        return "heated"
    return "seen"


def _initial_status(candidate: dict[str, Any]) -> str:
    return classify_alert(candidate, state_item={"days_seen": 1, "priority_delta": 0})


def _status_rank(status: str) -> int:
    return {NEW_SPARK: 1, WATCH: 2, VALIDATE_SOON: 3, ACT_NOW: 4}.get(status, 0)


def _case_pattern_name(category: str, tags: list[str]) -> str:
    useful_tags = [
        tag
        for tag in tags
        if tag.lower() not in {"software", "subscription", "china", "workflow"}
    ]
    if useful_tags:
        return useful_tags[0]
    return category


def _infer_case_archetype_from_analysis(analysis: dict[str, Any]) -> str:
    case = analysis.get("case", {})
    evidence = case.get("evidence", [])
    evidence_types = {
        item.get("type", "")
        for item in evidence
        if isinstance(item, dict)
    }
    text = " ".join([
        str(case.get("name", "")),
        str(case.get("category", "")),
        str(case.get("claim", "")),
        str(case.get("notes", "")),
        " ".join(str(tag) for tag in case.get("fit_tags", [])),
        " ".join(str(flag) for flag in case.get("risk_flags", [])),
    ]).lower()

    if analysis.get("suitability") == "Market Map" or analysis.get("case_role") == "market_map":
        return "incumbent_market_map"
    if evidence_types & {"signed_contract", "payment_receipt"}:
        if any(term in text for term in {"renewal", "repeat", "retention"}):
            return "renewal_repeat_payment"
        if any(term in text for term in {"indie", "micro", "solo", "bootstrap", "mrr"}):
            return "indie_micro_saas"
        return "quiet_b2b_paid_pilot"
    if float(case.get("amount", 0) or 0) >= 100_000_000 and "company_pr" in evidence_types:
        return "public_pr_mega_arr"
    return "revenue_case"


def _infer_evidence_independence(case: dict[str, Any]) -> str:
    evidence = case.get("evidence", [])
    evidence_types = {
        item.get("type", "")
        for item in evidence
        if isinstance(item, dict)
    }
    source_names = {
        str(item.get("source_name", "")).lower()
        for item in evidence
        if isinstance(item, dict) and item.get("source_name")
    }
    if evidence_types & {"signed_contract", "payment_receipt", "audited_financial", "public_filing", "exchange_disclosure"}:
        return "hard_independent"
    if "company_formal_disclosure" in evidence_types and len(source_names) >= 2:
        return "formal_independent"
    if "company_formal_disclosure" in evidence_types or "company_pr" in evidence_types:
        return "single_ultimate"
    if evidence_types:
        return "media_only"
    return ""


def _revenue_composite(analysis: dict[str, Any]) -> dict[str, Any]:
    grade = str(analysis.get("evidence_grade") or "E").upper()
    evidence = {
        "A": 100.0,
        "B": 82.0,
        "C": 62.0,
        "D": 40.0,
        "E": 18.0,
    }.get(grade, 18.0)
    founder_fit = float(analysis.get("founder_fit", 0) or 0)
    entry_fit = float(analysis.get("entry_fit", 0) or 0)
    quiet_money = float(analysis.get("quiet_money_score", 0) or 0)
    confidence = float(analysis.get("confidence", 0) or 0)
    case = analysis.get("case", {})
    risk_flags = set(case.get("risk_flags", []))
    risk_penalty = _risk_penalty(risk_flags, entry_fit)
    wildcard_bonus = 6.0 if analysis.get("protected_as_watchlist") else 0.0
    score = (
        evidence * 0.25
        + founder_fit * 0.20
        + entry_fit * 0.20
        + quiet_money * 0.20
        + confidence * 0.15
        - risk_penalty
        + wildcard_bonus
    )
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "evidence": round(evidence, 1),
        "founder_fit": round(founder_fit, 1),
        "entry_fit": round(entry_fit, 1),
        "quiet_money": round(quiet_money, 1),
        "confidence": round(confidence, 1),
        "risk_penalty": round(risk_penalty, 1),
        "wildcard_bonus": round(wildcard_bonus, 1),
    }


def _risk_penalty(risk_flags: set[str], entry_fit: float) -> float:
    penalties = {
        "heavy_capital": 18.0,
        "requires_inventory": 12.0,
        "enterprise_procurement": 10.0,
        "regulated": 10.0,
        "platform_dependency": 5.0,
        "crowded_market": 5.0,
        "human_operations": 4.0,
        "technical_complexity": 5.0,
        "data_dependency": 4.0,
        "low_margin": 6.0,
    }
    penalty = sum(penalties.get(flag, 0.0) for flag in risk_flags)
    if entry_fit >= 70:
        penalty *= 0.55
    elif entry_fit >= 58:
        penalty *= 0.75
    return min(penalty, 28.0)


def _cap_status(status: str, cap: str) -> str:
    return status if _status_rank(status) <= _status_rank(cap) else cap


def _explain_alert(candidate: dict[str, Any], status: str, gates: list[str]) -> dict[str, Any]:
    candidate_types = set(candidate.get("candidate_types", []))
    grade = candidate.get("best_grade", "E")
    composite = float(candidate.get("priority", 0) or 0)
    suitability = _first(candidate.get("suitabilities", [])) or str(candidate.get("metrics", {}).get("suitability", ""))
    evidence_independence = candidate.get("evidence_independence", "")
    archetype = _first(candidate.get("archetypes", []))
    gaps: list[str] = []

    if evidence_independence in {"single_ultimate", "media_only"}:
        gaps.append("Needs a second independent primary or hard-payment source.")
    if suitability in {"Market Map", "Verify First"}:
        gaps.append(f"Suitability is {suitability}; verify a smaller entry wedge before build commitment.")
    if "heavy_capital" in candidate.get("risk_flags", []):
        gaps.append("Heavy-capital risk means this should be treated as a market-map unless a software/service layer is found.")
    if "enterprise_procurement" in candidate.get("risk_flags", []):
        gaps.append("Enterprise procurement can exceed the 30-day validation window.")
    if "revenue_case" not in candidate_types and grade in {"D", "E"}:
        gaps.append("Evidence is still weak; look for payment or explicit buyer intent.")

    if status == ACT_NOW:
        reason = f"Evidence upgraded with high fit and composite score {composite:.1f}."
    elif status == VALIDATE_SOON:
        reason = f"{grade}-grade evidence with workable fit; composite score {composite:.1f}."
    elif status == WATCH:
        reason = f"Keep watching: {grade}-grade evidence, archetype {archetype or 'unknown'}, composite score {composite:.1f}."
    else:
        reason = f"New weak signal; preserve discovery value until repeat or stronger evidence appears."

    if gates:
        reason += f" Gates applied: {', '.join(gates)}."

    next_validation = _next_validation(candidate, status, gaps)
    return {
        "level_reason": reason,
        "evidence_gaps": gaps,
        "next_validation": next_validation,
    }


def _next_validation(candidate: dict[str, Any], status: str, gaps: list[str]) -> str:
    if gaps:
        first_gap = gaps[0]
        if "second independent" in first_gap:
            return "Find one non-PR primary proof: filing, contract, invoice, customer receipt, or merchant/order data."
        if "smaller entry wedge" in first_gap or "market-map" in first_gap:
            return "Map the proven budget pool, then search for an adjacent B/C-grade software or service wedge."
        if "Enterprise procurement" in first_gap:
            return "Find a buyer-side workflow that can be tested without a full enterprise procurement cycle."
    if status == VALIDATE_SOON:
        return "Interview 3 reachable buyers and verify willingness to pay before creating an opportunity."
    if status == ACT_NOW:
        return "Create a focused validation sprint with buyer, channel, price, and kill criteria."
    return _first(candidate.get("next_actions", [])) or "Collect one more independent signal before promoting."


def _strongest_independence(left: str, right: str) -> str:
    rank = {
        "": 0,
        "media_only": 1,
        "single_ultimate": 2,
        "formal_independent": 3,
        "hard_independent": 4,
    }
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def _prior_status_bias(prior: dict[str, Any]) -> str:
    grade_strength = GRADE_STRENGTH.get(prior.get("best_grade", "E"), 1)
    archetype = prior.get("archetype", "")
    if archetype in {"public_pr_mega_arr", "incumbent_market_map"}:
        return WATCH
    if archetype in {"quiet_b2b_paid_pilot", "renewal_repeat_payment", "indie_micro_saas"}:
        if prior["case_count"] >= 2 or prior["avg_quiet_money_score"] >= 62 or prior["avg_entry_fit"] >= 64:
            return VALIDATE_SOON
    if (
        grade_strength >= GRADE_STRENGTH["B"]
        and prior["avg_entry_fit"] >= 68
        and prior["avg_quiet_money_score"] >= 68
    ):
        return VALIDATE_SOON
    if prior["case_count"] >= 2 or prior["avg_quiet_money_score"] >= 58 or grade_strength >= GRADE_STRENGTH["C"]:
        return WATCH
    return NEW_SPARK


def _prior_warning_triggers(prior: dict[str, Any]) -> list[str]:
    triggers = []
    archetype = prior.get("archetype", "")
    if archetype in {"public_pr_mega_arr", "incumbent_market_map"}:
        triggers.append("treat as market map unless a smaller B/C wedge appears")
    if archetype in {"quiet_b2b_paid_pilot", "renewal_repeat_payment"}:
        triggers.append("payment-backed quiet-money pattern")
    if archetype == "indie_micro_saas":
        triggers.append("small self-serve software wedge with direct buyer proof")
    if prior["best_grade"] in {"A", "B"}:
        triggers.append("formal revenue proof or hard payment trace")
    if prior["avg_quiet_money_score"] >= 65:
        triggers.append("quiet-money evidence around a repeatable workflow")
    if prior["avg_entry_fit"] >= 65:
        triggers.append("small-team entry fit appears workable")
    if "enterprise_procurement" in prior.get("risk_flags", []):
        triggers.append("watch for smaller non-enterprise wedge")
    if "heavy_capital" in prior.get("risk_flags", []):
        triggers.append("prefer software/service layer around the capital-heavy market")
    return triggers or ["monitor for repeated demand and stronger evidence"]


def _prior_default_action(prior: dict[str, Any]) -> str:
    if prior["status_bias"] == VALIDATE_SOON:
        return "Map the buyer, find 3 reachable users, and verify willingness to pay."
    if prior["status_bias"] == WATCH:
        return "Track repeated signals and search for B/C-grade wedge evidence."
    return "Keep as discovery context until stronger proof appears."


def _alert_id(topic_key: str) -> str:
    digest = hashlib.sha1(topic_key.encode("utf-8")).hexdigest()[:10]
    return f"alert-{digest}"


def _topic_key(text: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", text.lower())
        if token not in STOPWORDS
    ]
    if not tokens:
        return "general"
    counts = Counter(tokens)
    return "-".join(token for token, _ in counts.most_common(6))


def _best_grade(left: str, right: str) -> str:
    left = (left or "E").upper()
    right = (right or "E").upper()
    return left if GRADE_STRENGTH.get(left, 1) >= GRADE_STRENGTH.get(right, 1) else right


def _unique(values: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value in ("", None):
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _unique_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for value in values:
        if not isinstance(value, dict):
            continue
        key = (
            value.get("type", ""),
            value.get("title", ""),
            value.get("url", ""),
            value.get("source_id", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def _first(values: list[Any]) -> str:
    return str(values[0]) if values else ""


def _first_url(evidence: list[dict[str, Any]]) -> str:
    for item in evidence:
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return ""


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")[:140]
