"""Bridge — auto-infer initial scores from scan signals.

Solves the gap between "I have signals" and "I need to rate 18 criteria
on a 1-10 scale." Users can override any auto-inferred score.
"""

from __future__ import annotations

import re
from collections import Counter


# ---------------------------------------------------------------------------
# Signal-to-score inference rules
# ---------------------------------------------------------------------------

# Each rule: given signal data, infer a criterion score (1-10)
# These are heuristics, not ground truth. The user always overrides.

def _count_by_strength(signals: list[dict]) -> tuple[int, int, int]:
    strong = sum(1 for s in signals if s.get("strength") == "强")
    medium = sum(1 for s in signals if s.get("strength") == "中")
    weak = len(signals) - strong - medium
    return strong, medium, weak


def _source_diversity(signals: list[dict]) -> int:
    sources = set(s.get("source", "").split("/")[0] for s in signals)
    return len(sources)


def _avg_momentum(signals: list[dict]) -> float:
    vals = [s.get("momentum", 0) for s in signals if s.get("momentum", 0) != 0]
    return sum(vals) / len(vals) if vals else 0


def _has_keywords(signals: list[dict], keywords: list[str]) -> bool:
    all_text = " ".join(
        f"{s.get('title', '')} {s.get('keyword', '')}" for s in signals
    ).lower()
    # Pad for boundary-aware keywords like " vs "
    padded = f" {all_text} "
    return any(kw.lower() in padded for kw in keywords)


