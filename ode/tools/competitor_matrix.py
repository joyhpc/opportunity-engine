"""竞品分析矩阵 — 重构为库函数.

Generates competitor comparison matrices and positioning maps.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
import json


def load_competitor_data(path: str) -> dict:
    """Load competitor data from YAML or JSON file."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        return yaml.safe_load(content)
    return json.loads(content)


def generate_quick_matrix(data: dict) -> str:
    """Quick competitor comparison table."""
    lines = [
        "# Competitor Matrix",
        f"Domain: **{data.get('opportunity', 'N/A')}**",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    dims = data.get("dimensions", [])
    comps = data.get("competitors", [])
    if not comps:
        return "\n".join(lines + ["No competitor data available."])

    header = "| Dimension | " + " | ".join(c["name"] for c in comps) + " |"
    sep = "|-----------|" + "|".join("------" for _ in comps) + "|"
    lines.extend([header, sep])

    for dim in dims:
        row = f"| {dim} |"
        for c in comps:
            score = c.get("scores", {}).get(dim, "—")
            row += f" {score}/10 |"
        lines.append(row)

    row = "| **Total** |"
    for c in comps:
        total = sum(c.get("scores", {}).get(d, 0) for d in dims)
        row += f" **{total}/{len(dims) * 10}** |"
    lines.append(row)

    lines.extend(["", "## Pricing"])
    for c in comps:
        lines.append(f"- **{c['name']}**: {c.get('pricing', 'Unknown')}")

    return "\n".join(lines)


def generate_deep_matrix(data: dict) -> str:
    """Deep competitor analysis with detail sections."""
    lines = [
        "# Competitor Deep Analysis",
        f"Domain: **{data.get('opportunity', 'N/A')}**",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Competitors analyzed: {len(data.get('competitors', []))}",
        "",
        generate_quick_matrix(data),
        "",
        "---",
        "## Detailed Breakdown",
    ]

    for c in data.get("competitors", []):
        lines.extend([
            "",
            f"### {c['name']}",
            f"- **Type**: {c.get('type', '—')}",
            f"- **Pricing**: {c.get('pricing', '—')}",
            f"- **Users**: {c.get('users', c.get('users_estimate', '—'))}",
            "",
            "**Strengths:**",
        ])
        for s in c.get("strengths", []):
            lines.append(f"  - {s}")
        lines.append("\n**Weaknesses:**")
        for w in c.get("weaknesses", []):
            lines.append(f"  - {w}")

        dims = data.get("dimensions", [])
        lines.extend(["", "**Capability Radar:**"])
        for dim in dims:
            score = c.get("scores", {}).get(dim, 0)
            clamped = min(10, max(0, score))
            bar = "█" * clamped + "░" * (10 - clamped)
            lines.append(f"  {dim:15s} [{bar}] {score}/10")

    # Differentiation opportunities
    lines.extend(["", "---", "## Differentiation Opportunities", ""])
    dims = data.get("dimensions", [])
    comps = data.get("competitors", [])
    for dim in dims:
        scores = [c.get("scores", {}).get(dim, 0) for c in comps]
        if scores:
            avg = sum(scores) / len(scores)
            if avg < 7:
                lines.append(f"- **{dim}** (avg {avg:.1f}/10): differentiation opportunity")

    return "\n".join(lines)


def build_competitor_summary(data: dict) -> dict:
    """Extract competitor summary for opportunity scoring."""
    comps = data.get("competitors", [])
    if not comps:
        return {"count": 0, "avg_score": 0, "top_competitor": ""}

    dims = data.get("dimensions", [])
    totals = []
    for c in comps:
        total = sum(c.get("scores", {}).get(d, 0) for d in dims)
        totals.append((c["name"], total))

    totals.sort(key=lambda x: x[1], reverse=True)
    avg = sum(t for _, t in totals) / len(totals)

    return {
        "count": len(comps),
        "avg_score": round(avg, 1),
        "max_score": len(dims) * 10,
        "top_competitor": totals[0][0] if totals else "",
        "competitors": [{"name": n, "score": s} for n, s in totals],
    }
