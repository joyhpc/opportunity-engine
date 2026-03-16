"""Explore — open-ended opportunity discovery for users in a fuzzy state.

No keywords needed. Scans HN/Reddit/Trends hot topics, clusters them
into themes, and outputs ranked opportunity hypotheses.

This is the "I don't know what to build" entry point.
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from datetime import datetime


# ---------------------------------------------------------------------------
# Signal clustering (no ML deps — pure text heuristics)
# ---------------------------------------------------------------------------

# Domain seed words for clustering unstructured signals
DOMAIN_SEEDS = {
    "health": ["health", "medical", "clinic", "patient", "therapy", "mental",
               "wellness", "biotech", "diagnosis", "care", "elder", "aging",
               "fitness", "nutrition", "sleep", "brain", "cognitive"],
    "education": ["learn", "teach", "student", "course", "tutor", "school",
                  "education", "training", "skill", "mentor", "child",
                  "language", "curriculum", "university", "mooc"],
    "fintech": ["finance", "bank", "payment", "invest", "crypto", "trading",
                "insurance", "loan", "credit", "wallet", "defi", "wealth"],
    "devtools": ["developer", "api", "code", "programming", "devops", "ci/cd",
                 "testing", "debug", "deploy", "infrastructure", "sdk",
                 "open source", "github", "database", "cloud"],
    "ai_ml": ["ai", "llm", "gpt", "machine learning", "model", "neural",
              "transformer", "agent", "prompt", "inference", "fine-tune",
              "rag", "embedding", "diffusion", "copilot", "chatbot"],
    "hardware": ["fpga", "pcb", "schematic", "circuit", "eda", "embedded",
                 "signal integrity", "power", "voltage", "gpio", "uart",
                 "spi", "layout", "bom", "gerber", "review", "simulation",
                 "oscilloscope", "soldering", "prototype", "ddr", "jtag",
                 "design rule", "impedance", "decoupling", "capacitor",
                 "resistor", "inductor", "mosfet", "transistor", "ic",
                 "sensor", "actuator", "motor", "antenna", "rf",
                 "microcontroller", "mcu", "soc", "asic", "chip",
                 "verification", "timing", "clock", "pll", "adc", "dac",
                 "thermal", "emc", "compliance", "certification",
                 "hardware", "electronics", "electrical", "board"],
    "robotics": ["robot", "robotics", "ros", "autonomous", "drone", "lidar",
                 "slam", "manipulator", "servo", "actuator", "motion",
                 "control system", "pid", "kinematics"],
    "creator": ["creator", "content", "video", "podcast", "newsletter",
                "community", "audience", "monetize", "subscription",
                "social media", "influencer", "brand"],
    "saas": ["saas", "b2b", "enterprise", "crm", "erp", "workflow",
             "automation", "integration", "platform", "dashboard",
             "analytics", "collaboration", "productivity"],
    "ecommerce": ["ecommerce", "shop", "retail", "marketplace", "product",
                  "shipping", "supply chain", "inventory", "dropship",
                  "d2c", "brand", "commerce"],
    "climate": ["climate", "energy", "solar", "battery", "carbon", "ev",
                "sustainable", "green", "renewable", "emission", "recycl"],
}


def _tokenize_signal(signal: dict) -> list[str]:
    """Extract lowercase tokens from a signal's title and keyword."""
    text = f"{signal.get('title', '')} {signal.get('keyword', '')}".lower()
    return re.findall(r'[a-z\u4e00-\u9fff]{2,}', text)


def _classify_domain(signal: dict) -> tuple[str, int]:
    """Classify a signal into the best-matching domain.

    Returns (domain, overlap_count). Falls back to ("emerging", 0).
    """
    tokens = set(_tokenize_signal(signal))
    best_domain = "emerging"
    best_overlap = 0

    for domain, seeds in DOMAIN_SEEDS.items():
        overlap = len(tokens & set(seeds))
        if overlap > best_overlap:
            best_overlap = overlap
            best_domain = domain

    return best_domain, best_overlap