def infer_scores(signals: list[dict],
                 domain: str = "",
                 market_data: dict | None = None,
                 financial_data: dict | None = None) -> dict:
    """Infer initial opportunity scores from available data.

    Returns a dict of criterion_id -> (score, confidence, reasoning).
    confidence is "auto" (heuristic) or "data" (from numbers).
    """
    scores = {}
    strong, medium, weak = _count_by_strength(signals)
    total = len(signals)
    diversity = _source_diversity(signals)
    momentum = _avg_momentum(signals)

    # ── Market Attractiveness ──────────────────────────────

    # tam_size: infer from signal volume and diversity
    if market_data and market_data.get("tam", 0) > 0:
        tam = market_data["tam"]
        if tam >= 1e9:
            s = 10
        elif tam >= 1e8:
            s = 7
        elif tam >= 1e7:
            s = 4
        else:
            s = 2
        scores["tam_size"] = (s, "data", f"TAM=${tam/1e6:.0f}M")
    else:
        # Heuristic: many signals from diverse sources = likely large market
        if total >= 20 and diversity >= 3:
            s = 7
        elif total >= 10:
            s = 5
        elif total >= 5:
            s = 4
        else:
            s = 3
        scores["tam_size"] = (s, "auto", f"{total} signals from {diversity} sources")

    # growth: infer from momentum
    if momentum > 50:
        s = 9
    elif momentum > 30:
        s = 7
    elif momentum > 10:
        s = 5
    elif momentum > 0:
        s = 4
    else:
        s = 3
    scores["growth"] = (s, "auto", f"avg momentum {momentum:.0f}%")

    # timing: infer from signal recency and strength distribution
    if strong >= 5:
        s = 9  # lots of strong signals = early growth phase
    elif strong >= 2:
        s = 7
    elif medium >= 5:
        s = 5  # many medium signals = mainstream
    else:
        s = 4
    scores["timing"] = (s, "auto", f"strong={strong} medium={medium}")

    # ── Competitive Landscape ──────────────────────────────

    # intensity: hard to infer from signals alone, default moderate
    competitor_keywords = [" vs ", "alternative", "competitor", "better than",
                          "compared to", "switch from"]
    has_comp_signals = _has_keywords(signals, competitor_keywords)
    if has_comp_signals:
        s = 4  # competition discussion = competitive market
    else:
        s = 6  # no competition chatter = possibly less crowded
    scores["intensity"] = (s, "auto",
        "competition keywords found" if has_comp_signals else "no competition chatter detected")

    # barrier: default moderate (hard to infer)
    scores["barrier"] = (6, "auto", "default — needs manual assessment")

    # moat_potential: check for network-effect / data keywords
    moat_keywords = ["network effect", "data flywheel", "marketplace",
                     "platform", "community", "ecosystem"]
    has_moat = _has_keywords(signals, moat_keywords)
    scores["moat_potential"] = (7 if has_moat else 4, "auto",
        "moat indicators found" if has_moat else "no moat indicators — needs validation")

    # ── Capability Fit ─────────────────────────────────────
    # Cannot infer from signals — use safe defaults
    scores["skill_match"] = (5, "auto", "needs manual assessment of your skills")
    scores["resource_need"] = (5, "auto", "needs manual assessment")
    scores["time_to_market"] = (5, "auto", "needs manual assessment")

    # ── Economic Viability ─────────────────────────────────

    if financial_data:
        ltv_cac = financial_data.get("ltv_cac_ratio", 0)
        if ltv_cac > 5:
            scores["ltv_cac"] = (10, "data", f"LTV/CAC={ltv_cac:.1f}x")
        elif ltv_cac > 3:
            scores["ltv_cac"] = (8, "data", f"LTV/CAC={ltv_cac:.1f}x")
        elif ltv_cac > 1:
            scores["ltv_cac"] = (5, "data", f"LTV/CAC={ltv_cac:.1f}x")
        else:
            scores["ltv_cac"] = (2, "data", f"LTV/CAC={ltv_cac:.1f}x")

        cogs_pct = financial_data.get("cogs_pct", 20)
        margin = financial_data.get("gross_margin_pct",
            (100 - cogs_pct) if financial_data.get("arpu") else 0)
        if margin > 80:
            scores["margin"] = (10, "data", f"margin={margin:.0f}%")
        elif margin > 60:
            scores["margin"] = (8, "data", f"margin={margin:.0f}%")
        elif margin > 40:
            scores["margin"] = (5, "data", f"margin={margin:.0f}%")
        else:
            scores["margin"] = (2, "data", f"margin={margin:.0f}%")

        payback = financial_data.get("payback_months", 0)
        if payback and payback < 3:
            scores["payback"] = (9, "data", f"payback={payback:.0f}mo")
        elif payback and payback < 6:
            scores["payback"] = (6, "data", f"payback={payback:.0f}mo")
        elif payback and payback < 12:
            scores["payback"] = (4, "data", f"payback={payback:.0f}mo")
        else:
            scores["payback"] = (5, "auto", "no financial data yet")
    else:
        # SaaS defaults if domain suggests software
        software_kw = ["saas", "app", "platform", "tool", "software", "ai", "api"]
        is_software = _has_keywords(signals, software_kw) or domain in ("devtools", "saas", "ai_ml")
        if is_software:
            scores["ltv_cac"] = (6, "auto", "SaaS typical assumption")
            scores["margin"] = (8, "auto", "software = high margin assumption")
            scores["payback"] = (6, "auto", "SaaS typical assumption")
        else:
            scores["ltv_cac"] = (5, "auto", "no financial data — needs estimation")
            scores["margin"] = (5, "auto", "no financial data — needs estimation")
            scores["payback"] = (5, "auto", "no financial data — needs estimation")

    # ── Validation Strength ────────────────────────────────

    # pain_evidence: check for pain-related keywords in signals
    pain_keywords = ["frustrated", "hate", "broken", "painful", "annoying",
                     "need", "help", "struggle", "problem", "issue",
                     "wish", "want", "looking for", "seeking"]
    has_pain = _has_keywords(signals, pain_keywords)
    if has_pain and strong >= 2:
        scores["pain_evidence"] = (7, "auto", "pain signals detected in strong discussions")
    elif has_pain:
        scores["pain_evidence"] = (5, "auto", "some pain signals detected")
    else:
        scores["pain_evidence"] = (3, "auto", "no pain signals — needs user interviews")

    scores["willingness_to_pay"] = (3, "auto", "cannot infer from signals — needs validation")
    scores["mvt_result"] = (1, "auto", "untested — no MVT data available")

    # ── AI-Native Potential ────────────────────────────────

    ai_keywords = ["ai", "llm", "gpt", "machine learning", "model",
                   "neural", "agent", "copilot", "automation"]
    ai_density = sum(1 for s in signals if _has_keywords([s], ai_keywords))
    ai_ratio = ai_density / max(total, 1)

    if ai_ratio > 0.5:
        scores["system_rethink"] = (8, "auto", f"{ai_ratio:.0%} signals are AI-related")
        scores["data_loop"] = (6, "auto", "AI-heavy space likely has data flywheel potential")
        scores["compound_advantage"] = (7, "auto", "AI reinforcement likely")
    elif ai_ratio > 0.2:
        scores["system_rethink"] = (6, "auto", f"{ai_ratio:.0%} AI signals — moderate AI opportunity")
        scores["data_loop"] = (5, "auto", "some AI presence")
        scores["compound_advantage"] = (5, "auto", "partial AI advantage")
    else:
        scores["system_rethink"] = (4, "auto", "low AI signal density")
        scores["data_loop"] = (4, "auto", "no clear data flywheel signal")
        scores["compound_advantage"] = (4, "auto", "AI may be optional for this space")

    return scores


