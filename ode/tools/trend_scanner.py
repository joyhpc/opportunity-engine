"""Trend scanning facade and aggregate report helpers.

Individual source adapters live in ``ode.tools.sources``. This module keeps
the original public scanner functions as compatibility wrappers and owns the
aggregate ``scan_all`` filtering/reporting behavior.
"""

from __future__ import annotations

from datetime import datetime

from ode.tools.sources.common import MEDIUM, STRONG, WEAK, clean_feed_text


def scan_google_trends(keywords: list[str], timeframe: str = "today 3-m",
                       geo: str = "") -> list[dict]:
    """Backward-compatible wrapper for the Google Trends adapter."""

    from ode.tools.sources.google_trends import scan

    return scan(keywords, timeframe, geo)


def scan_hackernews(top_n: int = 30) -> list[dict]:
    """Backward-compatible wrapper for the Hacker News adapter."""

    from ode.tools.sources.hackernews import scan

    return scan(top_n)


def scan_reddit(subreddits: list[str], limit: int = 10) -> list[dict]:
    """Backward-compatible wrapper for the Reddit adapter."""

    from ode.tools.sources.reddit import scan

    return scan(subreddits, limit=limit)


def scan_producthunt(limit: int = 30,
                     feed_url: str = "https://www.producthunt.com/feed") -> list[dict]:
    """Backward-compatible wrapper for the Product Hunt adapter."""

    from ode.tools.sources.producthunt import scan

    return scan(limit=limit, feed_url=feed_url)


def _clean_feed_text(value: str) -> str:
    """Backward-compatible wrapper for feed text cleaning."""

    return clean_feed_text(value)


def _relevance_score(signal: dict, keywords: list[str]) -> float:
    """0.0-1.0: fraction of keywords matched in title+keyword field."""

    if not keywords:
        return 1.0
    text = f"{signal.get('title', '')} {signal.get('keyword', '')}".lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / len(keywords)


def scan_all(keywords: list[str] | None = None,
             domain: str = "",
             hn_top: int = 0,
             subreddits: list[str] | None = None,
             timeframe: str = "today 3-m",
             geo: str = "") -> list[dict]:
    """Run all sources registered for the scan worker context."""

    from ode.tools.source_dispatch import scan_for_context

    signals = scan_for_context(
        "scan_worker",
        keywords=keywords,
        domain=domain,
        hn_top=hn_top,
        subreddits=subreddits,
        timeframe=timeframe,
        geo=geo,
    )

    if keywords and signals:
        for signal in signals:
            signal["relevance_score"] = round(_relevance_score(signal, keywords), 2)
        signals = [
            signal for signal in signals
            if signal.get("relevance_score", 0) >= 0.1
            or signal.get("strength") in (STRONG, MEDIUM)
        ]

    if domain and signals:
        domain_lower = domain.lower()
        filtered = [
            signal for signal in signals
            if domain_lower in signal.get("title", "").lower()
            or domain_lower in signal.get("keyword", "").lower()
        ]
        if filtered:
            signals = filtered

    return signals


def format_report(signals: list[dict]) -> str:
    """Format signals as a markdown report."""

    lines = [
        "# Trend Scan Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Total signals: {len(signals)}",
        "",
    ]

    by_source: dict[str, list] = {}
    for signal in signals:
        by_source.setdefault(signal["source"], []).append(signal)

    strength_order = {STRONG: 0, MEDIUM: 1, WEAK: 2}

    for source, items in by_source.items():
        lines.append(f"## {source}")
        lines.append("| Strength | Content | Metrics |")
        lines.append("|----------|---------|---------|")
        for item in sorted(items, key=lambda item: strength_order.get(item.get("strength", WEAK), 3)):
            strength = item.get("strength", "-")
            content = item.get("title") or item.get("keyword", "")
            content = content[:60]
            if "current_interest" in item:
                metric = f"interest={item['current_interest']}, momentum={item.get('momentum', 0)}%"
            elif "score" in item:
                metric = f"votes={item['score']} comments={item.get('comments', 0)}"
            else:
                metric = ""
            lines.append(f"| {strength} | {content} | {metric} |")
        lines.append("")

    strong = sum(1 for signal in signals if signal.get("strength") == STRONG)
    medium = sum(1 for signal in signals if signal.get("strength") == MEDIUM)
    weak = len(signals) - strong - medium
    lines.append(f"**Summary**: strong={strong} medium={medium} weak={weak}")

    return "\n".join(lines)
