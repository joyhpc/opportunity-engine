"""Synthesize — cross-data insight generation.

Turns raw aggregation into interpretation: finds contradictions,
blind spots, unexpected correlations, and actionable narratives.
"""

from __future__ import annotations

from datetime import datetime


def find_contradictions(opp_data: dict) -> list[dict]:
    """Find contradictions across different data dimensions.

    Returns list of {type, description, implication, suggested_action}.
    """
    contradictions = []
    scores = opp_data.get("scores", {})
    market = opp_data.get("market", {})
    financials = opp_data.get("financials", {})
    signals = opp_data.get("signals", [])
    gate_log = opp_data.get("gate_log", [])

    # 1. Big market but weak pain evidence
    tam = market.get("tam", 0)
    pain_score = scores.get("pain_evidence") or _dim_avg(scores, "Validation")
    if tam > 1e8 and pain_score and pain_score < 5:
        contradictions.append({
            "type": "market_vs_pain",
            "title": "Large market, weak pain evidence",
            "description": f"TAM is ${tam/1e6:.0f}M but pain evidence is only {pain_score}/10.",
            "implication": "A large market doesn't guarantee real demand. You might be looking at a 'nice-to-have' in a big space.",
            "action": "Run 5 user interviews focused on: 'How do you solve X today? What happens if you don't solve it?'",
        })

    # 2. High LTV/CAC but no willingness-to-pay validation
    ltv_cac = financials.get("ltv_cac_ratio", 0)
    wtp_score = scores.get("willingness_to_pay") or 5
    if ltv_cac > 3 and isinstance(wtp_score, (int, float)) and wtp_score < 4:
        contradictions.append({
            "type": "economics_vs_validation",
            "title": "Good unit economics on paper, unvalidated willingness to pay",
            "description": f"LTV/CAC is {ltv_cac:.1f}x but willingness-to-pay is {wtp_score}/10.",
            "implication": "Your financial model may be aspirational, not empirical. The churn and ARPU assumptions need real-world testing.",
            "action": "Pre-sell to 3 people at your target price before building anything.",
        })

    # 3. Strong signals but no competitors = possibly empty market
    # intensity scale: 10 = blue ocean, 7 = few, 3 = red ocean
    strong_signals = sum(1 for s in signals if s.get("strength") == "强") if isinstance(signals, list) else 0
    comp_score = scores.get("intensity") or _dim_avg(scores, "Competitive")
    if strong_signals >= 3 and comp_score and comp_score <= 4:
        contradictions.append({
            "type": "signal_vs_competition",
            "title": "Strong trend signals but no competitors",
            "description": f"{strong_signals} strong signals but competition intensity is {comp_score}/10 (high = blue ocean, low = red ocean).",
            "implication": "Beware of 'empty markets.' If smart people see the signals but aren't building here, there may be a hidden barrier (regulation, unit economics, tech feasibility).",
            "action": "Ask: why hasn't anyone built this yet? Search for failed startups in this space and learn from post-mortems.",
        })

    # 4. AI-native score high but capability low
    ai_score = scores.get("system_rethink") or _dim_avg(scores, "AI-Native")
    skill_score = scores.get("skill_match") or _dim_avg(scores, "Capability")
    if ai_score and skill_score and ai_score >= 7 and skill_score <= 4:
        contradictions.append({
            "type": "ai_ambition_vs_capability",
            "title": "High AI ambition, low skill match",
            "description": f"AI-Native potential is {ai_score}/10 but skill match is {skill_score}/10.",
            "implication": "Building an AI-native product requires AI engineering skills. Without them, you'll ship a wrapper, not a platform.",
            "action": "Either: (a) find an AI co-founder, (b) start with a simpler non-AI version, or (c) use AI APIs to bridge the gap.",
        })

    # 5. Good score but KILLED by redline
    for gate in gate_log:
        if gate.get("verdict") == "KILL" and gate.get("score", 0) > 50:
            contradictions.append({
                "type": "score_vs_redline",
                "title": "Decent score killed by redline",
                "description": f"Gate {gate.get('gate', '?')} returned KILL despite score {gate.get('score', 0)}.",
                "implication": "The overall opportunity is promising but has a fatal flaw. Fix the specific redline issue rather than abandoning the idea.",
                "action": "Review the specific redline that triggered. Can it be addressed with a pivot or partnership?",
            })

    return contradictions