def scores_to_flat(inferred: dict) -> dict:
    """Convert inferred scores dict to flat {criterion_id: score} for scorer."""
    return {k: v[0] for k, v in inferred.items()}


def quick_assess(signals: list[dict],
                 domain: str = "",
                 market_data: dict | None = None) -> dict:
    """Early-stage binary assessment — replaces meaningless 55-65 scores.

    Instead of 1-10 scales that cluster around 5, uses categorical
    judgments that are actually useful for comparison.
    """
    all_text = " ".join(
        f"{s.get('title', '')} {s.get('keyword', '')}" for s in signals
    ).lower()

    # -- can_you_do_it --
    software_domains = {"devtools", "saas", "ai_ml", "creator", "ecommerce"}
    regulated_domains = {"health", "fintech", "climate"}
    if domain in software_domains:
        can_do = "yes"
    elif domain in regulated_domains:
        can_do = "need_partner"
    else:
        # Check signal text for software vs regulated hints
        sw_kw = ["saas", "app", "platform", "tool", "software", "api", "code"]
        reg_kw = ["medical", "clinic", "bank", "compliance", "regulation", "fda"]
        if any(kw in all_text for kw in reg_kw):
            can_do = "need_partner"
        elif any(kw in all_text for kw in sw_kw):
            can_do = "yes"
        else:
            can_do = "yes"  # default optimistic for unknown

    # -- existing_revenue_proof --
    revenue_kw = ["pricing", "revenue", "arr", "paid", "customers", "mrr",
                  "subscription", "paying", "price", "monetiz"]
    has_revenue = any(kw in all_text for kw in revenue_kw)

    # -- days_to_first_test --
    hw_domains = {"hardware", "robotics", "climate"}
    if domain in hw_domains:
        days = "<90"
    elif domain in software_domains:
        days = "<7"
    else:
        days = "<30"

    # -- competition_density --
    comp_kw = [" vs ", "alternative", "competitor", "better than",
               "compared to", "switch from", "instead of"]
    # Pad text for word-boundary matching
    padded_text = f" {all_text} "
    comp_count = sum(1 for kw in comp_kw if kw in padded_text)
    # Boost from market_data if available
    if market_data and market_data.get("competitors"):
        comp_count += min(market_data["competitors"], 6)
    if comp_count == 0:
        density = "empty"
    elif comp_count <= 2:
        density = "sparse"
    elif comp_count <= 5:
        density = "crowded"
    else:
        density = "dominated"

    # -- user_urgency --
    fire_kw = ["urgent", "broken", "stuck", "critical", "emergency",
               "asap", "desperate", "nightmare", "can't work"]
    nice_kw = ["would be nice", "cool if", "maybe someday", "nice to have",
               "eventually"]
    pain_kw = ["frustrated", "hate", "painful", "annoying", "struggle",
               "problem", "issue", "need help"]
    if any(kw in all_text for kw in fire_kw):
        urgency = "hair_on_fire"
    elif any(kw in all_text for kw in pain_kw):
        urgency = "nice_to_have"
    elif any(kw in all_text for kw in nice_kw):
        urgency = "meh"
    else:
        urgency = "meh"

    # -- reasoning --
    reasoning = {
        "can_you_do_it": f"domain={domain or 'unknown'}",
        "existing_revenue_proof": "revenue keywords found" if has_revenue else "no revenue signals",
        "days_to_first_test": f"based on domain={domain or 'general'}",
        "competition_density": f"{comp_count} competition keywords matched",
        "user_urgency": f"inferred from signal text patterns",
    }

    return {
        "can_you_do_it": can_do,
        "existing_revenue_proof": "yes" if has_revenue else "no",
        "days_to_first_test": days,
        "competition_density": density,
        "user_urgency": urgency,
        "reasoning": reasoning,
    }