def cluster_signals(signals: list[dict]) -> dict[str, list[dict]]:
    """Cluster signals into domain themes using seed-word matching.

    Returns {domain: [signals]} sorted by cluster size descending.
    Signals matching no domain go into "emerging" (the interesting ones).
    """
    clusters: dict[str, list[dict]] = defaultdict(list)

    for sig in signals:
        domain, _ = _classify_domain(sig)
        clusters[domain].append(sig)

    # Sort by cluster size
    return dict(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True))


# ---------------------------------------------------------------------------
# Demand-pattern clustering (second dimension beyond domain)
# ---------------------------------------------------------------------------

DEMAND_PATTERNS = {
    "decision_proxy": ["help me choose", "which one", "best for", "should i buy",
                       "recommend me", "picking between"],
    "comparison":     [" vs ", "versus", "compared to", "better than",
                       "worth it", "difference between"],
    "capability_gap": ["how to", "how do i", "help with", "tutorial",
                       "guide", "getting started", "need help"],
    "avoidance":      ["scam", "waste", "regret", "avoid", "don't buy",
                       "not worth", "terrible", "warning", "ripoff"],
    "info_gap":       ["wish i knew", "didn't know", "nobody tells",
                       "hidden", "secret", "underrated", "overlooked"],
    "curation":       ["recommend", "best", "suggest", "top", "favorite",
                       "curated", "list of"],
}


def classify_demand_pattern(signal: dict) -> str:
    """Classify a single signal into a demand pattern.

    Returns the best-matching pattern key, or "unclassified".
    """
    # Pad with spaces so boundary-aware patterns like " vs " work at edges
    text = f" {signal.get('title', '')} {signal.get('keyword', '')} ".lower()

    best_pattern = "unclassified"
    best_count = 0

    for pattern, phrases in DEMAND_PATTERNS.items():
        count = sum(1 for p in phrases if p in text)
        if count > best_count:
            best_count = count
            best_pattern = pattern

    return best_pattern


def cluster_by_demand(signals: list[dict]) -> dict[str, list[dict]]:
    """Cluster signals by demand pattern.

    Returns {pattern: [signals]} sorted by cluster size descending.
    """
    clusters: dict[str, list[dict]] = defaultdict(list)

    for sig in signals:
        pattern = classify_demand_pattern(sig)
        clusters[pattern].append(sig)

    return dict(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True))


def build_demand_matrix(signals: list[dict]) -> dict:
    """Build a domain x demand-pattern matrix.

    Returns:
        {
            "matrix": {domain: {pattern: count}},
            "domain_totals": {domain: count},
            "pattern_totals": {pattern: count},
            "hotspots": [(domain, pattern, count), ...],  # sorted desc
        }
    """
    matrix: dict[str, Counter] = defaultdict(Counter)
    domain_totals: Counter = Counter()
    pattern_totals: Counter = Counter()

    for sig in signals:
        domain, _ = _classify_domain(sig)
        pattern = classify_demand_pattern(sig)

        matrix[domain][pattern] += 1
        domain_totals[domain] += 1
        pattern_totals[pattern] += 1

    # Find hotspots (cells with count >= 2)
    hotspots = []
    for domain, patterns in matrix.items():
        for pattern, count in patterns.items():
            if count >= 2:
                hotspots.append((domain, pattern, count))
    hotspots.sort(key=lambda x: x[2], reverse=True)

    return {
        "matrix": {d: dict(p) for d, p in matrix.items()},
        "domain_totals": dict(domain_totals),
        "pattern_totals": dict(pattern_totals),
        "hotspots": hotspots,
    }


