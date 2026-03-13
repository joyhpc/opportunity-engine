"""Data fetcher — web search + cache hybrid for evidence gathering."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime


def fetch_web(query: str, max_results: int = 5) -> list[dict]:
    """Fetch web search results. Returns list of {title, url, snippet}."""
    try:
        import requests
    except ImportError:
        print("requests not installed: pip install requests", file=sys.stderr)
        return []

    # Use DuckDuckGo instant answer API (no key needed)
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10,
        )
        data = resp.json()
        results = []

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if "Text" in topic:
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                    "source": "duckduckgo",
                })

        return results
    except Exception as e:
        print(f"Web fetch error: {e}", file=sys.stderr)
        return []


def cache_key(query: str) -> str:
    """Generate a cache key for a query."""
    return hashlib.sha256(query.encode()).hexdigest()[:16]
