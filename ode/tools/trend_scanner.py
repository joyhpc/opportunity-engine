"""趋势扫描器 — 多源信号采集 (重构为库函数).

Scans Google Trends, HackerNews, Reddit for trend signals.
Returns structured signal dicts suitable for Signal model.
"""

from __future__ import annotations

import logging
import html
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Google Trends
# ---------------------------------------------------------------------------

def scan_google_trends(keywords: list[str], timeframe: str = "today 3-m",
                       geo: str = "") -> list[dict]:
    """Scan Google Trends for keyword interest changes."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed: pip install pytrends")
        return []

    hl = os.environ.get("ODE_TRENDS_LOCALE", "zh-CN")
    tz = int(os.environ.get("ODE_TRENDS_TZ", "480"))
    pytrends = TrendReq(hl=hl, tz=tz)
    results = []

    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        try:
            pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo=geo)
            interest = pytrends.interest_over_time()
        except Exception as e:
            logger.warning("Google Trends error for %s: %s", batch, e)
            continue

        if interest.empty:
            continue

        for kw in batch:
            if kw not in interest.columns:
                continue
            series = interest[kw]
            recent = series.tail(4).mean()
            earlier = series.head(4).mean()
            momentum = ((recent - earlier) / max(earlier, 1)) * 100

            results.append({
                "source_id": "google_trends",
                "source": "google_trends",
                "keyword": kw,
                "title": kw,
                "current_interest": int(recent),
                "momentum": round(momentum, 1),
                "strength": "强" if momentum > 50 else "中" if momentum > 20 else "弱",
                "timeframe": timeframe,
                "geo": geo or "global",
            })

        try:
            related = pytrends.related_queries()
            for kw in batch:
                if kw in related and related[kw]["rising"] is not None:
                    top_rising = related[kw]["rising"].head(5)
                    for _, row in top_rising.iterrows():
                        results.append({
                            "source_id": "google_trends",
                            "source": "google_trends_rising",
                            "keyword": row["query"],
                            "title": row["query"],
                            "parent_keyword": kw,
                            "momentum": 0,
                            "strength": "中",
                        })
        except Exception:
            pass

    return results


# ---------------------------------------------------------------------------
# HackerNews
# ---------------------------------------------------------------------------

def scan_hackernews(top_n: int = 30) -> list[dict]:
    """Scan HackerNews top stories."""
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed: pip install requests")
        return []

    results = []
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10,
        )
        data = resp.json()
        if not isinstance(data, list):
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
                    "source_id": "hackernews_topstories",
                    "source": "hackernews",
                    "keyword": "",
                    "title": item.get("title", ""),
                    "url": item.get("url") or hn_item_url,
                    "summary": _clean_feed_text(item.get("text", "")),
                    "score": score,
                    "comments": item.get("descendants", 0),
                    "strength": "强" if score > 200 else "中" if score > 50 else "弱",
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
    except Exception as e:
        logger.error("HN scan failed: %s", e)

    return results


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

def scan_reddit(subreddits: list[str], limit: int = 10) -> list[dict]:
    """Scan Reddit subreddits for hot posts via RSS feed."""
    try:
        import requests
        import xml.etree.ElementTree as ET
    except ImportError:
        logger.warning("requests not installed: pip install requests")
        return []

    results = []
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for sub in subreddits:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot/.rss?limit={limit}",
                headers=headers, timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Reddit r/%s RSS returned %s", sub, resp.status_code)
                continue

            root = ET.fromstring(resp.text)
            entries = root.findall("atom:entry", ns)

            for position, entry in enumerate(entries[:limit]):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                content_el = entry.find("atom:content", ns)
                published_el = entry.find("atom:published", ns)
                updated_el = entry.find("atom:updated", ns)
                id_el = entry.find("atom:id", ns)
                author_el = entry.find("atom:author/atom:name", ns)
                title = _clean_feed_text(title_el.text if title_el is not None else "")
                url = link_el.get("href", "") if link_el is not None else ""
                summary = ""
                if content_el is not None:
                    summary = _clean_feed_text(" ".join(content_el.itertext()))

                # RSS doesn't include score/comments, estimate from position
                estimated_strength = "强" if position < 3 else "中" if position < 7 else "弱"

                results.append({
                    "source_id": "reddit_hot_rss",
                    "source": f"reddit/r/{sub}",
                    "keyword": "",
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "score": 0,
                    "comments": 0,
                    "strength": estimated_strength,
                    "momentum": 0,
                    "rank": position + 1,
                    "author": author_el.text if author_el is not None else "",
                    "published": published_el.text if published_el is not None else "",
                    "updated": updated_el.text if updated_el is not None else "",
                    "external_id": id_el.text if id_el is not None else "",
                })
        except Exception as e:
            logger.warning("Reddit r/%s scan failed: %s", sub, e)

    return results


# ---------------------------------------------------------------------------
# Product Hunt
# ---------------------------------------------------------------------------

def _clean_feed_text(value: str) -> str:
    """Collapse Atom/HTML text into a short readable snippet."""

    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*Read more on Product Hunt.*$", "", text, flags=re.I)
    text = re.sub(r"\s*(Discussion\s*\|\s*Link|Discussion|Link)\s*$", "", text, flags=re.I)
    return text


def scan_producthunt(limit: int = 30,
                     feed_url: str = "https://www.producthunt.com/feed") -> list[dict]:
    """Scan Product Hunt's public Atom feed for recent launches.

    Product Hunt's official GraphQL API needs an access token.  The public
    feed is intentionally treated as a weak launch/solution-side signal: it
    helps spot what makers are shipping, but does not prove revenue or pain.
    """

    try:
        import requests
        import xml.etree.ElementTree as ET
    except ImportError:
        logger.warning("requests not installed: pip install requests")
        return []

    results = []
    headers = {"User-Agent": "ode-opportunity-engine/0.1"}
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    try:
        resp = requests.get(feed_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning("Product Hunt feed returned %s", resp.status_code)
            return results

        root = ET.fromstring(resp.text)
        entries = root.findall("atom:entry", ns)

        for position, entry in enumerate(entries[:limit]):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            content_el = entry.find("atom:content", ns)
            published_el = entry.find("atom:published", ns)
            updated_el = entry.find("atom:updated", ns)
            id_el = entry.find("atom:id", ns)

            title = _clean_feed_text(title_el.text if title_el is not None else "")
            url = link_el.get("href", "") if link_el is not None else ""
            snippet = ""
            if content_el is not None:
                snippet = _clean_feed_text(" ".join(content_el.itertext()))

            strength = "strong" if position < 5 else "medium" if position < 15 else "weak"
            results.append({
                "source_id": "producthunt_feed",
                "source": "producthunt",
                "keyword": title,
                "title": title,
                "url": url,
                "summary": snippet,
                "score": 0,
                "comments": 0,
                "rank": position + 1,
                "strength": strength,
                "momentum": 0,
                "published": published_el.text if published_el is not None else "",
                "updated": updated_el.text if updated_el is not None else "",
                "external_id": id_el.text if id_el is not None else "",
            })
    except Exception as e:
        logger.warning("Product Hunt scan failed: %s", e)

    return results


# ---------------------------------------------------------------------------
# Aggregate scan
# ---------------------------------------------------------------------------

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
    """Run all configured scanners and return combined signal list."""
    signals = []

    if keywords:
        signals.extend(scan_google_trends(keywords, timeframe, geo))

    if hn_top > 0:
        signals.extend(scan_hackernews(hn_top))

    if subreddits:
        signals.extend(scan_reddit(subreddits))

    # Relevance scoring: attach score and filter noise
    if keywords and signals:
        for s in signals:
            s["relevance_score"] = round(_relevance_score(s, keywords), 2)
        # Keep signals with any keyword match, or strong/medium HN signals
        signals = [
            s for s in signals
            if s.get("relevance_score", 0) >= 0.1
            or s.get("strength") in ("强", "中")
        ]

    # Filter by domain keyword if specified
    if domain and signals:
        domain_lower = domain.lower()
        filtered = [
            s for s in signals
            if domain_lower in s.get("title", "").lower()
            or domain_lower in s.get("keyword", "").lower()
        ]
        # Keep all if filtering removes everything (domain might not be in titles)
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
    for s in signals:
        by_source.setdefault(s["source"], []).append(s)

    strength_order = {"强": 0, "中": 1, "弱": 2}

    for source, items in by_source.items():
        lines.append(f"## {source}")
        lines.append("| Strength | Content | Metrics |")
        lines.append("|----------|---------|---------|")
        for item in sorted(items, key=lambda x: strength_order.get(x.get("strength", "弱"), 3)):
            strength = item.get("strength", "—")
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

    strong = sum(1 for s in signals if s.get("strength") == "强")
    medium = sum(1 for s in signals if s.get("strength") == "中")
    weak = len(signals) - strong - medium
    lines.append(f"**Summary**: strong={strong} medium={medium} weak={weak}")

    return "\n".join(lines)
