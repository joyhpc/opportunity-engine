"""Pain-point listener for Reddit, Hacker News, and Product Hunt.

This module is intentionally evidence-aware.  Reddit/HN posts can contain
direct pain language, while Product Hunt is usually a solution-side launch
signal.  The listener keeps those evidence levels separate before ranking for
the founder profile.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ode.heuristics.fit_lens import FounderProfile


DEFAULT_REDDIT_SUBS = [
    "SaaS",
    "SideProject",
    "microsaas",
    "startups",
    "Entrepreneur",
    "ProductManagement",
    "webdev",
    "ArtificialInteligence",
    "LocalLLaMA",
]

DEFAULT_PROFILE_KEYWORDS = [
    "AI agents",
    "developer tools",
    "automation",
    "knowledge systems",
    "vertical SaaS",
    "workflow",
]

GRADE_STRENGTH = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}

PAIN_PHRASES = [
    "pain",
    "painful",
    "problem",
    "struggle",
    "struggling",
    "frustrating",
    "annoying",
    "hate",
    "hard to",
    "too hard",
    "difficult",
    "broken",
    "slow",
    "messy",
    "manual",
    "tedious",
    "repetitive",
    "bottleneck",
    "overwhelming",
    "doesn't work",
    "time consuming",
    "takes too long",
    "waste time",
    "too expensive",
    "expensive",
    "can't",
    "can't find",
    "cannot find",
    "wish there was",
    "looking for",
    "any tool",
    "need a",
    "need to",
    "need help",
    "is there a",
    "does anyone know",
    "recommend",
    "best way to",
    "alternative to",
    "how do i",
    "how to",
    "help with",
]

BUYER_PHRASES = [
    "pay for",
    "would pay",
    "paid",
    "budget",
    "pricing",
    "subscription",
    "invoice",
    "mrr",
    "arr",
    "revenue",
    "contract",
    "purchase",
    "$",
]

COMMERCIAL_CONTEXT_PHRASES = [
    "customer",
    "client",
    "agency",
    "founder",
    "team",
    "business",
    "b2b",
    "sales",
    "operator",
    "workflow",
]

SUCCESS_STORY_PHRASES = [
    "made my first internet money",
    "couldn't be happier",
    "i made",
    "we made",
    "i built",
    "we built",
    "i launched",
    "we launched",
    "just launched",
    "my saas",
    "our saas",
    "show hn",
]

REQUEST_INTENT_PHRASES = [
    "looking for",
    "need a",
    "need to",
    "need help",
    "any tool",
    "is there a",
    "does anyone know",
    "how do i",
    "how to",
    "recommend",
    "?",
]

WORKAROUND_PHRASES = [
    "spreadsheet",
    "notion",
    "zapier",
    "airtable",
    "manual process",
    "copy paste",
    "workaround",
    "script",
    "hack together",
    "glue",
]

URGENCY_PHRASES = [
    "urgent",
    "asap",
    "deadline",
    "blocked",
    "blocking",
    "production",
    "lost",
    "churn",
    "cancel",
]

DOMAIN_SEEDS = {
    "ai_agents": [
        "ai agent",
        "agent",
        "llm",
        "gpt",
        "rag",
        "prompt",
        "chatbot",
        "copilot",
        "autonomous",
    ],
    "developer_tools": [
        "developer",
        "api",
        "sdk",
        "github",
        "code",
        "debug",
        "deploy",
        "devtool",
        "ci",
        "database",
        "observability",
    ],
    "automation": [
        "automation",
        "workflow",
        "zapier",
        "integrate",
        "integration",
        "manual",
        "ops",
    ],
    "knowledge_systems": [
        "knowledge",
        "docs",
        "documentation",
        "wiki",
        "search",
        "notes",
        "retrieval",
    ],
    "vertical_saas": [
        "saas",
        "crm",
        "customer",
        "invoice",
        "booking",
        "clinic",
        "agency",
        "real estate",
        "law firm",
    ],
    "creator_tools": [
        "creator",
        "video",
        "podcast",
        "newsletter",
        "content",
        "social media",
    ],
    "sales_marketing": [
        "lead",
        "sales",
        "email",
        "outreach",
        "campaign",
        "ads",
        "seo",
    ],
    "customer_support": [
        "support",
        "ticket",
        "helpdesk",
        "chat",
        "handoff",
        "routing",
    ],
}


@dataclass
class PainSignal:
    title: str
    url: str = ""
    source: str = ""
    source_id: str = ""
    source_type: str = ""
    snippet: str = ""
    audience: str = ""
    pain_markers: list[str] = field(default_factory=list)
    buyer_markers: list[str] = field(default_factory=list)
    commercial_markers: list[str] = field(default_factory=list)
    downrank_markers: list[str] = field(default_factory=list)
    workaround_markers: list[str] = field(default_factory=list)
    urgency_markers: list[str] = field(default_factory=list)
    keyword_matches: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    pain_score: float = 0.0
    founder_fit: float = 0.0
    priority_score: float = 0.0
    evidence_grade: str = "E"
    cluster_size: int = 1
    source_diversity: int = 1
    recommendation: str = "Watch"
    reasons: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fetch_pain_sources(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
) -> list[dict[str, Any]]:
    """Fetch raw signals from the supported pain-listener sources."""

    from ode.tools.trend_scanner import scan_hackernews, scan_producthunt, scan_reddit

    signals: list[dict[str, Any]] = []
    if hn_top and hn_top > 0:
        signals.extend(scan_hackernews(hn_top))
    if subreddits:
        signals.extend(scan_reddit(subreddits, limit=reddit_limit))
    if include_product_hunt:
        signals.extend(scan_producthunt(limit=product_hunt_limit))
    return signals


def listen_with_fetch(
    *,
    hn_top: int = 50,
    subreddits: list[str] | None = None,
    reddit_limit: int = 15,
    include_product_hunt: bool = True,
    product_hunt_limit: int = 30,
    keywords: list[str] | None = None,
    profile: FounderProfile | dict[str, Any] | None = None,
    min_grade: str = "E",
    limit: int = 20,
) -> dict[str, Any]:
    """Fetch sources, then run the pure listener analysis."""

    subs = subreddits or DEFAULT_REDDIT_SUBS
    signals = fetch_pain_sources(
        hn_top=hn_top,
        subreddits=subs,
        reddit_limit=reddit_limit,
        include_product_hunt=include_product_hunt,
        product_hunt_limit=product_hunt_limit,
    )
    return listen(
        signals,
        profile=profile,
        keywords=keywords,
        min_grade=min_grade,
        limit=limit,
    )


def listen(
    signals: list[dict[str, Any]],
    *,
    profile: FounderProfile | dict[str, Any] | None = None,
    keywords: list[str] | None = None,
    min_grade: str = "E",
    limit: int = 20,
) -> dict[str, Any]:
    """Analyze already-fetched signals for pain, evidence, and founder fit."""

    founder = profile if isinstance(profile, FounderProfile) else FounderProfile.from_dict(profile)
    keywords = keywords or DEFAULT_PROFILE_KEYWORDS
    min_grade = (min_grade or "E").upper()

    unique = _dedupe_signals(signals)
    analyzed = [
        analyze_signal(signal, profile=founder, keywords=keywords)
        for signal in unique
    ]
    analyzed = [signal for signal in analyzed if _worth_keeping(signal)]
    _apply_cluster_support(analyzed)

    filtered = [
        signal for signal in analyzed
        if GRADE_STRENGTH.get(signal.evidence_grade, 0) >= GRADE_STRENGTH.get(min_grade, 1)
    ]
    filtered.sort(key=lambda signal: (
        -GRADE_STRENGTH.get(signal.evidence_grade, 0),
        -signal.priority_score,
        -signal.founder_fit,
        signal.title.lower(),
    ))
    top = filtered[:limit]

    source_summary = Counter(signal.source_id or signal.source for signal in filtered)
    tag_summary = Counter(tag for signal in filtered for tag in signal.tags)
    grade_summary = Counter(signal.evidence_grade for signal in filtered)
    validation_queues = _build_validation_queues(filtered)

    return {
        "status": "ok" if filtered else "no_signals",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_raw_signals": len(signals),
        "unique_signals": len(unique),
        "kept_signals": len(filtered),
        "min_grade": min_grade,
        "source_summary": dict(source_summary),
        "tag_summary": dict(tag_summary),
        "grade_summary": dict(grade_summary),
        "validation_queues": validation_queues,
        "profile": founder.to_dict(),
        "keywords": keywords,
        "top_signals": [signal.to_dict() for signal in top],
        "all_signals": [signal.to_dict() for signal in filtered],
        "source_notes": [
            "Reddit/HN are community-language signals, usually D or C when pain and buyer intent are explicit.",
            "Product Hunt feed items are launch/solution-side proxies, usually E unless the text itself states pain.",
            "Commercial context such as customers or teams boosts fit but is not buyer intent by itself.",
            "Launch and success-story posts are downranked; use the revenue-case workflow for money claims.",
            "No social signal is treated as verified revenue evidence.",
        ],
    }


def analyze_signal(
    signal: dict[str, Any],
    *,
    profile: FounderProfile | dict[str, Any] | None = None,
    keywords: list[str] | None = None,
) -> PainSignal:
    """Score a single raw signal."""

    founder = profile if isinstance(profile, FounderProfile) else FounderProfile.from_dict(profile)
    keywords = keywords or DEFAULT_PROFILE_KEYWORDS
    title = _clean_text(str(signal.get("title") or signal.get("keyword") or ""))
    snippet = _clean_text(str(signal.get("summary") or signal.get("text") or signal.get("selftext") or ""))
    text = _signal_text(signal)

    pain_markers = _phrase_hits(PAIN_PHRASES, text)
    buyer_markers = _phrase_hits(BUYER_PHRASES, text)
    commercial_markers = _phrase_hits(COMMERCIAL_CONTEXT_PHRASES, text)
    downrank_markers = _downrank_markers(title, text)
    workaround_markers = _phrase_hits(WORKAROUND_PHRASES, text)
    urgency_markers = _phrase_hits(URGENCY_PHRASES, text)
    keyword_matches = _phrase_hits(keywords, text)
    tags = _domain_tags(text)
    source_id = str(signal.get("source_id") or "")
    source = str(signal.get("source") or "")
    source_type = _source_type(source_id, source)
    audience = _audience(source_id, source)

    marker_score = min(len(pain_markers) * 9, 36)
    buyer_score = min(len(buyer_markers) * 8, 24)
    commercial_score = min(len(commercial_markers) * 3, 9)
    workaround_score = min(len(workaround_markers) * 7, 18)
    urgency_score = min(len(urgency_markers) * 6, 12)
    keyword_score = min(len(keyword_matches) * 4, 12)
    tag_score = min(len(tags) * 3, 12)
    engagement_score = _engagement_score(signal)
    solution_penalty = 10 if source_id == "producthunt_feed" and not pain_markers else 0
    story_penalty = 24 if downrank_markers else 0

    pain_score = _clamp(
        18
        + marker_score
        + buyer_score
        + commercial_score
        + workaround_score
        + urgency_score
        + keyword_score
        + tag_score
        + engagement_score
        - solution_penalty
        - story_penalty
    )
    founder_fit = _founder_fit(founder, text, tags, source_id, source)
    evidence_grade = _evidence_grade(
        source_id=source_id,
        pain_markers=pain_markers,
        buyer_markers=buyer_markers,
        commercial_markers=commercial_markers,
        downrank_markers=downrank_markers,
        workaround_markers=workaround_markers,
        urgency_markers=urgency_markers,
        pain_score=pain_score,
        engagement_score=engagement_score,
    )
    priority = _clamp((pain_score * 0.56) + (founder_fit * 0.34) + (engagement_score * 0.10))

    analyzed = PainSignal(
        title=title,
        url=str(signal.get("url") or ""),
        source=source,
        source_id=source_id,
        source_type=source_type,
        snippet=snippet,
        audience=audience,
        pain_markers=pain_markers,
        buyer_markers=buyer_markers,
        commercial_markers=commercial_markers,
        downrank_markers=downrank_markers,
        workaround_markers=workaround_markers,
        urgency_markers=urgency_markers,
        keyword_matches=keyword_matches,
        tags=tags,
        pain_score=round(pain_score, 1),
        founder_fit=round(founder_fit, 1),
        priority_score=round(priority, 1),
        evidence_grade=evidence_grade,
        raw_data=signal,
    )
    _finalize_recommendation(analyzed)
    return analyzed


def format_pain_report(result: dict[str, Any]) -> str:
    """Format listener output as a markdown report."""

    if result.get("status") != "ok":
        return "\n".join([
            "# Pain Listener Report",
            "",
            "No pain signals survived the evidence filter.",
            f"Raw signals scanned: {result.get('total_raw_signals', 0)}",
            f"Evidence filter: >= {result.get('min_grade', 'E')}",
        ])

    lines = [
        "# Pain Listener Report",
        f"Generated: {result.get('generated_at', '')}",
        f"Raw signals: {result.get('total_raw_signals', 0)}",
        f"Kept after evidence filter: {result.get('kept_signals', 0)}",
        f"Evidence filter: >= {result.get('min_grade', 'E')}",
        "",
        "Evidence rule: C = explicit pain plus buyer intent or cross-source support; D = explicit community pain; E = weak social or solution-side proxy.",
        "",
    ]

    if result.get("source_summary"):
        lines.append("## Source Mix")
        for source, count in sorted(result["source_summary"].items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {source}: {count}")
        lines.append("")

    if result.get("tag_summary"):
        lines.append("## Profile-Relevant Themes")
        for tag, count in sorted(result["tag_summary"].items(), key=lambda item: (-item[1], item[0]))[:8]:
            lines.append(f"- {tag}: {count}")
        lines.append("")

    validation_queues = result.get("validation_queues", [])
    if validation_queues:
        lines.extend([
            "## Validation Queues",
            "",
            "| Theme | Signals | Sources | Best Grade | Avg Fit | Suggested Wedge |",
            "|-------|---------|---------|------------|---------|-----------------|",
        ])
        for queue in validation_queues[:6]:
            lines.append(
                f"| {_table_cell(queue.get('theme', ''))} | "
                f"{queue.get('signal_count', 0)} | {queue.get('source_diversity', 0)} | "
                f"{queue.get('best_grade', 'E')} | {queue.get('avg_founder_fit', 0):.1f} | "
                f"{_table_cell(queue.get('suggested_wedge', ''))} |"
            )
        lines.append("")

    top_signals = result.get("top_signals", [])
    lines.extend([
        "## Ranked Signals",
        "",
        "| Rank | Grade | Priority | Fit | Source | Tags | Signal |",
        "|------|-------|----------|-----|--------|------|--------|",
    ])
    for index, signal in enumerate(top_signals, 1):
        tags = ", ".join(signal.get("tags", [])[:3]) or "general"
        lines.append(
            f"| {index} | {signal.get('evidence_grade', 'E')} | "
            f"{signal.get('priority_score', 0):.1f} | {signal.get('founder_fit', 0):.1f} | "
            f"{_table_cell(signal.get('source') or signal.get('source_id', ''))} | "
            f"{_table_cell(tags)} | {_table_cell(_shorten(signal.get('title', ''), 72))} |"
        )
    lines.append("")

    lines.append("## Best Matches")
    for index, signal in enumerate(top_signals[:8], 1):
        lines.extend([
            "",
            f"### {index}. {signal.get('title', '')}",
            f"Source: {signal.get('source', '')} | Grade: {signal.get('evidence_grade', 'E')} | Priority: {signal.get('priority_score', 0):.1f} | Founder fit: {signal.get('founder_fit', 0):.1f}",
        ])
        if signal.get("url"):
            lines.append(f"URL: {signal['url']}")
        if signal.get("snippet"):
            lines.append(f"Snippet: {_shorten(signal['snippet'], 180)}")

        markers = _marker_line(signal)
        if markers:
            lines.append(f"Markers: {markers}")
        if signal.get("reasons"):
            lines.append("Why:")
            lines.extend([f"- {reason}" for reason in signal["reasons"]])
        if signal.get("next_actions"):
            lines.append("Next actions:")
            lines.extend([f"- {action}" for action in signal["next_actions"]])

    if result.get("source_notes"):
        lines.extend(["", "## Caveats"])
        lines.extend([f"- {note}" for note in result["source_notes"]])

    return "\n".join(lines)


def _dedupe_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for signal in signals:
        title = _clean_text(str(signal.get("title") or signal.get("keyword") or "")).lower()
        url = str(signal.get("url") or "").split("?")[0]
        key = (title, url)
        if key in seen or not title:
            continue
        seen.add(key)
        unique.append(signal)
    return unique


def _worth_keeping(signal: PainSignal) -> bool:
    if signal.downrank_markers and signal.evidence_grade == "E":
        return False
    if signal.evidence_grade in {"C", "D"}:
        return True
    if (signal.pain_markers or signal.buyer_markers or signal.workaround_markers) and (
        signal.tags or signal.keyword_matches or signal.founder_fit >= 52 or signal.priority_score >= 48
    ):
        return True
    if signal.source_id == "producthunt_feed" and (signal.keyword_matches or signal.tags):
        return True
    return signal.priority_score >= 55


def _apply_cluster_support(signals: list[PainSignal]) -> None:
    clusters: dict[str, list[PainSignal]] = defaultdict(list)
    for signal in signals:
        keys = signal.tags[:2] or [_theme_key(signal.title)]
        for key in keys:
            clusters[key].append(signal)

    for signal in signals:
        keys = signal.tags[:2] or [_theme_key(signal.title)]
        best_cluster = max((clusters[key] for key in keys), key=len)
        source_diversity = len({item.source_id or item.source for item in best_cluster})
        support = min((len(best_cluster) - 1) * 3 + (source_diversity - 1) * 5, 14)
        signal.cluster_size = len(best_cluster)
        signal.source_diversity = source_diversity
        signal.priority_score = round(_clamp(signal.priority_score + support), 1)

        if signal.evidence_grade == "D" and source_diversity >= 2 and (signal.buyer_markers or signal.pain_score >= 75):
            signal.evidence_grade = "C"
        elif signal.evidence_grade == "E" and source_diversity >= 2 and signal.pain_markers:
            signal.evidence_grade = "D"
        _finalize_recommendation(signal)


def _build_validation_queues(signals: list[PainSignal]) -> list[dict[str, Any]]:
    """Group individual signals into small validation queues."""

    grouped: dict[str, list[PainSignal]] = defaultdict(list)
    for signal in signals:
        key = signal.tags[0] if signal.tags else _theme_key(signal.title)
        grouped[key].append(signal)

    queues: list[dict[str, Any]] = []
    for theme, items in grouped.items():
        items = sorted(
            items,
            key=lambda item: (
                -GRADE_STRENGTH.get(item.evidence_grade, 0),
                -item.priority_score,
                -item.founder_fit,
            ),
        )
        sources = sorted({item.source_id or item.source for item in items if item.source_id or item.source})
        best_grade = max(
            (item.evidence_grade for item in items),
            key=lambda grade: GRADE_STRENGTH.get(grade, 0),
        )
        avg_fit = sum(item.founder_fit for item in items) / len(items)
        avg_priority = sum(item.priority_score for item in items) / len(items)
        top = items[0]
        queues.append({
            "theme": theme.replace("_", " "),
            "theme_key": theme,
            "signal_count": len(items),
            "source_diversity": len(sources),
            "sources": sources,
            "best_grade": best_grade,
            "avg_founder_fit": round(avg_fit, 1),
            "avg_priority": round(avg_priority, 1),
            "top_titles": [item.title for item in items[:3]],
            "suggested_wedge": _suggested_wedge(theme, top),
            "next_step": _queue_next_step(best_grade, avg_fit, len(sources)),
        })

    queues.sort(key=lambda queue: (
        -GRADE_STRENGTH.get(queue["best_grade"], 0),
        -queue["source_diversity"],
        -queue["avg_priority"],
        -queue["avg_founder_fit"],
        queue["theme"],
    ))
    return queues


def _suggested_wedge(theme: str, signal: PainSignal) -> str:
    audience = signal.audience or "this audience"
    labels = {
        "ai_agents": "AI-agent debugging or workflow reliability",
        "developer_tools": "developer workflow automation",
        "automation": "manual workflow removal",
        "knowledge_systems": "searchable knowledge base or retrieval workflow",
        "vertical_saas": "narrow vertical SaaS workflow",
        "creator_tools": "creator production workflow",
        "sales_marketing": "sales or outreach workflow",
        "customer_support": "support triage or response workflow",
    }
    label = labels.get(theme, theme.replace("_", " "))
    if signal.source_id == "producthunt_feed":
        return f"Map launch language to a real {label} complaint"
    if signal.buyer_markers:
        return f"Offer a paid concierge fix for {label} in {audience}"
    return f"Validate a focused {label} pain in {audience}"


def _queue_next_step(best_grade: str, avg_fit: float, source_diversity: int) -> str:
    if GRADE_STRENGTH.get(best_grade, 0) >= GRADE_STRENGTH["C"] and avg_fit >= 60:
        return "Run a 5-user payment-intent sprint."
    if source_diversity >= 2:
        return "Collect comments and compare current workarounds."
    return "Find the same pain in one more source before building."


def _finalize_recommendation(signal: PainSignal) -> None:
    reasons: list[str] = []
    if signal.pain_markers:
        reasons.append(f"Pain language: {', '.join(signal.pain_markers[:5])}.")
    if signal.buyer_markers:
        reasons.append(f"Buyer intent or money language: {', '.join(signal.buyer_markers[:5])}.")
    if signal.commercial_markers and not signal.buyer_markers:
        reasons.append(f"Commercial context: {', '.join(signal.commercial_markers[:4])}.")
    if signal.workaround_markers:
        reasons.append(f"Existing workaround: {', '.join(signal.workaround_markers[:4])}.")
    if signal.downrank_markers:
        reasons.append(f"Downranked as launch/success-story context: {', '.join(signal.downrank_markers[:3])}.")
    if signal.tags:
        reasons.append(f"Matches profile themes: {', '.join(signal.tags[:4])}.")
    if signal.source_id == "producthunt_feed":
        reasons.append("Product Hunt is treated as solution-side evidence, so verify the user pain elsewhere.")
    if signal.source_diversity >= 2:
        reasons.append(f"Theme repeats across {signal.source_diversity} source types.")

    if signal.source_id == "producthunt_feed":
        recommendation = "Map To Pain"
    elif signal.evidence_grade in {"C", "D"} and signal.priority_score >= 72 and signal.founder_fit >= 60:
        recommendation = "Validate Now"
    elif signal.priority_score >= 60:
        recommendation = "Research Next"
    else:
        recommendation = "Watch"

    signal.recommendation = recommendation
    signal.reasons = reasons or ["Weak but potentially relevant source-language signal."]
    signal.next_actions = _next_actions(signal)


def _next_actions(signal: PainSignal) -> list[str]:
    if signal.source_id == "producthunt_feed":
        return [
            "Search Reddit/HN for complaints using the product tagline and adjacent keywords.",
            "List the incumbent workaround and identify what the launch claims to remove.",
            "Do not create an opportunity until a user pain post or buyer quote is found.",
        ]
    if signal.buyer_markers:
        return [
            "Collect 5 similar posts or comments from the same audience.",
            "Offer a narrow paid concierge fix before building a full product.",
            "Create an ODE opportunity only after the buyer and repeatable workflow are explicit.",
        ]
    return [
        "Find the same pain in at least two communities.",
        "Interview 3 users about current workaround, frequency, and budget.",
        "Write a small validation artifact: landing page, script, or manual service.",
    ]


def _signal_text(signal: dict[str, Any]) -> str:
    parts = [
        str(signal.get("title") or ""),
        str(signal.get("keyword") or ""),
        str(signal.get("summary") or ""),
        str(signal.get("text") or ""),
        str(signal.get("selftext") or ""),
        str(signal.get("source") or ""),
    ]
    return _clean_text(" ".join(parts)).lower()


def _phrase_hits(phrases: list[str], text: str) -> list[str]:
    normalized = text.lower()
    hits = []
    for phrase in phrases:
        value = phrase.lower().strip()
        if value and value in normalized:
            hits.append(phrase)
    return hits


def _downrank_markers(title: str, text: str) -> list[str]:
    """Find launch/success-story language that is not a user pain request."""

    title_text = title.lower()
    story_hits = _phrase_hits(SUCCESS_STORY_PHRASES, text)
    if not story_hits:
        return []
    if _phrase_hits(REQUEST_INTENT_PHRASES, title_text):
        return []
    return story_hits


def _domain_tags(text: str) -> list[str]:
    tags = []
    for tag, seeds in DOMAIN_SEEDS.items():
        if any(seed in text for seed in seeds):
            tags.append(tag)
    return tags


def _founder_fit(founder: FounderProfile, text: str, tags: list[str], source_id: str, source: str) -> float:
    score = 36.0
    profile_terms = founder.strengths + founder.exploration_interests
    channel_terms = founder.channels
    hard_hits = _phrase_hits(founder.hard_exclusions, text)

    score += min(len(_phrase_hits(profile_terms, text)) * 8, 32)
    score += min(len(_phrase_hits(channel_terms, f"{text} {source}")) * 4, 12)
    score += min(len(tags) * 5, 20)

    if source_id == "hackernews_topstories":
        score += 8
    if source.startswith("reddit/r/") and any(item in source.lower() for item in ["saas", "sideproject", "webdev"]):
        score += 7
    if source_id == "producthunt_feed":
        score += 4

    if any(term in text for term in ["hardware", "clinical", "medical device", "manufacturing"]):
        score -= 12
    if any(term in text for term in ["enterprise procurement", "government", "regulated"]):
        score -= 8
    if hard_hits:
        score = min(score, 10)
    return _clamp(score)


def _source_type(source_id: str, source: str) -> str:
    if source_id == "producthunt_feed":
        return "solution_launch"
    if source_id == "hackernews_topstories":
        return "technical_community"
    if source.startswith("reddit/"):
        return "community_post"
    return "unknown"


def _audience(source_id: str, source: str) -> str:
    if source.startswith("reddit/r/"):
        return source.replace("reddit/r/", "r/")
    if source_id == "hackernews_topstories":
        return "technical early adopters"
    if source_id == "producthunt_feed":
        return "makers and startup early adopters"
    return source or source_id


def _engagement_score(signal: dict[str, Any]) -> float:
    source_id = str(signal.get("source_id") or "")
    source = str(signal.get("source") or "")
    score = signal.get("score") or 0
    comments = signal.get("comments") or signal.get("descendants") or 0

    if source_id == "hackernews_topstories":
        return min(float(score) / 20, 12) + min(float(comments) / 10, 8)
    if source.startswith("reddit/r/"):
        return 6
    if source_id == "producthunt_feed":
        rank = int(signal.get("rank") or 99)
        if rank <= 5:
            return 8
        if rank <= 15:
            return 5
        return 2
    return 0


def _evidence_grade(
    *,
    source_id: str,
    pain_markers: list[str],
    buyer_markers: list[str],
    commercial_markers: list[str],
    downrank_markers: list[str],
    workaround_markers: list[str],
    urgency_markers: list[str],
    pain_score: float,
    engagement_score: float,
) -> str:
    if downrank_markers:
        return "E"
    if source_id == "producthunt_feed":
        if pain_markers and (buyer_markers or workaround_markers or urgency_markers):
            return "D"
        return "E"
    if pain_markers and buyer_markers and pain_score >= 65:
        return "C"
    if pain_markers and (workaround_markers or urgency_markers or engagement_score >= 8):
        return "D"
    if pain_markers and commercial_markers and pain_score >= 60:
        return "D"
    if buyer_markers and workaround_markers:
        return "D"
    return "E"


def _theme_key(title: str) -> str:
    tokens = re.findall(r"[a-z0-9]{3,}", title.lower())
    stop = {"the", "and", "for", "with", "this", "that", "from", "how", "what", "why"}
    meaningful = [token for token in tokens if token not in stop]
    return meaningful[0] if meaningful else "general"


def _marker_line(signal: dict[str, Any]) -> str:
    groups = []
    for label, key in [
        ("pain", "pain_markers"),
        ("buyer", "buyer_markers"),
        ("commercial", "commercial_markers"),
        ("workaround", "workaround_markers"),
        ("urgency", "urgency_markers"),
        ("downrank", "downrank_markers"),
    ]:
        values = signal.get(key) or []
        if values:
            groups.append(f"{label}: {', '.join(values[:4])}")
    return "; ".join(groups)


def _table_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _shorten(value: str, limit: int) -> str:
    value = _clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))