def find_blind_spots(opp_data: dict) -> list[dict]:
    """Identify data gaps and unexplored areas."""
    blind_spots = []
    scores = opp_data.get("scores", {})
    market = opp_data.get("market", {})
    financials = opp_data.get("financials", {})
    signals = opp_data.get("signals", [])

    # Missing data checks
    if not market.get("tam"):
        blind_spots.append({
            "area": "Market Size",
            "severity": "high",
            "description": "No market sizing done. You're flying blind on whether this is a $1M or $1B opportunity.",
            "action": "Run: ode eval <id> --tam <estimate> --segment-pct <pct> --geo-pct <pct>",
        })

    if not financials.get("ltv") or financials.get("ltv", 0) == 0:
        blind_spots.append({
            "area": "Unit Economics",
            "severity": "high",
            "description": "No financial model. Without LTV/CAC you can't know if growth = profit or growth = loss.",
            "action": "Run: ode eval <id> --arpu <price> --cac <cost> --churn <pct>",
        })

    mvt = scores.get("mvt_result", 0)
    if isinstance(mvt, (int, float)) and mvt <= 2:
        blind_spots.append({
            "area": "Market Validation",
            "severity": "high",
            "description": "No minimum viable test (MVT) done. Everything is assumption until users vote with their wallet.",
            "action": "This week: create a landing page, drive traffic, measure signup/payment intent.",
        })

    if not signals or (isinstance(signals, list) and len(signals) == 0):
        blind_spots.append({
            "area": "Trend Signals",
            "severity": "medium",
            "description": "No signals collected. You may be operating on gut feeling alone.",
            "action": "Run: ode scan --keywords '<your keywords>'",
        })

    # Check for single-source signals
    if isinstance(signals, list) and signals:
        sources = set(s.get("source", "").split("/")[0] for s in signals)
        if len(sources) == 1:
            blind_spots.append({
                "area": "Signal Diversity",
                "severity": "medium",
                "description": f"All signals from one source ({list(sources)[0]}). Single-source analysis is biased.",
                "action": "Add more sources: --hn-top 30 --reddit 'startup,SaaS'",
            })

    # Regulatory blind spot
    domain = opp_data.get("domain", "")
    regulated_domains = ["health", "medical", "fintech", "finance", "education", "insurance"]
    if domain.lower() in regulated_domains:
        regulatory = opp_data.get("regulatory", {})
        if not regulatory.get("risks"):
            blind_spots.append({
                "area": "Regulatory Risk",
                "severity": "high",
                "description": f"Domain '{domain}' is typically regulated, but no regulatory risks are documented.",
                "action": "Research: licensing requirements, data privacy laws, industry-specific compliance.",
            })

    return blind_spots


def _dim_avg(scores: dict, dim_prefix: str) -> float | None:
    """Try to extract a dimension average from scores dict."""
    for k, v in scores.items():
        if isinstance(v, (int, float)) and dim_prefix.lower() in k.lower():
            return v
    return None


def synthesize(opp_data: dict) -> dict:
    """Run full synthesis: contradictions + blind spots + narrative."""
    contradictions = find_contradictions(opp_data)
    blind_spots = find_blind_spots(opp_data)

    # Generate overall narrative
    score = opp_data.get("scores", {}).get("_weighted_pct", 0)
    stage = opp_data.get("stage", "SENSE")

    if contradictions:
        narrative = (
            f"This opportunity has {len(contradictions)} internal contradiction(s) "
            f"that need resolution before advancing. The data tells conflicting stories — "
            f"resolve these before trusting the score."
        )
    elif blind_spots and any(b["severity"] == "high" for b in blind_spots):
        narrative = (
            f"Key data is missing. The current score ({score:.0f}/100) is based on "
            f"incomplete information. Fill the blind spots before making a decision."
        )
    elif score >= 70:
        narrative = (
            f"This opportunity scores well ({score:.0f}/100) with no major contradictions. "
            f"Focus on validation: can you get 3 people to pay?"
        )
    elif score >= 50:
        narrative = (
            f"Borderline opportunity ({score:.0f}/100). The potential is there but not proven. "
            f"Set a 2-week time box to address the weakest dimension."
        )
    else:
        narrative = (
            f"Below threshold ({score:.0f}/100). Consider pivoting or reframing "
            f"rather than pushing forward with the current positioning."
        )

    return {
        "narrative": narrative,
        "contradictions": contradictions,
        "blind_spots": blind_spots,
        "contradiction_count": len(contradictions),
        "blind_spot_count": len(blind_spots),
        "high_severity_gaps": sum(1 for b in blind_spots if b["severity"] == "high"),
    }


def format_synthesis_report(synthesis: dict) -> str:
    """Format synthesis as readable report."""
    lines = [
        "# Opportunity Insights",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## Overall Assessment",
        "",
        synthesis["narrative"],
        "",
    ]

    # Contradictions
    if synthesis["contradictions"]:
        lines.extend([
            f"## Contradictions ({synthesis['contradiction_count']})",
            "",
            "These are internal inconsistencies in your data that need resolution.",
            "",
        ])
        for i, c in enumerate(synthesis["contradictions"], 1):
            lines.extend([
                f"### {i}. {c['title']}",
                "",
                c["description"],
                "",
                f"**So what?** {c['implication']}",
                "",
                f"**Do this:** {c['action']}",
                "",
            ])

    # Blind spots
    if synthesis["blind_spots"]:
        lines.extend([
            f"## Blind Spots ({synthesis['blind_spot_count']})",
            "",
        ])
        for b in synthesis["blind_spots"]:
            severity_tag = "[!]" if b["severity"] == "high" else "[?]"
            lines.extend([
                f"- {severity_tag} **{b['area']}**: {b['description']}",
                f"  Action: {b['action']}",
            ])
        lines.append("")

    if not synthesis["contradictions"] and not synthesis["blind_spots"]:
        lines.append("No contradictions or blind spots detected. Data looks consistent.")

    return "\n".join(lines)