def _extract_themes(cluster: list[dict], top_n: int = 5) -> list[str]:
    """Extract top recurring themes (bigrams/keywords) from a cluster."""
    word_freq: Counter = Counter()
    stop = {"the", "and", "for", "with", "that", "this", "from", "are",
            "was", "has", "have", "not", "but", "how", "what", "why",
            "your", "you", "can", "will", "just", "about", "more",
            "new", "use", "one", "all", "get", "its"}

    for sig in cluster:
        tokens = _tokenize_signal(sig)
        meaningful = [t for t in tokens if t not in stop and len(t) > 2]
        word_freq.update(meaningful)

    return [word for word, _ in word_freq.most_common(top_n)]


# ---------------------------------------------------------------------------
# Opportunity hypothesis generation
# ---------------------------------------------------------------------------

def generate_hypotheses(clusters: dict[str, list[dict]],
                        min_signals: int = 2,
                        demand_clusters: dict[str, list[dict]] | None = None,
                        demand_matrix: dict | None = None) -> list[dict]:
    """Generate opportunity hypotheses from signal clusters.

    Each hypothesis captures:
    - domain, themes, signal_count, strength profile
    - a human-readable hypothesis statement
    - suggested next steps
    - (optional) dominant demand need and need-aware next steps
    """
    hypotheses = []

    for domain, signals in clusters.items():
        if len(signals) < min_signals:
            continue

        themes = _extract_themes(signals)
        strong = sum(1 for s in signals if s.get("strength") == "强")
        medium = sum(1 for s in signals if s.get("strength") == "中")

        # Sources diversity
        sources = set(s.get("source", "").split("/")[0] for s in signals)

        # Momentum (avg of non-zero)
        momentums = [s.get("momentum", 0) for s in signals if s.get("momentum", 0) != 0]
        avg_momentum = sum(momentums) / len(momentums) if momentums else 0

        # Confidence: more signals + more sources + more strong = higher
        confidence = min(10, (
            len(signals) * 0.5 +
            strong * 2 +
            medium * 0.5 +
            len(sources) * 1.5 +
            (1 if avg_momentum > 30 else 0)
        ))

        # Build hypothesis statement
        theme_str = " + ".join(themes[:3])
        if domain == "emerging":
            hypothesis = f"Emerging pattern around [{theme_str}] — cross-domain signal cluster worth investigating"
        else:
            hypothesis = f"{domain.replace('_', ' ').title()} opportunity: [{theme_str}] — {len(signals)} signals from {len(sources)} source(s)"

        # Determine dominant demand pattern for this cluster
        dominant_need = ""
        if demand_matrix and demand_matrix.get("matrix", {}).get(domain):
            pattern_counts = demand_matrix["matrix"][domain]
            if pattern_counts:
                dominant_need = max(pattern_counts, key=pattern_counts.get)

        # Suggest next steps based on confidence
        need_aware_steps = {
            "decision_proxy": "Build a recommendation/comparison tool for this niche",
            "comparison": "Create a structured comparison framework users can trust",
            "capability_gap": "Ship a tutorial or getting-started guide as lead magnet",
            "avoidance": "Build a trust/verification layer (reviews, certifications)",
            "info_gap": "Curate the hidden knowledge into an accessible resource",
            "curation": "Start a curated list or newsletter in this space",
        }

        if confidence >= 7:
            next_steps = [
                f"Create opportunity: ode create --name \"{themes[0]}\" --domain \"{domain}\" --keywords \"{','.join(themes[:3])}\"",
                "Run deep scan with domain-specific subreddits",
                "Check competitors in this space",
            ]
        elif confidence >= 4:
            next_steps = [
                f"Investigate further: ode scan --keywords \"{','.join(themes[:3])}\"",
                "Look for pain points in related communities",
                "Talk to 3 potential users in this space",
            ]
        else:
            next_steps = [
                "Monitor for 1-2 weeks before investing time",
                "Set up a Google Alert for key terms",
            ]

        # Add demand-aware step if available
        if dominant_need and dominant_need in need_aware_steps:
            next_steps.insert(0, f"[{dominant_need}] {need_aware_steps[dominant_need]}")

        hypotheses.append({
            "domain": domain,
            "themes": themes,
            "hypothesis": hypothesis,
            "signal_count": len(signals),
            "strong_signals": strong,
            "sources": sorted(sources),
            "avg_momentum": round(avg_momentum, 1),
            "confidence": round(confidence, 1),
            "next_steps": next_steps,
            "dominant_need": dominant_need,
            "top_signals": sorted(signals,
                key=lambda s: {"强": 0, "中": 1, "弱": 2}.get(s.get("strength", "弱"), 3))[:5],
        })

    # Sort by confidence
    hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
    return hypotheses


