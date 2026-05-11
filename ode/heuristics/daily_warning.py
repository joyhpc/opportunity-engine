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


NEW_SPARK = "New Spark"
WATCH = "Watch"
VALIDATE_SOON = "Validate Soon"
ACT_NOW = "Act Now"

ACTIVE_LABELS = [NEW_SPARK, WATCH, VALIDATE_SOON, ACT_NOW]

GRADE_STRENGTH = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
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
            "evidence_refs": [],
            "reasons": [],
            "next_actions": [],
            "metrics": {},
        })
        item["candidate_types"] = _unique(item["candidate_types"] + candidate.get("candidate_types", []))
        item["tags"] = _unique(item["tags"] + candidate.get("tags", []))
        item["source_ids"] = _unique(item["source_ids"] + candidate.get("source_ids", []))
        item["source_titles"] = _unique(item["source_titles"] + candidate.get("source_titles", []))
        item["evidence_refs"] = _unique_dicts(item["evidence_refs"] + candidate.get("evidence_refs", []))
        item["reasons"] = _unique(item["reasons"] + candidate.get("reasons", []))
        item["next_actions"] = _unique(item["next_actions"] + candidate.get("next_actions", []))
        item["best_grade"] = _best_grade(item["best_grade"], candidate.get("best_grade", "E"))
        item["priority"] = max(float(item["priority"]), float(candidate.get("priority", 0) or 0))
        item["founder_fit"] = max(float(item["founder_fit"]), float(candidate.get("founder_fit", 0) or 0))
        item["source_diversity"] = len({source for source in item["source_ids"] if source})
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
        status = classify_alert(candidate, previous_item=previous, state_item=item)
        item["status"] = status
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
        "reset": reset,
    }


def learn_case_priors(revenue_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Learn reusable warning priors from analyzed revenue cases."""

    groups: dict[str, dict[str, Any]] = {}
    for analysis in revenue_cases:
        case = analysis.get("case", {})
        tags = [str(tag) for tag in case.get("fit_tags", []) if tag]
        category = str(case.get("category") or "uncategorized")
        pattern = _case_pattern_name(category, tags)
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

    previous_grade = (previous_item or {}).get("best_grade", "E")
    grade_upgraded = grade_strength > GRADE_STRENGTH.get(previous_grade, 1)
    status_upgraded = previous_item and (
        grade_upgraded or priority_delta >= 15 or source_diversity > int(previous_item.get("source_diversity", 0) or 0)
    )

    if (
        previous_item
        and status_upgraded
        and founder_fit >= 70
        and (grade_strength >= GRADE_STRENGTH["B"] or priority >= 82)
        and not only_product_hunt
    ):
        return ACT_NOW

    if not only_product_hunt:
        if "revenue_case" in candidate_types and grade_strength >= GRADE_STRENGTH["B"]:
            return VALIDATE_SOON
        if "pain_signal" in candidate_types and grade_strength >= GRADE_STRENGTH["C"]:
            return VALIDATE_SOON
        if priority >= 84 and founder_fit >= 70 and source_diversity >= 2:
            return VALIDATE_SOON

    if days_seen >= 2 or source_diversity >= 2 or priority >= 65:
        return WATCH
    return NEW_SPARK


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
            lines.append(
                f"| {alert.get('status', NEW_SPARK)} | "
                f"{_cell(alert.get('title', ''))} | "
                f"{alert.get('best_grade', 'E')} | "
                f"{float(alert.get('founder_fit', 0) or 0):.1f} | "
                f"{alert.get('source_diversity', 0)} | "
                f"{float(alert.get('priority_delta', 0) or 0):+.1f} | "
                f"{_cell(_first(alert.get('reasons', [])))} |"
            )
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
            "| Level | Topic | Evidence | Fit | Sources | Next Action |",
            "|-------|-------|----------|-----|---------|-------------|",
        ])
        for alert in alerts:
            lines.append(
                f"| {alert.get('status', NEW_SPARK)} | {_cell(alert.get('title', ''))} | "
                f"{alert.get('best_grade', 'E')} | "
                f"{float(alert.get('founder_fit', 0) or 0):.1f} | "
                f"{alert.get('source_diversity', 0)} | "
                f"{_cell(_first(alert.get('next_actions', [])))} |"
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
    priority = max(
        float(analysis.get("quiet_money_score", 0) or 0),
        float(analysis.get("entry_fit", 0) or 0),
        float(analysis.get("confidence", 0) or 0),
    )
    founder_fit = float(analysis.get("founder_fit", 0) or 0)
    topic_key = _topic_key(" ".join(tags) or f"{case.get('category', '')} {title}")
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
        "evidence_refs": [{
            "type": "revenue_case",
            "title": title,
            "url": _first_url(case.get("evidence", [])),
            "source_id": ",".join(source_ids),
            "grade": grade,
        }],
        "reasons": [
            f"Revenue evidence grade {grade}; suitability {analysis.get('suitability', 'unknown')}."
        ],
        "next_actions": list(analysis.get("next_actions") or []),
        "metrics": {
            "confidence": analysis.get("confidence", 0),
            "entry_fit": analysis.get("entry_fit", 0),
            "quiet_money_score": analysis.get("quiet_money_score", 0),
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
        "source_diversity": max(
            int(previous.get("source_diversity", 0) or 0),
            int(candidate.get("source_diversity", 0) or 0),
        ),
        "best_grade": _best_grade(previous.get("best_grade", "E"), candidate.get("best_grade", "E")),
        "priority": priority,
        "previous_priority": previous_priority,
        "priority_delta": round(priority - previous_priority, 1),
        "founder_fit": max(float(previous.get("founder_fit", 0) or 0), float(candidate.get("founder_fit", 0) or 0)),
        "evidence_refs": _unique_dicts(previous.get("evidence_refs", []) + candidate.get("evidence_refs", []))[-12:],
        "last_reasons": candidate.get("reasons", []),
        "next_actions": candidate.get("next_actions", []),
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


def _prior_status_bias(prior: dict[str, Any]) -> str:
    grade_strength = GRADE_STRENGTH.get(prior.get("best_grade", "E"), 1)
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
