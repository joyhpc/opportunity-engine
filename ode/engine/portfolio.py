"""Portfolio view — multi-opportunity comparison and management."""

from __future__ import annotations

from ..core.store import list_opportunities
from ..core.models import Opportunity


def get_portfolio_summary() -> list[dict]:
    """Get a summary of all opportunities in the portfolio."""
    opps = list_opportunities()
    summaries = []

    for opp in opps:
        # Use stored weighted percentage if available, else fallback
        score = opp.scores.get("_weighted_pct", 0) if opp.scores else 0
        summaries.append({
            "id": opp.id,
            "name": opp.name,
            "domain": opp.domain,
            "stage": opp.stage,
            "status": opp.status,
            "score": round(score, 1),
            "tam": opp.market.get("tam", 0),
            "ltv_cac": opp.financials.get("ltv_cac_ratio", 0),
            "npv": opp.financials.get("npv", 0),
            "signal_count": len(opp.signals),
            "created": opp.created_at,
        })

    return sorted(summaries, key=lambda x: x["score"], reverse=True)


def format_portfolio(summaries: list[dict]) -> str:
    """Format portfolio as a markdown table."""
    if not summaries:
        return "No opportunities in portfolio."

    lines = [
        "# Opportunity Portfolio",
        "",
        "| # | Name | Stage | Score | TAM | LTV/CAC | Status |",
        "|---|------|-------|-------|-----|---------|--------|",
    ]

    for i, s in enumerate(summaries, 1):
        tam_str = f"${s['tam'] / 1e6:.0f}M" if s["tam"] > 0 else "—"
        ltv_str = f"{s['ltv_cac']:.1f}x" if s["ltv_cac"] > 0 else "—"
        lines.append(
            f"| {i} | {s['name']} | {s['stage']} | {s['score']:.0f} | "
            f"{tam_str} | {ltv_str} | {s['status']} |"
        )

    active = sum(1 for s in summaries if s["status"] == "active")
    lines.extend([
        "",
        f"**Total**: {len(summaries)} opportunities ({active} active)",
    ])

    return "\n".join(lines)


def compare_opportunities(opp_ids: list[str]) -> str:
    """Compare specific opportunities side by side."""
    opps = list_opportunities()
    selected = [o for o in opps if o.id in opp_ids or o.name.lower() in [i.lower() for i in opp_ids]]

    if not selected:
        return "No matching opportunities found."

    lines = [
        "# Opportunity Comparison",
        "",
        "| Metric | " + " | ".join(o.name for o in selected) + " |",
        "|--------|" + "|".join("------" for _ in selected) + "|",
    ]

    rows = [
        ("Stage", [o.stage for o in selected]),
        ("Status", [o.status for o in selected]),
        ("TAM", [f"${o.market.get('tam', 0) / 1e6:.0f}M" for o in selected]),
        ("SAM", [f"${o.market.get('sam', 0) / 1e6:.0f}M" for o in selected]),
        ("LTV/CAC", [f"{o.financials.get('ltv_cac_ratio', 0):.1f}x" for o in selected]),
        ("NPV", [f"${o.financials.get('npv', 0):,.0f}" for o in selected]),
        ("Signals", [str(len(o.signals)) for o in selected]),
    ]

    for label, values in rows:
        lines.append(f"| {label} | " + " | ".join(values) + " |")

    return "\n".join(lines)