# ---------------------------------------------------------------------------
# Main exploration flow
# ---------------------------------------------------------------------------

_DEFAULT_SUBS = [
    "startup", "SaaS", "Entrepreneur", "sideproject",
    "artificial", "MachineLearning",
]


def explore(signals: list[dict],
            hn_top: int = 30,
            subreddits: list[str] | None = None,
            keywords: list[str] | None = None) -> dict:
    """Run exploration on pre-fetched signals (pure computation, no I/O).

    ``signals`` is the list of raw signal dicts.  The remaining keyword
    arguments are accepted for backwards-compatibility but ignored when
    *signals* is non-empty.  When *signals* is empty the function returns
    a ``no_signals`` result.
    """
    if not signals:
        return {
            "status": "no_signals",
            "message": "No signals found. Try different subreddits or check network.",
            "clusters": {},
            "hypotheses": [],
        }

    clusters = cluster_signals(signals)
    demand_clusters_result = cluster_by_demand(signals)
    demand_matrix_result = build_demand_matrix(signals)
    hypotheses = generate_hypotheses(
        clusters,
        demand_clusters=demand_clusters_result,
        demand_matrix=demand_matrix_result,
    )

    return {
        "status": "ok",
        "total_signals": len(signals),
        "cluster_count": len(clusters),
        "hypotheses": hypotheses,
        "clusters": {k: len(v) for k, v in clusters.items()},
        "demand_clusters": {k: len(v) for k, v in demand_clusters_result.items()},
        "demand_matrix": demand_matrix_result,
    }


def explore_with_fetch(hn_top: int = 30,
                       subreddits: list[str] | None = None,
                       keywords: list[str] | None = None) -> dict:
    """Convenience wrapper: fetch signals then run explore().

    This is the I/O-inclusive version for CLI / direct use.
    """
    from ..tools.trend_scanner import scan_all

    subs = subreddits or _DEFAULT_SUBS
    signals = scan_all(
        keywords=keywords,
        hn_top=hn_top or 30,
        subreddits=subs,
    )
    return explore(signals)


