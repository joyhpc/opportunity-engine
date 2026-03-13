"""市场规模估算器 — TAM/SAM/SOM (重构为库函数).

Supports top-down and bottom-up estimation with cross-validation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class MarketEstimate:
    method: str
    tam: float
    sam: float
    som: float
    tam_label: str
    sam_label: str
    som_label: str
    assumptions: list
    confidence: str  # 高/中/低
    currency: str = "USD"

    def format_value(self, val: float) -> str:
        if val >= 1e9:
            return f"${val / 1e9:.1f}B"
        elif val >= 1e6:
            return f"${val / 1e6:.1f}M"
        elif val >= 1e3:
            return f"${val / 1e3:.0f}K"
        return f"${val:.0f}"

    def to_dict(self) -> dict:
        return asdict(self)


def topdown_estimate(market_size: float, segment_pct: float,
                     geo_pct: float, capture_pct: float = 5,
                     growth_rate: float = 0) -> MarketEstimate:
    """Top-down: TAM -> SAM (segment x geo) -> SOM (capture %)."""
    tam = market_size
    sam = tam * (segment_pct / 100) * (geo_pct / 100)
    som = sam * (capture_pct / 100)

    assumptions = [
        f"Total market: ${market_size / 1e9:.1f}B",
        f"Target segment: {segment_pct}%",
        f"Target geography: {geo_pct}%",
        f"Expected market share: {capture_pct}% (3yr)",
    ]
    if growth_rate > 0:
        assumptions.append(f"Annual growth: {growth_rate}%")

    return MarketEstimate(
        method="Top-Down",
        tam=tam, sam=sam, som=som,
        tam_label="Total market",
        sam_label="Serviceable (segment x geo)",
        som_label="Obtainable (3yr target)",
        assumptions=assumptions,
        confidence="中" if market_size < 1e10 else "低",
    )


def bottomup_estimate(target_users: int, price_per_unit: float,
                      frequency: int = 1, capture_pct: float = 2,
                      potential_users_total: int | None = None) -> MarketEstimate:
    """Bottom-up: users x price x frequency."""
    annual_rev_per_user = price_per_unit * frequency
    total_potential = potential_users_total or (target_users * 20)

    som = target_users * annual_rev_per_user * (capture_pct / 100)
    sam = total_potential * annual_rev_per_user
    tam = sam * 3

    assumptions = [
        f"Target users: {target_users:,}",
        f"Price per unit: ${price_per_unit:.2f}",
        f"Annual frequency: {frequency}",
        f"Annual value/user: ${annual_rev_per_user:.2f}",
        f"Total potential users: {total_potential:,}",
        f"Expected capture rate: {capture_pct}%",
    ]

    return MarketEstimate(
        method="Bottom-Up",
        tam=tam, sam=sam, som=som,
        tam_label="Broad market (incl. adjacencies)",
        sam_label="Direct serviceable users x ARPU",
        som_label="Expected capture x ARPU",
        assumptions=assumptions,
        confidence="中",
    )


def cross_validate(td: MarketEstimate, bu: MarketEstimate) -> dict:
    """Cross-validate top-down vs bottom-up estimates."""
    sam_ratio = td.sam / bu.sam if bu.sam > 0 else float("inf")
    som_ratio = td.som / bu.som if bu.som > 0 else float("inf")

    if 0.5 < sam_ratio < 2.0:
        consistency = "consistent"
    elif 0.2 < sam_ratio < 5.0:
        consistency = "divergent"
    else:
        consistency = "severely_divergent"

    return {
        "sam_ratio": round(sam_ratio, 2),
        "som_ratio": round(som_ratio, 2),
        "consistency": consistency,
    }


def estimate_market(tam: float = 0, sam: float = 0, som: float = 0,
                    growth_rate: float = 0,
                    **kwargs) -> dict:
    """Convenience: return a market dict for Opportunity.market field."""
    confidence = "高" if som > 0 and tam > 0 else "低"
    return {
        "tam": tam, "sam": sam, "som": som,
        "growth_rate": growth_rate,
        "confidence": confidence,
    }


def format_report(estimates: list[MarketEstimate],
                  validation: dict | None = None) -> str:
    """Generate markdown market sizing report."""
    lines = [
        "# Market Sizing Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for est in estimates:
        lines.extend([
            f"## {est.method}",
            "",
            "| Level | Description | Size |",
            "|-------|-------------|------|",
            f"| **TAM** | {est.tam_label} | {est.format_value(est.tam)} |",
            f"| **SAM** | {est.sam_label} | {est.format_value(est.sam)} |",
            f"| **SOM** | {est.som_label} | {est.format_value(est.som)} |",
            "",
            f"Confidence: **{est.confidence}**",
            "",
            "### Assumptions",
        ])
        for i, a in enumerate(est.assumptions, 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    if validation:
        lines.extend([
            "## Cross Validation",
            f"- SAM ratio (TD/BU): {validation['sam_ratio']}x",
            f"- Consistency: **{validation['consistency']}**",
            "",
        ])

    return "\n".join(lines)
