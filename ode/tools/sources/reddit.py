"""Reddit RSS source adapter."""

from __future__ import annotations

import logging
import time

from ode.tools.sources.common import append_note, clean_feed_text, strength_from_position

logger = logging.getLogger(__name__)

SOURCE_ID = "reddit_hot_rss"
RETRY_STATUSES = {403, 429, 500, 502, 503, 504}


def scan(subreddits: list[str], limit: int = 10,
         source_notes: list[dict] | None = None) -> list[dict]:
    """Scan Reddit subreddits for hot posts via RSS feed."""

    try:
        import requests
        import xml.etree.ElementTree as ET
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
    headers = {"User-Agent": "ode-opportunity-engine/0.1 (+https://github.com/joyhpc/opportunity-engine)"}
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot/.rss?limit={limit}"
            resp, attempts = _get_with_retry(requests, url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning("Reddit r/%s RSS returned %s", sub, resp.status_code)
                append_note(
                    source_notes,
                    source_id=SOURCE_ID,
                    status="failed",
                    reason="http_status",
                    subreddit=sub,
                    http_status=resp.status_code,
                    attempts=attempts,
                )
                continue

            root = ET.fromstring(resp.text)
            entries = root.findall("atom:entry", ns)
            if not entries:
                append_note(
                    source_notes,
                    source_id=SOURCE_ID,
                    status="empty",
                    subreddit=sub,
                    attempts=attempts,
                )

            for position, entry in enumerate(entries[:limit]):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                content_el = entry.find("atom:content", ns)
                published_el = entry.find("atom:published", ns)
                updated_el = entry.find("atom:updated", ns)
                id_el = entry.find("atom:id", ns)
                author_el = entry.find("atom:author/atom:name", ns)
                title = clean_feed_text(title_el.text if title_el is not None else "")
                url = link_el.get("href", "") if link_el is not None else ""
                summary = ""
                if content_el is not None:
                    summary = clean_feed_text(" ".join(content_el.itertext()))

                results.append({
                    "source_id": SOURCE_ID,
                    "source": f"reddit/r/{sub}",
                    "keyword": "",
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "score": 0,
                    "comments": 0,
                    "strength": strength_from_position(position, strong_before=3, medium_before=7),
                    "momentum": 0,
                    "rank": position + 1,
                    "author": author_el.text if author_el is not None else "",
                    "published": published_el.text if published_el is not None else "",
                    "updated": updated_el.text if updated_el is not None else "",
                    "external_id": id_el.text if id_el is not None else "",
                })
        except ET.ParseError as exc:
            logger.warning("Reddit r/%s RSS parse failed: %s", sub, exc)
            append_note(
                source_notes,
                source_id=SOURCE_ID,
                status="failed",
                reason="malformed_xml",
                subreddit=sub,
                error=str(exc),
            )
        except Exception as exc:
            logger.warning("Reddit r/%s scan failed: %s", sub, exc)
            append_note(
                source_notes,
                source_id=SOURCE_ID,
                status="failed",
                reason="request_error",
                subreddit=sub,
                error=str(exc),
            )

    return results


def _get_with_retry(requests_module, url: str, *, headers: dict, timeout: int):
    attempts = 0
    response = None
    for attempts in range(1, 3):
        response = requests_module.get(url, headers=headers, timeout=timeout)
        if response.status_code not in RETRY_STATUSES:
            break
        if attempts == 1:
            time.sleep(0.1)
    return response, attempts
