"""Revenue case triage: learn from what already made money."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ode.core.constants import EVIDENCE_GRADE_STRENGTH as GRADE_STRENGTH
from ode.heuristics.dbs import copyability_label, score_copyability
from ode.heuristics.fit_lens import FounderProfile, default_profile


DEFAULT_CASES_PATH = Path(__file__).resolve().parents[2] / "examples" / "revenue_cases" / "seed_cases.json"
GRADE_BASE_CONFIDENCE = {"A": 92, "B": 78, "C": 62, "D": 40, "E": 18}
ENTRY_SWEET_SPOT_GRADES = {"B", "C"}
QUIET_MONEY_EVIDENCE_TYPES = {"signed_contract", "payment_receipt"}
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
    archetype: str = ""
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
            archetype=str(data.get("archetype", "")).strip(),
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
    entry_fit: float
    quiet_money_score: float
    case_role: str
    suitability: str
    revenue_quality: str
    archetype: str
    evidence_independence: str
    red_flags: list[str]
    verification_steps: list[str]
    next_actions: list[str]
    dbs_copyability: dict[str, Any] = field(default_factory=dict)
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
    evidence_independence = classify_evidence_independence(revenue_case)
    confidence = _confidence(revenue_case, evidence_grade, red_flags)
    founder_fit = _founder_fit(revenue_case, founder)
    entry_fit = _entry_fit(revenue_case, founder, evidence_grade)
    revenue_quality = _revenue_quality(revenue_case)
    quiet_money_score = _quiet_money_score(revenue_case, evidence_grade, revenue_quality, red_flags)
    protected = confidence >= 58 and founder_fit < 45 and revenue_quality != "not_revenue"
    case_role = _case_role(
        evidence_grade=evidence_grade,
        confidence=confidence,
        founder_fit=founder_fit,
        entry_fit=entry_fit,
        quiet_money_score=quiet_money_score,
        revenue_quality=revenue_quality,
    )
    suitability = _suitability(
        confidence=confidence,
        founder_fit=founder_fit,
        entry_fit=entry_fit,
        quiet_money_score=quiet_money_score,
        evidence_grade=evidence_grade,
        revenue_quality=revenue_quality,
        protected_as_watchlist=protected,
    )
    dbs_copyability = score_copyability(
        revenue_case,
        profile=founder,
        analysis={
            "evidence_grade": evidence_grade,
            "confidence": confidence,
            "founder_fit": founder_fit,
            "entry_fit": entry_fit,
            "quiet_money_score": quiet_money_score,
            "revenue_quality": revenue_quality,
            "evidence_independence": evidence_independence,
        },
    ).to_dict()

    return RevenueCaseAnalysis(
        case=revenue_case,
        evidence_grade=evidence_grade,
        confidence=round(confidence, 1),
        founder_fit=round(founder_fit, 1),
        entry_fit=round(entry_fit, 1),
        quiet_money_score=round(quiet_money_score, 1),
        case_role=case_role,
        suitability=suitability,
        revenue_quality=revenue_quality,
        archetype=revenue_case.archetype or _infer_archetype(revenue_case, case_role, suitability),
        evidence_independence=evidence_independence,
        red_flags=red_flags,
        verification_steps=_verification_steps(revenue_case, evidence_grade, revenue_quality, red_flags),
        next_actions=_next_actions(suitability, evidence_grade, revenue_quality, case_role),
        dbs_copyability=dbs_copyability,
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

    suitability_rank = {
        "Prime Case": 0,
        "Quiet Candidate": 1,
        "Candidate": 2,
        "Market Map": 3,
        "Watchlist": 4,
        "Verify First": 5,
        "Reject For Now": 6,
    }
    analyses.sort(key=lambda item: (
        suitability_rank.get(item.suitability, 9),
        -item.quiet_money_score,
        -item.entry_fit,
        -item.founder_fit,
        -item.confidence,
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


def classify_evidence_independence(case: RevenueCase) -> str:
    """Classify whether evidence is independently verifiable or PR-derived."""

    evidence_types = {item.type for item in case.evidence}
    source_names = {item.source_name.lower() for item in case.evidence if item.source_name}

    if evidence_types & {"signed_contract", "payment_receipt", "audited_financial", "public_filing", "exchange_disclosure"}:
        return "hard_independent"
    if "company_formal_disclosure" in evidence_types and len(source_names) >= 2:
        return "formal_independent"
    if "company_formal_disclosure" in evidence_types:
        return "single_ultimate"
    if "company_pr" in evidence_types:
        return "single_ultimate"
    if evidence_types and evidence_types <= {"independent_media", "founder_interview", "investor_article", "analyst_estimate", "data_platform_estimate", "media_estimate"}:
        return "media_only"
    return "single_ultimate"


def format_revenue_case_report(analyses: list[RevenueCaseAnalysis]) -> str:
    """Format ranked case analysis for terminal output."""

    lines = [
        "# Revenue Case Analysis",
        "",
        "| Rank | Case | Region | Grade | Independence | Copyability | Confidence | Founder Fit | Entry Fit | Quiet Money | Role | Suitability |",
        "|------|------|--------|-------|--------------|-------------|------------|-------------|-----------|-------------|------|-------------|",
    ]
    for index, item in enumerate(analyses, 1):
        case = item.case
        lines.append(
            f"| {index} | {case.name} | {case.region} | {item.evidence_grade} | "
            f"{item.evidence_independence} | {copyability_label(item.dbs_copyability)} | "
            f"{item.confidence:.1f} | {item.founder_fit:.1f} | {item.entry_fit:.1f} | "
            f"{item.quiet_money_score:.1f} | "
            f"{item.case_role} | {item.suitability} |"
        )

    for item in analyses:
        case = item.case
        lines.extend([
            "",
            f"## {case.name}",
            f"Claim: {case.claim}",
            f"Metric: {case.metric_type} {case.amount or ''} {case.currency} {case.period}".strip(),
            f"Revenue quality: {item.revenue_quality}",
            f"Archetype: {item.archetype}",
            f"Evidence independence: {item.evidence_independence}",
            f"DBS copyability: {copyability_label(item.dbs_copyability)}",
            f"Evidence grade: {item.evidence_grade}",
            f"Entry fit: {item.entry_fit:.1f}",
            f"Quiet money score: {item.quiet_money_score:.1f}",
            f"Role: {item.case_role}",
            f"Suitability: {item.suitability}",
        ])
        copyability = item.dbs_copyability or {}
        if copyability.get("blockers"):
            lines.append("Copyability blockers:")
            lines.extend([f"- {flag}" for flag in copyability["blockers"]])
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


def _entry_fit(case: RevenueCase, founder: FounderProfile, evidence_grade: str) -> float:
    """Estimate whether this is directly enterable by the current builder.

    Evidence strength proves the market. Entry fit asks whether the current
    founder can find a small wedge without copying an incumbent's capital,
    channels, inventory, or procurement path.
    """

    text = " ".join([
        case.name,
        case.category,
        case.claim,
        case.notes,
        " ".join(case.fit_tags),
        " ".join(case.risk_flags),
    ]).lower()

    score = 42.0
    if evidence_grade in ENTRY_SWEET_SPOT_GRADES:
        score += 12
    elif evidence_grade == "A":
        score -= 8
    elif evidence_grade in {"D", "E"}:
        score -= 10

    if case.metric_type in {"arr", "mrr", "subscription_revenue", "paid_subscribers"}:
        score += 8
    if case.metric_type in {"contract_value", "order_revenue"}:
        score += 4

    wedge_terms = {
        "software",
        "workflow",
        "automation",
        "api",
        "developer",
        "vertical saas",
        "subscription",
        "knowledge",
        "analytics",
        "tool",
        "platform",
        "data",
    }
    if any(term in text for term in wedge_terms):
        score += 14
    if "hardware" in text and not any(term in text for term in {"software", "workflow", "data", "api"}):
        score -= 10
    if any(term in text for term in {"robot", "robotics", "lidar", "chip", "server", "glasses"}):
        score -= 5

    penalties = {
        "heavy_capital": 26,
        "requires_inventory": 18,
        "enterprise_procurement": 14,
        "regulated": 14,
        "platform_dependency": 7,
        "low_margin": 8,
    }
    for flag, penalty in penalties.items():
        if flag in case.risk_flags:
            score -= penalty

    if founder.capital_budget_usd <= 5000 and any(flag in case.risk_flags for flag in {"heavy_capital", "requires_inventory"}):
        score -= 10
    if founder.validation_window_days <= 30 and "enterprise_procurement" in case.risk_flags:
        score -= 8
    if case.amount and case.amount >= 100_000_000 and evidence_grade == "A":
        score -= 8

    return _clamp(score)


def _quiet_money_score(
    case: RevenueCase,
    evidence_grade: str,
    revenue_quality: str,
    red_flags: list[str],
) -> float:
    """Detect low-publicity money signals without lowering proof standards."""

    evidence_types = {item.type for item in case.evidence}
    source_names = {item.source_name for item in case.evidence if item.source_name}
    text = " ".join([
        case.name,
        case.category,
        case.claim,
        case.notes,
        " ".join(case.fit_tags),
        " ".join(case.risk_flags),
        " ".join(item.notes for item in case.evidence),
    ]).lower()

    score = 28.0
    if revenue_quality == "direct_revenue":
        score += 10
    elif revenue_quality == "revenue_adjacent":
        score += 2
    else:
        score -= 25

    if evidence_types & QUIET_MONEY_EVIDENCE_TYPES:
        score += 22
    if "company_formal_disclosure" in evidence_types:
        score += 8
    if "company_pr" in evidence_types and not (evidence_types & QUIET_MONEY_EVIDENCE_TYPES):
        score -= 12
    if evidence_types <= {"social_screenshot", "rumor"}:
        score -= 18

    if evidence_grade in ENTRY_SWEET_SPOT_GRADES:
        score += 8
    elif evidence_grade == "A":
        score -= 8
    elif evidence_grade in {"D", "E"}:
        score -= 6

    if case.metric_type in {"contract_value", "order_revenue", "subscription_revenue", "net_revenue"}:
        score += 14
    elif case.metric_type in {"arr", "mrr", "revenue"}:
        score += 5
    elif case.metric_type == "paid_subscribers":
        score += 2

    if case.amount is None:
        score -= 4
    elif 1_000 <= case.amount <= 5_000_000:
        score += 12
    elif case.amount <= 50_000_000:
        score += 8
    elif case.amount >= 100_000_000:
        score -= 10

    if len(source_names) >= 2 or len(case.source_ids) >= 2:
        score += 5

    operational_terms = {
        "contract",
        "invoice",
        "order",
        "booking",
        "procurement",
        "tender",
        "dealer",
        "integrator",
        "maintenance",
        "rental",
        "ops",
        "operation",
        "vertical",
        "niche",
        "workflow",
        "renewal",
        "repeat",
    }
    score += min(sum(1 for term in operational_terms if term in text) * 4, 20)

    noisy_terms = {"funding", "valuation", "press", "viral", "downloads", "traffic"}
    score -= min(sum(1 for term in noisy_terms if term in text) * 4, 16)

    if "platform_dependency" in case.risk_flags:
        score -= 4
    if "heavy_capital" in case.risk_flags:
        score -= 5
    if "requires_inventory" in case.risk_flags:
        score -= 4
    if "enterprise_procurement" in case.risk_flags:
        score += 2

    if red_flags:
        score -= min(len(red_flags) * 2, 8)

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
    entry_fit: float,
    quiet_money_score: float,
    evidence_grade: str,
    revenue_quality: str,
    protected_as_watchlist: bool,
) -> str:
    if revenue_quality == "not_revenue" and confidence < 55:
        return "Reject For Now"
    if evidence_grade == "A" and entry_fit < 62:
        return "Market Map"
    if (
        confidence >= 76
        and founder_fit >= 60
        and entry_fit >= 58
        and evidence_grade in ENTRY_SWEET_SPOT_GRADES
    ):
        return "Prime Case"
    if quiet_money_score >= 68 and entry_fit >= 45 and confidence >= 42 and revenue_quality != "not_revenue":
        return "Quiet Candidate"
    if confidence >= 62 and founder_fit >= 48 and entry_fit >= 42:
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
    if grade == "A":
        steps.append("Treat A-grade cases as market maps first; search for B/C-grade wedges around the incumbent instead of copying the core business.")
    if case.evidence and any(item.type in QUIET_MONEY_EVIDENCE_TYPES for item in case.evidence):
        steps.append("For quiet-money cases, verify repeatability: second customer, renewal, refill order, or paid operator referral.")
    steps.append("Identify the repeatable pattern: buyer, painful job, channel, pricing, and why now.")
    steps.append("Look for at least one disconfirming source before moving to build validation.")
    return steps


def _next_actions(suitability: str, grade: str, revenue_quality: str, case_role: str) -> list[str]:
    if suitability == "Market Map" or case_role == "market_map":
        return [
            "Use this case to confirm the budget pool and buyer vocabulary.",
            "Look for under-served workflows, services, or tooling around the proven incumbent.",
            "Do not model the first validation sprint on the incumbent's capital or channel requirements.",
        ]
    if suitability == "Quiet Candidate" or case_role == "quiet_money":
        return [
            "Validate the hidden demand before expanding the source search.",
            "Find 5 operators or buyers in the same narrow workflow.",
            "Ask for proof of repeat purchase, renewal, inventory turn, or paid implementation.",
        ]
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


def _case_role(
    *,
    evidence_grade: str,
    confidence: float,
    founder_fit: float,
    entry_fit: float,
    quiet_money_score: float,
    revenue_quality: str,
) -> str:
    if revenue_quality == "not_revenue":
        return "context_only"
    if evidence_grade == "A" and entry_fit < 62:
        return "market_map"
    if evidence_grade in ENTRY_SWEET_SPOT_GRADES and entry_fit >= 58 and founder_fit >= 50:
        return "buildable_wedge"
    if quiet_money_score >= 68 and entry_fit >= 45:
        return "quiet_money"
    if confidence >= 55 and entry_fit >= 40:
        return "validation_candidate"
    if confidence >= 42:
        return "watchlist"
    return "weak_signal"


def _infer_archetype(case: RevenueCase, case_role: str, suitability: str) -> str:
    evidence_types = {item.type for item in case.evidence}
    text = " ".join([
        case.name,
        case.category,
        case.claim,
        case.notes,
        " ".join(case.fit_tags),
        " ".join(case.risk_flags),
    ]).lower()

    if suitability == "Market Map" or case_role == "market_map":
        return "incumbent_market_map"
    if evidence_types & {"signed_contract", "payment_receipt"}:
        if any(term in text for term in {"renewal", "repeat", "retention", "second order"}):
            return "renewal_repeat_payment"
        if any(term in text for term in {"indie", "micro", "solo", "bootstrap", "mrr"}):
            return "indie_micro_saas"
        return "quiet_b2b_paid_pilot"
    if case.amount and case.amount >= 100_000_000 and "company_pr" in evidence_types:
        return "public_pr_mega_arr"
    if case_role == "quiet_money":
        return "quiet_money_trace"
    return "revenue_case"


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
