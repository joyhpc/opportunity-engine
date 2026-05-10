"""Revenue case triage: learn from what already made money."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ode.heuristics.fit_lens import FounderProfile, default_profile


DEFAULT_CASES_PATH = Path(__file__).resolve().parents[2] / "examples" / "revenue_cases" / "seed_cases.json"

GRADE_STRENGTH = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
GRADE_BASE_CONFIDENCE = {"A": 92, "B": 78, "C": 62, "D": 40, "E": 18}
EVIDENCE_TYPE_GRADES = {
    "audited_financial": "A",
    "public_filing": "A",
    "exchange_disclosure": "A",
    "company_formal_disclosure": "B",
    "signed_contract": "B",
    "payment_receipt": "B",
    "company_pr": "C",
    "founder_interview": "C",
    "investor_article": "C",
    "independent_media": "C",
    "analyst_estimate": "D",
    "data_platform_estimate": "D",
    "government_promotion": "D",
    "media_estimate": "D",
    "social_screenshot": "E",
    "rumor": "E",
}
REVENUE_METRICS = {
    "arr",
    "mrr",
    "revenue",
    "net_revenue",
    "paid_subscribers",
    "contract_value",
    "order_revenue",
    "subscription_revenue",
}
REVENUE_ADJACENT_METRICS = {
    "gmv",
    "gross_sales",
    "bookings",
    "app_revenue_estimate",
    "marketplace_volume",
}
NON_REVENUE_METRICS = {
    "funding",
    "valuation",
    "downloads",
    "users",
    "traffic",
    "social_engagement",
    "press_mentions",
}


@dataclass(frozen=True)
class RevenueEvidence:
    type: str
    source_name: str
    url: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RevenueEvidence":
        return cls(
            type=str(data.get("type", "")).strip(),
            source_name=str(data.get("source_name", "")).strip(),
            url=str(data.get("url", "")).strip(),
            notes=str(data.get("notes", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevenueCase:
    id: str
    name: str
    category: str
    region: str
    claim: str
    metric_type: str
    amount: float | None = None
    currency: str = ""
    period: str = ""
    source_ids: list[str] = field(default_factory=list)
    evidence: list[RevenueEvidence] = field(default_factory=list)
    fit_tags: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    notes: str = ""
    published_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RevenueCase":
        evidence = [
            RevenueEvidence.from_dict(item)
            for item in data.get("evidence", [])
            if isinstance(item, dict)
        ]
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            category=str(data.get("category", "")).strip(),
            region=str(data.get("region", "global")).strip() or "global",
            claim=str(data.get("claim", "")).strip(),
            metric_type=str(data.get("metric_type", "")).strip().lower(),
            amount=data.get("amount"),
            currency=str(data.get("currency", "")).strip(),
            period=str(data.get("period", "")).strip(),
            source_ids=[str(item) for item in data.get("source_ids", [])],
            evidence=evidence,
            fit_tags=[str(item) for item in data.get("fit_tags", [])],
            risk_flags=[str(item) for item in data.get("risk_flags", [])],
            notes=str(data.get("notes", "")).strip(),
            published_at=str(data.get("published_at", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


@dataclass(frozen=True)
class RevenueCaseAnalysis:
    case: RevenueCase
    evidence_grade: str
    confidence: float
    founder_fit: float
    suitability: str
    revenue_quality: str
    red_flags: list[str]
    verification_steps: list[str]
    next_actions: list[str]
    protected_as_watchlist: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["case"] = self.case.to_dict()
        return data


def load_revenue_cases(path: str | Path | None = None) -> list[RevenueCase]:
    """Load revenue cases from a JSON file."""

    case_path = Path(path) if path else DEFAULT_CASES_PATH
    data = json.loads(case_path.read_text(encoding="utf-8"))
    cases = data.get("cases", data if isinstance(data, list) else [])
    if not isinstance(cases, list):
        raise ValueError("Revenue case file must contain a list or {'cases': [...]} object")
    return [RevenueCase.from_dict(item) for item in cases if isinstance(item, dict)]


def analyze_revenue_case(
    case: RevenueCase | dict[str, Any],
    profile: FounderProfile | dict[str, Any] | None = None,
) -> RevenueCaseAnalysis:
    """Score one case for evidence quality, fit, and next verification steps."""

    revenue_case = case if isinstance(case, RevenueCase) else RevenueCase.from_dict(case)
    founder = profile if isinstance(profile, FounderProfile) else FounderProfile.from_dict(profile)

    evidence_grade, red_flags = grade_revenue_evidence(revenue_case)
    confidence = _confidence(revenue_case, evidence_grade, red_flags)
    founder_fit = _founder_fit(revenue_case, founder)
    revenue_quality = _revenue_quality(revenue_case)
    protected = confidence >= 58 and founder_fit < 45 and revenue_quality != "not_revenue"
    suitability = _suitability(
        confidence=confidence,
        founder_fit=founder_fit,
        evidence_grade=evidence_grade,
        revenue_quality=revenue_quality,
        protected_as_watchlist=protected,
    )

    return RevenueCaseAnalysis(
        case=revenue_case,
        evidence_grade=evidence_grade,
        confidence=round(confidence, 1),
        founder_fit=round(founder_fit, 1),
        suitability=suitability,
        revenue_quality=revenue_quality,
        red_flags=red_flags,
        verification_steps=_verification_steps(revenue_case, evidence_grade, revenue_quality, red_flags),
        next_actions=_next_actions(suitability, evidence_grade, revenue_quality),
        protected_as_watchlist=protected,
    )


def analyze_revenue_cases(
    *,
    path: str | Path | None = None,
    profile: FounderProfile | dict[str, Any] | None = None,
    region: str | None = None,
    min_grade: str | None = None,
    top: int | None = None,
) -> list[RevenueCaseAnalysis]:
    """Load, filter, and rank revenue cases."""

    cases = load_revenue_cases(path)
    if region:
        cases = [case for case in cases if case.region == region]

    analyses = [analyze_revenue_case(case, profile=profile or default_profile()) for case in cases]
    if min_grade:
        threshold = GRADE_STRENGTH[min_grade]
        analyses = [
            item for item in analyses
            if GRADE_STRENGTH[item.evidence_grade] >= threshold
        ]

    analyses.sort(key=lambda item: (
        item.suitability != "Prime Case",
        -item.confidence,
        -item.founder_fit,
        item.case.name,
    ))
    return analyses[:top] if top else analyses


def grade_revenue_evidence(case: RevenueCase) -> tuple[str, list[str]]:
    """Return an A-E evidence grade plus red flags."""

    red_flags: list[str] = []
    if not case.evidence:
        return "E", ["No evidence items attached."]

    grade = "E"
    evidence_types = {item.type for item in case.evidence}
    for item in case.evidence:
        candidate = EVIDENCE_TYPE_GRADES.get(item.type, "E")
        if GRADE_STRENGTH[candidate] > GRADE_STRENGTH[grade]:
            grade = candidate

    if "company_pr" in evidence_types and "independent_media" in evidence_types:
        grade = _stronger_grade(grade, "B")

    metric = case.metric_type
    if metric in NON_REVENUE_METRICS:
        grade = _cap_grade(grade, "D")
        red_flags.append(f"{metric} is not revenue; use it only as context.")
    elif metric in REVENUE_ADJACENT_METRICS:
        grade = _cap_grade(grade, "C")
        red_flags.append(f"{metric} is revenue-adjacent; verify take-rate, refunds, and net revenue.")
    elif metric not in REVENUE_METRICS:
        grade = _cap_grade(grade, "D")
        red_flags.append(f"Unknown metric type '{metric}'; verify it is actual revenue.")

    if evidence_types == {"government_promotion"}:
        grade = _cap_grade(grade, "D")
        red_flags.append("Government promotion is policy context, not market or revenue proof.")

    if case.amount is None:
        red_flags.append("No numeric amount captured.")
    if not case.period:
        red_flags.append("No period captured for the revenue claim.")
    if "platform_dependency" in case.risk_flags:
        red_flags.append("Platform dependency can make replication fragile.")

    return grade, red_flags


def format_revenue_case_report(analyses: list[RevenueCaseAnalysis]) -> str:
    """Format ranked case analysis for terminal output."""

    lines = [
        "# Revenue Case Analysis",
        "",
        "| Rank | Case | Region | Grade | Confidence | Fit | Suitability |",
        "|------|------|--------|-------|------------|-----|-------------|",
    ]
    for index, item in enumerate(analyses, 1):
        case = item.case
        lines.append(
            f"| {index} | {case.name} | {case.region} | {item.evidence_grade} | "
            f"{item.confidence:.1f} | {item.founder_fit:.1f} | {item.suitability} |"
        )

    for item in analyses:
        case = item.case
        lines.extend([
            "",
            f"## {case.name}",
            f"Claim: {case.claim}",
            f"Metric: {case.metric_type} {case.amount or ''} {case.currency} {case.period}".strip(),
            f"Revenue quality: {item.revenue_quality}",
            f"Evidence grade: {item.evidence_grade}",
            f"Suitability: {item.suitability}",
        ])
        if item.red_flags:
            lines.append("Red flags:")
            lines.extend([f"- {flag}" for flag in item.red_flags])
        lines.append("Verification steps:")
        lines.extend([f"- {step}" for step in item.verification_steps])
        lines.append("Next actions:")
        lines.extend([f"- {step}" for step in item.next_actions])

    return "\n".join(lines)


def _confidence(case: RevenueCase, grade: str, red_flags: list[str]) -> float:
    score = float(GRADE_BASE_CONFIDENCE[grade])
    evidence_types = {item.type for item in case.evidence}
    source_names = {item.source_name for item in case.evidence if item.source_name}

    if case.amount is not None and case.currency:
        score += 5
    if case.period:
        score += 5
    if len(evidence_types) >= 2:
        score += 5
    if len(source_names) >= 2:
        score += 4
    if any(item.url for item in case.evidence):
        score += 3
    if "estimate" in " ".join(evidence_types):
        score -= 8
    score -= min(len(red_flags) * 4, 20)
    return _clamp(score)


def _founder_fit(case: RevenueCase, founder: FounderProfile) -> float:
    text = " ".join([
        case.name,
        case.category,
        case.claim,
        case.notes,
        " ".join(case.fit_tags),
    ]).lower()

    score = 35.0
    score += min(_match_count(founder.strengths, text) * 8, 24)
    score += min(_match_count(founder.exploration_interests, text) * 9, 27)
    score += min(_match_count(founder.channels, text) * 5, 12)

    if case.region == "china":
        score += 4
    if case.metric_type in {"arr", "mrr", "subscription_revenue", "paid_subscribers"}:
        score += 7
    if "developer" in text or "api" in text or "infrastructure" in text:
        score += 8

    penalties = {
        "heavy_capital": 12,
        "regulated": 10,
        "enterprise_procurement": 7,
        "requires_inventory": 8,
        "platform_dependency": 6,
        "low_margin": 6,
    }
    for flag, penalty in penalties.items():
        if flag in case.risk_flags:
            score -= penalty

    return _clamp(score)


def _revenue_quality(case: RevenueCase) -> str:
    if case.metric_type in REVENUE_METRICS:
        return "direct_revenue"
    if case.metric_type in REVENUE_ADJACENT_METRICS:
        return "revenue_adjacent"
    if case.metric_type in NON_REVENUE_METRICS:
        return "not_revenue"
    return "unknown"


def _suitability(
    *,
    confidence: float,
    founder_fit: float,
    evidence_grade: str,
    revenue_quality: str,
    protected_as_watchlist: bool,
) -> str:
    if revenue_quality == "not_revenue" and confidence < 55:
        return "Reject For Now"
    if confidence >= 76 and founder_fit >= 60 and evidence_grade in {"A", "B"}:
        return "Prime Case"
    if confidence >= 62 and founder_fit >= 48:
        return "Candidate"
    if protected_as_watchlist:
        return "Watchlist"
    if confidence >= 42:
        return "Verify First"
    return "Reject For Now"


def _verification_steps(
    case: RevenueCase,
    grade: str,
    revenue_quality: str,
    red_flags: list[str],
) -> list[str]:
    steps = []
    if grade in {"C", "D", "E"}:
        steps.append("Find a primary source: filing, audited report, contract, invoice, or official results deck.")
    if revenue_quality == "revenue_adjacent":
        steps.append("Convert GMV/gross sales into net revenue: take-rate, refunds, discounts, and fees.")
    if revenue_quality == "not_revenue":
        steps.append("Do not treat funding, valuation, downloads, or users as revenue evidence.")
    if any("Government promotion" in flag for flag in red_flags):
        steps.append("Use government material only as policy/procurement context; verify buyer payment separately.")
    if case.region == "china":
        steps.append("Cross-check Chinese claims with filings, platform merchant data, contracts, or independent customer proof.")
    steps.append("Identify the repeatable pattern: buyer, painful job, channel, pricing, and why now.")
    steps.append("Look for at least one disconfirming source before moving to build validation.")
    return steps


def _next_actions(suitability: str, grade: str, revenue_quality: str) -> list[str]:
    if suitability == "Prime Case":
        return [
            "Extract the wedge and map it to a narrow validation sprint.",
            "Interview 3 comparable buyers or operators.",
            "Create an ODE opportunity only after the buyer and channel are explicit.",
        ]
    if suitability == "Candidate":
        return [
            "Run a focused authenticity pass before ideation.",
            "Translate the case into 2-3 adjacent opportunity hypotheses.",
            "Score with Founder Fit Lens instead of filtering it out early.",
        ]
    if suitability == "Watchlist":
        return [
            "Keep it visible as a wildcard because the case has learning value.",
            "Do not commit build time until a founder-fit wedge appears.",
            "Collect one more independent evidence item.",
        ]
    if suitability == "Verify First":
        return [
            "Pause ideation and verify the money claim first.",
            "Search for primary documents and customer-side proof.",
            "Downgrade the case if all evidence traces back to one PR or estimate.",
        ]
    return [
        "Do not use this as a model case yet.",
        "Keep only as weak market context unless new revenue proof appears.",
    ]


def _stronger_grade(current: str, candidate: str) -> str:
    if GRADE_STRENGTH[candidate] > GRADE_STRENGTH[current]:
        return candidate
    return current


def _cap_grade(current: str, cap: str) -> str:
    if GRADE_STRENGTH[current] > GRADE_STRENGTH[cap]:
        return cap
    return current


def _match_count(terms: list[str], text: str) -> int:
    return sum(1 for term in terms if str(term).strip().lower() in text)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))
