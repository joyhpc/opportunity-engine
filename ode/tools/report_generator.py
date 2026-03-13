"""Report generator — aggregate stage outputs into assessment reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


STAGE_TITLES = {
    "sense": "Opportunity Sensing Report",
    "screen": "Screening Report",
    "analyze": "Deep Analysis Report",
    "validate": "Validation Report",
    "plan": "Business Plan",
    "launch": "Launch Report",
    "monitor": "Monitoring Report",
    "full": "Full Assessment Report",
}

STAGE_SECTIONS = {
    "sense": [
        ("Trend Signals", "trend_scan.md"),
        ("Industry Feed", "industry_feed.md"),
        ("Social Listening", "social_listening.md"),
        ("Tech Scan", "patent_tech_scan.md"),
        ("Opportunity Brief", "opportunity_brief.md"),
    ],
    "screen": [
        ("Market Sizing", "market_sizing.md"),
        ("Competition Scan", "competition_scan.md"),
        ("Capability Match", "capability_match.md"),
        ("Unit Economics", "rough_economics.md"),
        ("Scorecard", "scorecard.md"),
    ],
    "analyze": [
        ("Market Deep Dive", "market_deep_dive.md"),
        ("Competitor Analysis", "competitor_analysis.md"),
        ("Value Chain", "value_chain.md"),
        ("Risk Assessment", "risk_assessment.md"),
        ("Financial Model", "financial_model.md"),
    ],
    "validate": [
        ("Key Hypotheses", "hypothesis_list.md"),
        ("MVP Design", "mvp_design.md"),
        ("Test Data", "mvp_results.md"),
        ("Validation Verdict", "validation_verdict.md"),
    ],
    "plan": [
        ("Business Model", "business_model.md"),
        ("Go-to-Market", "go_to_market.md"),
        ("Resource Plan", "resource_plan.md"),
        ("Risk Mitigation", "risk_mitigation.md"),
    ],
}


def generate_stage_report(opportunity: str, stage: str,
                          input_dir: str | None = None,
                          sections_data: dict | None = None) -> str:
    """Generate a stage report from file outputs or provided data."""
    title = STAGE_TITLES.get(stage, f"{stage} Report")
    lines = [
        f"# {title}",
        f"**Opportunity**: {opportunity}",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Stage**: {stage.upper()}",
        "",
        "---",
        "",
    ]

    sections = STAGE_SECTIONS.get(stage, [])

    for section_title, filename in sections:
        lines.append(f"## {section_title}")
        lines.append("")

        content = None
        if input_dir:
            filepath = Path(input_dir) / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")

        if not content and sections_data:
            content = sections_data.get(filename)

        if content:
            lines.append(content)
        else:
            lines.append(f"*Pending — run the corresponding tool to generate `{filename}`*")

        lines.append("")

    # Decision summary
    lines.extend(["---", "", "## Decision Summary", "",
                   "| Item | Status |", "|------|--------|"])

    for section_title, filename in sections:
        has_content = False
        if input_dir:
            filepath = Path(input_dir) / filename
            has_content = filepath.exists()
        if not has_content and sections_data:
            has_content = filename in sections_data

        status = "Done" if has_content else "Pending"
        lines.append(f"| {section_title} | {status} |")

    return "\n".join(lines)


def generate_full_report(opportunity: str, input_dir: str) -> str:
    """Generate a full report aggregating all stages."""
    lines = [
        f"# {opportunity} — Full Assessment",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]

    for stage in ["sense", "screen", "analyze", "validate", "plan"]:
        stage_dir = Path(input_dir) / stage if input_dir else None
        if stage_dir and stage_dir.exists():
            lines.append(generate_stage_report(opportunity, stage, str(stage_dir)))
        else:
            lines.extend([
                f"## {STAGE_TITLES.get(stage, stage)}",
                "*Stage not completed*",
                "",
            ])

    return "\n".join(lines)


def generate_opportunity_report(opportunity_name: str,
                                stage: str,
                                scan_data: dict | None = None,
                                eval_data: dict | None = None) -> str:
    """Generate a report from in-memory worker results."""
    lines = [
        f"# {STAGE_TITLES.get(stage, stage + ' Report')}",
        f"**Opportunity**: {opportunity_name}",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Stage**: {stage.upper()}",
        "",
        "---",
        "",
    ]

    if scan_data:
        signals = scan_data.get("signals", [])
        lines.extend([
            "## Signal Summary",
            f"Total signals: {len(signals)}",
            "",
        ])
        strong = sum(1 for s in signals if s.get("strength") == "强")
        medium = sum(1 for s in signals if s.get("strength") == "中")
        lines.append(f"- Strong: {strong}")
        lines.append(f"- Medium: {medium}")
        lines.append(f"- Weak: {len(signals) - strong - medium}")
        lines.append("")

        if signals:
            lines.extend(["### Top Signals", ""])
            for s in sorted(signals, key=lambda x: {"强": 0, "中": 1, "弱": 2}.get(x.get("strength", "弱"), 3))[:10]:
                title = s.get("title") or s.get("keyword", "")
                lines.append(f"- [{s.get('strength', '?')}] {title}")
            lines.append("")

    if eval_data:
        lines.extend(["## Evaluation Summary", ""])

        if "scoring" in eval_data:
            sc = eval_data["scoring"]
            lines.append(f"**Score**: {sc.get('percentage', 0):.0f}/100 — {sc.get('verdict', 'N/A')}")
            lines.append("")

        if "market" in eval_data:
            m = eval_data["market"]
            lines.extend([
                "### Market",
                f"- TAM: ${m.get('tam', 0) / 1e6:.0f}M" if m.get("tam", 0) > 0 else "- TAM: N/A",
                f"- SAM: ${m.get('sam', 0) / 1e6:.0f}M" if m.get("sam", 0) > 0 else "- SAM: N/A",
                f"- SOM: ${m.get('som', 0) / 1e6:.0f}M" if m.get("som", 0) > 0 else "- SOM: N/A",
                "",
            ])

        if "financials" in eval_data:
            f_data = eval_data["financials"]
            lines.extend([
                "### Financials",
                f"- LTV/CAC: {f_data.get('ltv_cac_ratio', 0):.1f}x",
                f"- NPV: ${f_data.get('npv', 0):,.0f}",
                f"- Breakeven: {'M' + str(f_data['breakeven_months']) if f_data.get('breakeven_months') else 'N/A'}",
                "",
            ])

    return "\n".join(lines)