def format_exploration_report(result: dict) -> str:
    """Format exploration results as a readable report."""
    if result.get("status") != "ok":
        return result.get("message", "Exploration failed.")

    lines = [
        "# Opportunity Exploration Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Signals scanned: {result['total_signals']}",
        f"Themes found: {result['cluster_count']}",
        "",
    ]

    # Cluster overview
    lines.extend(["## Signal Landscape", ""])
    for domain, count in sorted(result["clusters"].items(),
                                 key=lambda x: x[1], reverse=True):
        bar = "█" * min(count, 30)
        label = domain.replace("_", " ").title()
        lines.append(f"  {label:15s} {bar} ({count})")
    lines.append("")

    # Demand landscape
    demand_clusters = result.get("demand_clusters", {})
    if demand_clusters:
        # Show classified patterns first, unclassified at bottom (de-emphasized)
        classified = {k: v for k, v in demand_clusters.items() if k != "unclassified"}
        unclassified_count = demand_clusters.get("unclassified", 0)
        if classified:
            lines.extend(["## Demand Landscape", ""])
            for pattern, count in sorted(classified.items(),
                                          key=lambda x: x[1], reverse=True):
                bar = "█" * min(count, 30)
                label = pattern.replace("_", " ").title()
                lines.append(f"  {label:20s} {bar} ({count})")
            if unclassified_count:
                lines.append(f"  {'Unclassified':20s} {'░' * min(unclassified_count, 30)} ({unclassified_count})")
            lines.append("")

    # Domain x Need Matrix
    demand_matrix = result.get("demand_matrix", {})
    if demand_matrix and demand_matrix.get("matrix"):
        matrix = demand_matrix["matrix"]
        all_patterns = sorted(demand_matrix.get("pattern_totals", {}).keys())
        # Filter out unclassified from matrix display
        all_patterns = [p for p in all_patterns if p != "unclassified"]
        if all_patterns:
            # Readable abbreviations for column headers
            _abbrev = {
                "decision_proxy": "decide",
                "comparison": "compare",
                "capability_gap": "howto",
                "avoidance": "avoid",
                "info_gap": "info",
                "curation": "curate",
            }
            lines.extend(["## Domain x Need Matrix", ""])
            # Header
            header = "| Domain      |"
            sep = "|-------------|"
            for p in all_patterns:
                col = _abbrev.get(p, p[:7])
                header += f" {col:>7s} |"
                sep += "---------|"
            lines.append(header)
            lines.append(sep)
            # Rows
            for domain in sorted(matrix.keys()):
                label = domain.replace("_", " ").title()[:12]
                row = f"| {label:<11s} |"
                for p in all_patterns:
                    count = matrix[domain].get(p, 0)
                    cell = f"{count}" if count > 0 else "·"
                    row += f" {cell:>7s} |"
                lines.append(row)
            lines.append("")

            # Hotspots
            hotspots = demand_matrix.get("hotspots", [])
            if hotspots:
                lines.append("**Hotspots** (domain + need with 2+ signals):")
                for domain, pattern, count in hotspots[:5]:
                    lines.append(f"  - {domain} x {pattern}: {count} signals")
                lines.append("")

    # Hypotheses
    hypotheses = result.get("hypotheses", [])
    if not hypotheses:
        lines.append("No strong opportunity hypotheses found. Try scanning more sources.")
        return "\n".join(lines)

    lines.extend(["## Opportunity Hypotheses", ""])

    for i, h in enumerate(hypotheses, 1):
        conf_bar = "●" * int(h["confidence"]) + "○" * (10 - int(h["confidence"]))
        lines.extend([
            f"### {i}. {h['hypothesis']}",
            f"Confidence: [{conf_bar}] {h['confidence']}/10",
            f"Signals: {h['signal_count']} (strong={h['strong_signals']})",
            f"Sources: {', '.join(h['sources'])}",
            f"Themes: {', '.join(h['themes'])}",
        ])
        if h.get("dominant_need"):
            lines.append(f"Dominant need: **{h['dominant_need'].replace('_', ' ').title()}**")
        lines.append("")

        # Top signals
        if h.get("top_signals"):
            lines.append("**Key signals:**")
            for s in h["top_signals"][:3]:
                title = s.get("title") or s.get("keyword", "")
                lines.append(f"  - [{s.get('strength', '?')}] {title[:80]}")
            lines.append("")

        # Next steps
        lines.append("**Next steps:**")
        for step in h["next_steps"]:
            lines.append(f"  {step}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Footer
    lines.extend([
        "## How to use these results",
        "",
        "1. Pick the hypothesis that resonates most with your skills/interests",
        "2. Run the suggested `ode create` + `ode scan` commands",
        "3. Use `ode eval` to score it (or let auto-scoring do a first pass)",
        "4. The engine will guide you through SCREEN -> ANALYZE -> VALIDATE",
        "",
        "Remember: these are hypotheses, not validated opportunities.",
        "The goal is to give you a starting direction, not a final answer.",
    ])

    return "\n".join(lines)
