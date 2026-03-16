"""机会评分系统 v2 — 重构为库函数.

Bug fixes from original:
- Fixed kill threshold == maybe threshold (kill lowered to 30)
- Added '>' operator to redline condition parser
- Fixed system_rethink "不相关" score (5 -> 2)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# -- Scoring framework v2 (YC/a16z criteria) --------------------------------

FRAMEWORK_V2 = {
    "name": "Opportunity Scorecard v2 (YC/a16z)",
    "dimensions": [
        {
            "id": "market",
            "name": "Market Attractiveness",
            "weight": 25,
            "criteria": [
                {"id": "tam_size", "name": "Market Size", "description": "TAM > $1B = 10, > $100M = 7, > $10M = 4, < $10M = 2"},
                {"id": "growth", "name": "Growth Rate", "description": "CAGR > 20% = 10, > 10% = 7, > 5% = 4, < 5% = 2"},
                {"id": "timing", "name": "Market Timing", "description": "Early growth = 10, Mainstream = 7, Mature = 4, Decline = 1"},
            ],
        },
        {
            "id": "competition",
            "name": "Competitive Landscape",
            "weight": 15,
            "criteria": [
                {"id": "intensity", "name": "Competition Intensity", "description": "Blue ocean = 10, Few = 7, Red ocean = 3, Monopoly = 1"},
                {"id": "barrier", "name": "Entry Barrier", "description": "Low = 10, Medium = 6, High = 3"},
                {"id": "moat_potential", "name": "Moat Potential", "description": "Strong network/data = 10, Brand/scale = 6, Weak = 2"},
            ],
        },
        {
            "id": "capability",
            "name": "Capability Fit",
            "weight": 15,
            "criteria": [
                {"id": "skill_match", "name": "Skill Match", "description": "Core skills ready = 10, Minor learning = 7, Major learning = 3"},
                {"id": "resource_need", "name": "Resource Need", "description": "Solo = 10, 1-2 people = 7, Team = 4, Funding needed = 2"},
                {"id": "time_to_market", "name": "Time to Market", "description": "< 2wk = 10, < 1mo = 8, < 3mo = 5, > 3mo = 2"},
            ],
        },
        {
            "id": "economics",
            "name": "Economic Viability",
            "weight": 25,
            "criteria": [
                {"id": "ltv_cac", "name": "LTV/CAC Ratio", "description": "LTV/CAC > 5 = 10, > 3 = 8, > 1 = 5, < 1 = 1"},
                {"id": "margin", "name": "Gross Margin", "description": "> 80% = 10, > 60% = 8, > 40% = 5, < 40% = 2"},
                {"id": "payback", "name": "Payback Period", "description": "< 1mo = 10, < 3mo = 8, < 6mo = 5, > 6mo = 2"},
            ],
        },
        {
            "id": "validation",
            "name": "Validation Strength (YC MVT)",
            "weight": 10,
            "criteria": [
                {"id": "pain_evidence", "name": "Pain Evidence", "description": "Users actively seeking = 10, Interview confirmed = 7, Speculation = 3, None = 1"},
                {"id": "willingness_to_pay", "name": "Willingness to Pay", "description": "Already paid = 10, Verbal commit = 6, Survey says yes = 3, Untested = 1"},
                {"id": "mvt_result", "name": "MVT Result", "description": "10+ paid = 10, 5+ paid = 7, Signups = 4, Untested = 1"},
            ],
        },
        {
            "id": "ai_native",
            "name": "AI-Native Potential (a16z)",
            "weight": 10,
            "criteria": [
                # FIX: "不相关" was scored 5 (higher than 锦上添花=4), now correctly 2
                {"id": "system_rethink", "name": "System Rethink", "description": "Full rethink = 10, Significant = 7, Nice-to-have = 4, Not relevant = 2"},
                {"id": "data_loop", "name": "Data Flywheel", "description": "More use = smarter = 10, Data accumulation = 6, No data moat = 3"},
                {"id": "compound_advantage", "name": "Compound Advantage", "description": "AI reinforces biz model = 10, AI cuts cost = 7, AI optional = 4"},
            ],
        },
    ],
    "thresholds": {
        "go": 70,
        "maybe": 50,
        "kill": 30,  # FIX: was 50 (same as maybe), now 30
    },
    "redlines": [
        {"id": "no_pain", "name": "No real pain", "condition": "pain_evidence <= 2",
         "message": "No evidence of users actively seeking solutions"},
        {"id": "no_margin", "name": "Low margin", "condition": "margin <= 2",
         "message": "Gross margin < 40%, hard to sustain growth"},
        {"id": "giant_moat", "name": "Giant moat", "condition": "intensity <= 1 and barrier <= 3",
         "message": "Monopoly + high barrier, frontal attack nearly impossible"},
        {"id": "too_slow", "name": "Too slow", "condition": "time_to_market <= 2 and resource_need <= 3",
         "message": "Needs large resources and long time, not for solo founder"},
    ],
}

FRAMEWORK_V1 = {
    "name": "Opportunity Scorecard v1",
    "dimensions": [
        {
            "id": "market", "name": "Market Attractiveness", "weight": 30,
            "criteria": [
                {"id": "tam_size", "name": "Market Size", "description": "TAM > $1B = 10, > $100M = 7, > $10M = 4, < $10M = 2"},
                {"id": "growth", "name": "Growth Rate", "description": "CAGR > 20% = 10, > 10% = 7, > 5% = 4, < 5% = 2"},
                {"id": "timing", "name": "Market Timing", "description": "Early growth = 10, Mainstream = 7, Mature = 4, Decline = 1"},
            ],
        },
        {
            "id": "competition", "name": "Competitive Landscape", "weight": 20,
            "criteria": [
                {"id": "intensity", "name": "Competition Intensity", "description": "Blue ocean = 10, Few = 7, Red ocean = 3, Monopoly = 1"},
                {"id": "barrier", "name": "Entry Barrier", "description": "Low = 10, Medium = 6, High = 3"},
                {"id": "moat_potential", "name": "Moat Potential", "description": "Strong = 10, Medium = 6, Weak = 2"},
            ],
        },
        {
            "id": "capability", "name": "Capability Fit", "weight": 20,
            "criteria": [
                {"id": "skill_match", "name": "Skill Match", "description": "Core skills ready = 10, Minor learning = 7, Major learning = 3"},
                {"id": "resource_need", "name": "Resource Need", "description": "Low = 10, Medium = 6, High = 3"},
                {"id": "time_to_market", "name": "Time to Market", "description": "< 1mo = 10, < 3mo = 7, < 6mo = 4, > 6mo = 2"},
            ],
        },
        {
            "id": "economics", "name": "Economic Viability", "weight": 30,
            "criteria": [
                {"id": "ltv_cac", "name": "LTV/CAC Ratio", "description": "LTV/CAC > 5 = 10, > 3 = 8, > 1 = 5, < 1 = 1"},
                {"id": "margin", "name": "Gross Margin", "description": "> 80% = 10, > 60% = 8, > 40% = 5, < 40% = 2"},
                {"id": "payback", "name": "Payback Period", "description": "< 3mo = 10, < 6mo = 7, < 12mo = 4, > 12mo = 2"},
            ],
        },
    ],
    "thresholds": {"go": 70, "maybe": 50, "kill": 30},
}

FRAMEWORKS = {"v1": FRAMEWORK_V1, "v2": FRAMEWORK_V2}


@dataclass
class ScoringResult:
    opportunity_name: str
    total_score: float
    max_score: float
    percentage: float
    dimension_scores: dict
    verdict: str
    details: list
    redline_violations: list = field(default_factory=list)
    weakest_dimension: str = ""
    strongest_dimension: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def to_dict(self) -> dict:
        return {
            "opportunity_name": self.opportunity_name,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": self.percentage,
            "verdict": self.verdict,
            "weakest_dimension": self.weakest_dimension,
            "strongest_dimension": self.strongest_dimension,
            "redline_violations": self.redline_violations,
            "dimension_scores": self.dimension_scores,
            "details": self.details,
        }


def check_redlines(scores: dict, redlines: list) -> list[dict]:
    """Check redlines — any trigger forces Kill regardless of total score."""
    violations = []
    for rl in redlines:
        parts = rl["condition"].split(" and ")
        all_triggered = True
        for part in parts:
            tokens = part.strip().split()
            if len(tokens) == 3:
                field_id, op = tokens[0], tokens[1]
                try:
                    threshold = float(tokens[2])
                except ValueError:
                    all_triggered = False
                    continue
                value = scores.get(field_id, 5)
                _OPS = {"<=", "<", ">=", ">"}
                if op not in _OPS:
                    # Unknown operator — do not trigger
                    all_triggered = False
                elif op == "<=" and not (value <= threshold):
                    all_triggered = False
                elif op == "<" and not (value < threshold):
                    all_triggered = False
                elif op == ">=" and not (value >= threshold):
                    all_triggered = False
                elif op == ">" and not (value > threshold):
                    all_triggered = False
            else:
                all_triggered = False

        if all_triggered:
            violations.append({
                "id": rl["id"],
                "name": rl["name"],
                "message": rl["message"],
            })

    return violations


def score_opportunity(name: str, scores: dict,
                      framework: dict | None = None) -> ScoringResult:
    """Score an opportunity across all dimensions with weighted average."""
    fw = framework or FRAMEWORK_V2
    dimension_scores = {}
    details = []
    total_weighted = 0
    max_weighted = 0

    for dim in fw["dimensions"]:
        dim_scores = []
        for crit in dim["criteria"]:
            score = scores.get(crit["id"], 5)
            score = max(1, min(10, score))
            dim_scores.append(score)
            details.append({
                "dimension": dim["name"],
                "criterion": crit["name"],
                "score": score,
                "max": 10,
            })

        dim_avg = sum(dim_scores) / len(dim_scores)
        dim_weighted = dim_avg * dim["weight"] / 100
        dimension_scores[dim["name"]] = {
            "average": round(dim_avg, 1),
            "weight": dim["weight"],
            "weighted": round(dim_weighted, 1),
        }
        total_weighted += dim_weighted
        max_weighted += 10 * dim["weight"] / 100

    percentage = (total_weighted / max_weighted) * 100 if max_weighted > 0 else 0

    redline_violations = []
    if "redlines" in fw:
        redline_violations = check_redlines(scores, fw["redlines"])

    sorted_dims = sorted(dimension_scores.items(), key=lambda x: x[1]["average"])
    weakest = sorted_dims[0][0] if sorted_dims else ""
    strongest = sorted_dims[-1][0] if sorted_dims else ""

    if redline_violations:
        verdict = f"KILL — {len(redline_violations)} redline(s) triggered"
    else:
        thresholds = fw.get("thresholds", FRAMEWORK_V2["thresholds"])
        if percentage >= thresholds["go"]:
            verdict = "GO — worth pursuing"
        elif percentage >= thresholds["maybe"]:
            verdict = "MAYBE — needs more validation"
        else:
            verdict = "KILL — recommend dropping"

    return ScoringResult(
        opportunity_name=name,
        total_score=round(total_weighted, 1),
        max_score=round(max_weighted, 1),
        percentage=round(percentage, 1),
        dimension_scores=dimension_scores,
        verdict=verdict,
        details=details,
        redline_violations=redline_violations,
        weakest_dimension=weakest,
        strongest_dimension=strongest,
    )


def format_report(result: ScoringResult) -> str:
    """Generate scoring report as markdown."""
    lines = [
        "# Opportunity Scoring Report",
        f"**Opportunity**: {result.opportunity_name}",
        f"**Time**: {result.timestamp}",
        "",
        f"## Score: {result.percentage:.0f}/100",
        f"### {result.verdict}",
        "",
    ]

    if result.redline_violations:
        lines.extend(["## Redline Alerts", ""])
        for v in result.redline_violations:
            lines.append(f"- **{v['name']}**: {v['message']}")
        lines.extend(["", "> Redline trigger = forced Kill regardless of total score.", ""])

    lines.extend([
        "## Dimension Scores",
        "",
        "| Dimension | Weight | Avg | Weighted | Visual |",
        "|-----------|--------|-----|----------|--------|",
    ])

    for dim_name, ds in result.dimension_scores.items():
        bar_len = int(ds["average"])
        bar = "█" * bar_len + "░" * (10 - bar_len)
        marker = " <-- weakest" if dim_name == result.weakest_dimension else ""
        lines.append(
            f"| {dim_name} | {ds['weight']}% | {ds['average']}/10 | {ds['weighted']:.1f} | {bar} |{marker}"
        )

    lines.extend(["", "## Detail Scores", ""])
    current_dim = None
    for d in result.details:
        if d["dimension"] != current_dim:
            current_dim = d["dimension"]
            lines.append(f"### {current_dim}")
        score = d["score"]
        indicator = "OK" if score >= 7 else "WARN" if score >= 4 else "CRIT"
        lines.append(f"- [{indicator}] {d['criterion']}: **{score}/10**")

    return "\n".join(lines)
