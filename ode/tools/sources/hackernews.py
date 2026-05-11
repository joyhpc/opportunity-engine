"""Hacker News source adapter."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from ode.tools.sources.common import append_note, clean_feed_text, strength_from_score

logger = logging.getLogger(__name__)

SOURCE_ID = "hackernews_topstories"


def scan(top_n: int = 30, source_notes: list[dict] | None = None) -> list[dict]:
    """Scan Hacker News top stories through the Firebase API."""

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed: pip install requests")
        append_note(
            source_notes,
            source_id=SOURCE_ID,
            status="unavailable",
            reason="missing_dependency",
            dependency="requests",
        )
        return []

    results = []
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10,
        )
        data = resp.json()
        if not isinstance(data, list):
            append_note(
                source_notes,
                source_id=SOURCE_ID,
                status="failed",
                reason="unexpected_topstories_payload",
            )
            return results
        story_ids = data[:top_n]

        def _fetch_item(sid):
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=5,
                ).json()
                if not item or not isinstance(item, dict):
                    return None
                score = item.get("score", 0)
                hn_item_url = f"https://news.ycombinator.com/item?id={sid}"
                return {
                    "source_id": SOURCE_ID,
                    "source": "hackernews",
                    "keyword": "",
                    "title": item.get("title", ""),
                    "url": item.get("url") or hn_item_url,
                    "summary": clean_feed_text(item.get("text", "")),
                    "score": score,
                    "comments": item.get("descendants", 0),
                    "strength": strength_from_score(score),
                    "momentum": 0,
                    "type": item.get("type", ""),
                    "external_id": str(sid),
                    "discussion_url": hn_item_url,
                    "time": datetime.fromtimestamp(item.get("time", 0)).isoformat(),
                }
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_fetch_item, sid): sid for sid in story_ids}
            for future in as_completed(futures):
                item = future.result()
                if item:
                    results.append(item)
    except Exception as exc:
        logger.error("HN scan failed: %s", exc)
        append_note(
            source_notes,
            source_id=SOURCE_ID,
            status="failed",
            reason="request_error",
            error=str(exc),
        )

    return results