def format_quick_assess_report(assessment: dict) -> str:
    """Format quick assessment as a readable summary."""
    icons = {
        "can_you_do_it": {"yes": "YES", "need_partner": "NEED PARTNER", "no": "NO"},
        "existing_revenue_proof": {"yes": "YES", "no": "NO"},
        "days_to_first_test": {"<7": "<7 days", "<30": "<30 days", "<90": "<90 days"},
        "competition_density": {"empty": "EMPTY", "sparse": "SPARSE", "crowded": "CROWDED", "dominated": "DOMINATED"},
        "user_urgency": {"hair_on_fire": "HAIR ON FIRE", "nice_to_have": "NICE TO HAVE", "meh": "MEH"},
    }

    lines = [
        "# Quick Assessment (Early Stage)",
        "",
        "Binary/categorical judgments — more useful than 1-10 scales at this stage.",
        "",
        "| Question | Answer | Reasoning |",
        "|----------|--------|-----------|",
    ]

    labels = {
        "can_you_do_it": "Can you build this?",
        "existing_revenue_proof": "Revenue proof exists?",
        "days_to_first_test": "Days to first test?",
        "competition_density": "Competition density?",
        "user_urgency": "User urgency?",
    }

    reasoning = assessment.get("reasoning", {})
    for field, label in labels.items():
        val = assessment.get(field, "?")
        display = icons.get(field, {}).get(val, val)
        reason = reasoning.get(field, "")
        lines.append(f"| {label} | **{display}** | {reason} |")

    # Summary verdict
    lines.append("")
    green = 0
    if assessment.get("can_you_do_it") == "yes":
        green += 1
    if assessment.get("existing_revenue_proof") == "yes":
        green += 1
    if assessment.get("days_to_first_test") == "<7":
        green += 1
    if assessment.get("competition_density") in ("empty", "sparse"):
        green += 1
    if assessment.get("user_urgency") == "hair_on_fire":
        green += 1

    if green >= 4:
        lines.append("**Summary: Strong early signal — worth a 1-week sprint.**")
    elif green >= 2:
        lines.append("**Summary: Mixed signals — investigate the weak areas before committing.**")
    else:
        lines.append("**Summary: Weak early signal — consider pivoting or gathering more data.**")

    return "\n".join(lines)


def format_bridge_report(inferred: dict) -> str:
    """Format inferred scores with confidence and reasoning."""
    lines = [
        "# Auto-Inferred Scores",
        "",
        "These scores are heuristic estimates from signal analysis.",
        "Override any that don't match your knowledge.",
        "",
        "| Criterion | Score | Source | Reasoning |",
        "|-----------|-------|--------|-----------|",
    ]

    for crit_id, (score, confidence, reason) in inferred.items():
        conf_icon = "[ data ]" if confidence == "data" else "[ auto ]"
        lines.append(f"| {crit_id} | {score}/10 | {conf_icon} | {reason} |")

    auto_count = sum(1 for _, (_, c, _) in inferred.items() if c == "auto")
    data_count = len(inferred) - auto_count

    lines.extend([
        "",
        f"**{data_count} scores from data, {auto_count} auto-inferred.**",
        "",
        "To override: `ode eval <id> --scores '{\"criterion\": value, ...}'`",
        "Only include the scores you want to change — auto scores fill the rest.",
    ])

    return "\n".join(lines)
