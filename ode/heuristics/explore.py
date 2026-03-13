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


def cluster_signals(signals: list[dict]) -> dict[str, list[dict]]:
    """Cluster signals into domain themes using seed-word matching.

    Returns {domain: [signals]} sorted by cluster size descending.
    Signals matching no domain go into "emerging" (the interesting ones).
    """
    clusters: dict[str, list[dict]] = defaultdict(list)

    for sig in signals:
        tokens = set(_tokenize_signal(sig))
        matched_domains = []

        for domain, seeds in DOMAIN_SEEDS.items():
            overlap = tokens & set(seeds)
            if overlap:
                matched_domains.append((domain, len(overlap)))

        if matched_domains:
            # Assign to best-matching domain
            best = max(matched_domains, key=lambda x: x[1])[0]
            clusters[best].append(sig)
        else:
            clusters["emerging"].append(sig)

    # Sort by cluster size
    return dict(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True))


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
                        min_signals: int = 2) -> list[dict]:
    """Generate opportunity hypotheses from signal clusters.

    Each hypothesis captures:
    - domain, themes, signal_count, strength profile
    - a human-readable hypothesis statement
    - suggested next steps
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

        # Suggest next steps based on confidence
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
            "top_signals": sorted(signals,
                key=lambda s: {"强": 0, "中": 1, "弱": 2}.get(s.get("strength", "弱"), 3))[:5],
        })

    # Sort by confidence
    hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
    return hypotheses


# ---------------------------------------------------------------------------
# Main exploration flow
# ---------------------------------------------------------------------------

def explore(hn_top: int = 30,
            subreddits: list[str] | None = None,
            keywords: list[str] | None = None) -> dict:
    """Run open-ended exploration and return structured results.

    Can be called with zero arguments — will scan HN top stories by default.
    """
    from ..tools.trend_scanner import scan_all

    # Default subreddits covering diverse opportunity spaces
    default_subs = [
        "startup", "SaaS", "Entrepreneur", "sideproject",
        "artificial", "MachineLearning",
    ]
    subs = subreddits or default_subs

    # If no keywords, still scan HN and Reddit (the discovery path)
    signals = scan_all(
        keywords=keywords,
        hn_top=hn_top or 30,
        subreddits=subs,
    )

    if not signals:
        return {
            "status": "no_signals",
            "message": "No signals found. Try different subreddits or check network.",
            "clusters": {},
            "hypotheses": [],
        }

    clusters = cluster_signals(signals)
    hypotheses = generate_hypotheses(clusters)

    return {
        "status": "ok",
        "total_signals": len(signals),
        "cluster_count": len(clusters),
        "hypotheses": hypotheses,
        "clusters": {k: len(v) for k, v in clusters.items()},
    }


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
            "",
        ])

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
