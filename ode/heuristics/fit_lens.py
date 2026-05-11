"""Founder Fit Lens: soft sorting without narrowing discovery too early."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from ode.core.recommendations import (
    BUILD_NOW,
    IGNORE,
    RESEARCH,
    VALIDATE_SOON,
    WATCH,
)


@dataclass(frozen=True)
class FounderProfile:
    """A lightweight profile used to rank opportunities, not discard them."""

    strengths: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    exploration_interests: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    preferred_channels: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    soft_negative_keywords: list[str] = field(default_factory=list)
    hard_exclusions: list[str] = field(default_factory=list)
    channel_weight: float = 7.0
    negative_weight: float = 12.0
    soft_negative_weight: float = 8.0
    validation_window_days: int = 30
    time_budget_hours_per_week: int = 10
    capital_budget_usd: float = 5000.0
    wildcard_reserve_pct: int = 25

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FounderProfile":
        if not data:
            return default_profile()
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LensResult:
    opportunity_score: float
    founder_fit: float
    discovery_value: float
    recommendation: str
    reasons: list[str]
    risks: list[str]
    next_actions: list[str]
    protected_as_wildcard: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_profile() -> FounderProfile:
    """Open default profile based on a technical solo/small-team builder."""

    return FounderProfile(
        strengths=[
            "software engineering",
            "AI workflows",
            "systems thinking",
            "rapid prototyping",
            "strategic analysis",
        ],
        constraints=[
            "avoid heavy upfront capital",
            "avoid long enterprise procurement before validation",
            "validate within 30 days",
        ],
        exploration_interests=[
            "AI agents",
            "developer tools",
            "automation",
            "knowledge systems",
            "vertical SaaS",
            "opportunity discovery",
        ],
        channels=[
            "GitHub",
            "technical communities",
            "founder networks",
            "builder communities",
        ],
        preferred_channels=[
            "reddit/r/saas",
            "reddit/r/sideproject",
            "reddit/r/webdev",
        ],
        negative_keywords=[
            "hardware",
            "clinical",
            "medical device",
            "manufacturing",
        ],
        soft_negative_keywords=[
            "enterprise procurement",
            "government",
            "regulated",
        ],
        hard_exclusions=[
            "illegal",
            "fraud",
            "weapon",
        ],
    )


def apply_fit_lens(
    opportunity: dict[str, Any],
    signals: list[dict[str, Any]] | None = None,
    profile: FounderProfile | dict[str, Any] | None = None,
) -> LensResult:
    """Classify an opportunity through an open-but-personalized lens."""

    founder = profile if isinstance(profile, FounderProfile) else FounderProfile.from_dict(profile)
    signals = signals or []

    text = _opportunity_text(opportunity, signals)
    hard_hits = _matches(founder.hard_exclusions, text)
    opportunity_score = _opportunity_score(opportunity, signals)
    founder_fit = _founder_fit(opportunity, signals, founder, text)
    discovery_value = _discovery_value(opportunity, signals, founder, text)

    reasons = _reason_notes(opportunity_score, founder_fit, discovery_value, founder, text)
    risks = _risk_notes(opportunity, signals, founder, text, hard_hits)
    protected_as_wildcard = discovery_value >= 70 and founder_fit < 55 and not hard_hits
    recommendation = _recommendation(
        opportunity_score=opportunity_score,
        founder_fit=founder_fit,
        discovery_value=discovery_value,
        hard_hits=hard_hits,
        signal_count=len(signals),
        protected_as_wildcard=protected_as_wildcard,
    )
    next_actions = _next_actions(recommendation, risks)

    return LensResult(
        opportunity_score=round(opportunity_score, 1),
        founder_fit=round(founder_fit, 1),
        discovery_value=round(discovery_value, 1),
        recommendation=recommendation,
        reasons=reasons,
        risks=risks,
        next_actions=next_actions,
        protected_as_wildcard=protected_as_wildcard,
    )


def format_lens_report(result: LensResult) -> str:
    """Format a LensResult for terminal output."""

    wildcard = " yes" if result.protected_as_wildcard else " no"
    lines = [
        "# Founder Fit Lens",
        "",
        f"Recommendation: {result.recommendation}",
        f"Opportunity Score: {result.opportunity_score:.1f}/100",
        f"Founder Fit: {result.founder_fit:.1f}/100",
        f"Discovery Value: {result.discovery_value:.1f}/100",
        f"Protected as Wildcard:{wildcard}",
        "",
        "## Why",
        *[f"- {reason}" for reason in result.reasons],
    ]
    if result.risks:
        lines.extend(["", "## Risks", *[f"- {risk}" for risk in result.risks]])
    if result.next_actions:
        lines.extend(["", "## Next Actions", *[f"- {action}" for action in result.next_actions]])
    return "\n".join(lines)


def _opportunity_score(opportunity: dict[str, Any], signals: list[dict[str, Any]]) -> float:
    scores = opportunity.get("scores") or {}
    if scores.get("_weighted_pct"):
        return _clamp(float(scores["_weighted_pct"]))

    dimension_values = [
        value
        for key, value in scores.items()
        if not str(key).startswith("_") and isinstance(value, (int, float))
    ]
    if dimension_values:
        return _clamp(sum(dimension_values) / len(dimension_values) * 10)

    signal_bonus = min(len(signals) * 8, 32)
    strong_bonus = sum(_strength_weight(signal.get("strength", "")) for signal in signals)
    return _clamp(35 + signal_bonus + strong_bonus)


def _founder_fit(
    opportunity: dict[str, Any],
    signals: list[dict[str, Any]],
    founder: FounderProfile,
    text: str,
) -> float:
    score = 35.0
    strength_hits = _matches(founder.strengths, text)
    interest_hits = _matches(founder.exploration_interests, text)
    channel_hits = _matches(founder.channels, text)
    constraint_hits = _matches(founder.constraints, text)

    score += min(len(strength_hits) * 10, 25)
    score += min(len(interest_hits) * 8, 24)
    score += min(len(channel_hits) * 5, 10)

    capability = opportunity.get("scores", {}).get("Capability Fit")
    if isinstance(capability, (int, float)):
        score = (score * 0.65) + (float(capability) * 10 * 0.35)

    if _has_any(text, ["hardware", "manufacturing", "medical device", "clinical trial"]):
        score -= 12
    if _has_any(text, ["enterprise", "procurement", "compliance"]):
        score -= 5
    if len(signals) >= 3:
        score += 5
    if constraint_hits:
        score -= min(len(constraint_hits) * 4, 12)

    return _clamp(score)


def _discovery_value(
    opportunity: dict[str, Any],
    signals: list[dict[str, Any]],
    founder: FounderProfile,
    text: str,
) -> float:
    score = 30.0
    score += min(len(signals) * 10, 35)
    score += min(len({signal.get("source", "") for signal in signals if signal.get("source")}) * 5, 15)
    score += min(sum(_strength_weight(signal.get("strength", "")) for signal in signals), 20)

    scores = opportunity.get("scores") or {}
    for key in ("Market Attractiveness", "AI-Native Potential (a16z)"):
        value = scores.get(key)
        if isinstance(value, (int, float)):
            score += max(0, (float(value) - 6) * 4)

    if _has_any(text, ["new", "emerging", "runtime", "agent", "autonomous", "infrastructure"]):
        score += 8
    if _matches(founder.exploration_interests, text):
        score += 5

    return _clamp(score)


def _recommendation(
    *,
    opportunity_score: float,
    founder_fit: float,
    discovery_value: float,
    hard_hits: list[str],
    signal_count: int,
    protected_as_wildcard: bool,
) -> str:
    if hard_hits:
        return IGNORE
    if signal_count < 2 and opportunity_score < 60:
        return RESEARCH
    if opportunity_score >= 70 and founder_fit >= 70:
        return BUILD_NOW
    if opportunity_score >= 65 and founder_fit >= 45:
        return VALIDATE_SOON
    if protected_as_wildcard:
        return WATCH
    if discovery_value >= 65:
        return RESEARCH
    if opportunity_score < 45 and discovery_value < 45:
        return IGNORE
    return WATCH


def _reason_notes(
    opportunity_score: float,
    founder_fit: float,
    discovery_value: float,
    founder: FounderProfile,
    text: str,
) -> list[str]:
    notes: list[str] = []
    if opportunity_score >= 70:
        notes.append("Opportunity quality is high enough to consider active validation.")
    elif opportunity_score >= 55:
        notes.append("Opportunity quality is plausible but needs more evidence.")
    else:
        notes.append("Opportunity quality is still weak or under-evidenced.")

    if founder_fit >= 70:
        notes.append("Founder fit is strong for the current profile.")
    elif founder_fit >= 45:
        notes.append("Founder fit is workable, but the first test should stay small.")
    else:
        notes.append("Founder fit is currently weak, so preserve it as learning before committing.")

    if discovery_value >= 70:
        notes.append("Discovery value is high; do not discard this just because fit is imperfect.")
    elif discovery_value >= 55:
        notes.append("Discovery value is meaningful enough to keep on the radar.")

    matched = _matches(founder.exploration_interests + founder.strengths, text)
    if matched:
        notes.append(f"Profile overlap: {', '.join(matched[:5])}.")
    return notes


def _risk_notes(
    opportunity: dict[str, Any],
    signals: list[dict[str, Any]],
    founder: FounderProfile,
    text: str,
    hard_hits: list[str],
) -> list[str]:
    risks: list[str] = []
    if hard_hits:
        risks.append(f"Hard exclusion matched: {', '.join(hard_hits)}.")
    if len(signals) < 2:
        risks.append("Signal base is thin; run open discovery before committing.")
    if opportunity.get("scores", {}).get("Validation Strength (YC MVT)", 10) < 6:
        risks.append("Validation strength is low; user payment or commitment evidence is missing.")
    if _has_any(text, ["enterprise", "security", "compliance"]):
        risks.append("Enterprise/security markets may have slow procurement and trust barriers.")
    if _has_any(text, ["regulated", "clinical", "medical", "finance"]):
        risks.append("Regulated-market risk should be validated before implementation.")
    if founder.capital_budget_usd < 10000 and _has_any(text, ["hardware", "manufacturing"]):
        risks.append("Capital needs may exceed current founder budget.")
    return risks


def _next_actions(recommendation: str, risks: list[str]) -> list[str]:
    if recommendation == BUILD_NOW:
        return [
            "Build a narrow prototype this week.",
            "Talk to 5 target users before adding breadth.",
            "Record one measurable validation experiment in ODE.",
        ]
    if recommendation == VALIDATE_SOON:
        return [
            "Design a 2-4 week validation sprint.",
            "Keep scope to the riskiest assumption.",
            "Require payment intent, design partner commitment, or repeated usage.",
        ]
    if recommendation == WATCH:
        return [
            "Keep this in the wildcard watchlist.",
            "Collect 3 more external signals before deciding.",
            "Look for an adjacent wedge that fits the founder profile better.",
        ]
    if recommendation == RESEARCH:
        return [
            "Run open discovery without fit filtering.",
            "Identify the buyer, painful moment, and current workaround.",
            "Re-score once at least 3 independent signals exist.",
        ]
    return [
        "Do not spend build time now.",
        "Keep only if a new strong signal changes opportunity quality.",
    ]


def _matches(terms: list[str], text: str) -> list[str]:
    normalized = text.lower()
    hits = []
    for term in terms:
        value = str(term).strip()
        if value and value.lower() in normalized:
            hits.append(value)
    return hits


def _has_any(text: str, terms: list[str]) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in terms)


def _strength_weight(strength: str) -> float:
    value = str(strength).lower()
    if value in {"强", "strong", "high"}:
        return 6
    if value in {"中", "medium", "mid"}:
        return 3
    return 0


def _opportunity_text(opportunity: dict[str, Any], signals: list[dict[str, Any]]) -> str:
    parts: list[str] = [
        str(opportunity.get("name", "")),
        str(opportunity.get("domain", "")),
        str(opportunity.get("description", "")),
        " ".join(str(item) for item in opportunity.get("keywords", [])),
        " ".join(str(item) for item in opportunity.get("tags", [])),
    ]
    for signal in signals:
        parts.extend([
            str(signal.get("title", "")),
            str(signal.get("keyword", "")),
            str(signal.get("source", "")),
        ])
    return " ".join(parts)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))
