"""Context-aware dispatch for registered discovery sources."""

from __future__ import annotations

from typing import Any

from ode.tools.source_registry import DataSource, load_source_adapter, sources_for_context


def scan_for_context(context: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Run registered source adapters for a runtime context."""

    return scan_for_context_with_notes(context, **kwargs)["signals"]


def scan_for_context_with_notes(context: str, **kwargs: Any) -> dict[str, Any]:
    """Run registered source adapters and return signals plus source events."""

    signals: list[dict[str, Any]] = []
    source_events: list[dict[str, Any]] = []
    for source in sources_for_context(context):
        if source.status not in {"active", "optional"}:
            continue
        if not _source_enabled(source, **kwargs):
            continue

        adapter = load_source_adapter(source)
        before = len(source_events)
        try:
            items = _call_adapter(source, adapter, source_notes=source_events, **kwargs)
        except Exception as exc:
            source_events.append({
                "source_id": source.id,
                "status": "failed",
                "reason": "adapter_exception",
                "error": str(exc),
            })
            continue
        signals.extend(items)
        if len(source_events) == before:
            source_events.append({
                "source_id": source.id,
                "status": "ok",
                "count": len(items),
            })

    return {"signals": signals, "source_events": source_events}


def _source_enabled(source: DataSource, **kwargs: Any) -> bool:
    if source.id == "google_trends":
        return bool(kwargs.get("keywords"))
    if source.id == "hackernews_topstories":
        return int(kwargs.get("hn_top") or 0) > 0
    if source.id == "reddit_hot_rss":
        return bool(kwargs.get("subreddits"))
    if source.id == "producthunt_feed":
        return bool(kwargs.get("include_product_hunt", True))
    return False


def _call_adapter(source: DataSource, adapter, source_notes: list[dict], **kwargs: Any) -> list[dict[str, Any]]:
    if source.id == "google_trends":
        return adapter(
            kwargs.get("keywords") or [],
            kwargs.get("timeframe", "today 3-m"),
            kwargs.get("geo", ""),
            source_notes=source_notes,
        )
    if source.id == "hackernews_topstories":
        return adapter(int(kwargs.get("hn_top") or 0), source_notes=source_notes)
    if source.id == "reddit_hot_rss":
        subreddits = kwargs.get("subreddits") or []
        reddit_limit = kwargs.get("reddit_limit")
        if reddit_limit is None:
            return adapter(subreddits, source_notes=source_notes)
        return adapter(subreddits, limit=int(reddit_limit), source_notes=source_notes)
    if source.id == "producthunt_feed":
        return adapter(limit=int(kwargs.get("product_hunt_limit") or 30), source_notes=source_notes)
    return []
