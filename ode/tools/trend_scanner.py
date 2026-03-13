"""趋势扫描器 — 多源信号采集 (重构为库函数).

Scans Google Trends, HackerNews, Reddit for trend signals.
Returns structured signal dicts suitable for Signal model.
"""

from __future__ import annotations

import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Google Trends
# ---------------------------------------------------------------------------

def scan_google_trends(keywords: list[str], timeframe: str = "today 3-m",
                       geo: str = "") -> list[dict]:
    """Scan Google Trends for keyword interest changes."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("pytrends not installed: pip install pytrends", file=sys.stderr)
        return []

    pytrends = TrendReq(hl="zh-CN", tz=480)
    results = []

    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        try:
            pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo=geo)
            interest = pytrends.interest_over_time()
        except Exception as e:
            print(f"Google Trends error for {batch}: {e}", file=sys.stderr)
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
        print("requests not installed: pip install requests", file=sys.stderr)
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

        for sid in story_ids:
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=5,
                ).json()
                if not item or not isinstance(item, dict):
                    continue
                score = item.get("score", 0)
                results.append({
                    "source": "hackernews",
                    "keyword": "",
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "score": score,
                    "comments": item.get("descendants", 0),
                    "strength": "强" if score > 200 else "中" if score > 50 else "弱",
                    "momentum": 0,
                    "time": datetime.fromtimestamp(item.get("time", 0)).isoformat(),
                })
            except Exception:
                continue
    except Exception as e:
        print(f"HN scan failed: {e}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

def scan_reddit(subreddits: list[str], limit: int = 10) -> list[dict]:
    """Scan Reddit subreddits for hot posts."""
    try:
        import requests
    except ImportError:
        print("requests not installed: pip install requests", file=sys.stderr)
        return []

    results = []
    headers = {"User-Agent": "ODE/1.0"}

    for sub in subreddits:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}",
                headers=headers, timeout=10,
            )
            data = resp.json()
            for post in data.get("data", {}).get("children", []):
                d = post["data"]
                score = d.get("score", 0)
                results.append({
                    "source": f"reddit/r/{sub}",
                    "keyword": "",
                    "title": d.get("title", ""),
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "score": score,
                    "comments": d.get("num_comments", 0),
                    "strength": "强" if score > 500 else "中" if score > 100 else "弱",
                    "momentum": 0,
                })
        except Exception as e:
            print(f"Reddit r/{sub} scan failed: {e}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# Aggregate scan
# ---------------------------------------------------------------------------

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
