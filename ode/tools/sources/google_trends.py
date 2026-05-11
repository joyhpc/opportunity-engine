"""Google Trends source adapter."""

from __future__ import annotations

import logging
import os

from ode.tools.sources.common import MEDIUM, STRONG, WEAK, append_note

logger = logging.getLogger(__name__)

SOURCE_ID = "google_trends"


def scan(keywords: list[str], timeframe: str = "today 3-m",
         geo: str = "", source_notes: list[dict] | None = None) -> list[dict]:
    """Scan Google Trends for keyword interest changes."""

    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed: pip install pytrends")
        append_note(
            source_notes,
            source_id=SOURCE_ID,
            status="unavailable",
            reason="missing_optional_dependency",
            dependency="pytrends",
        )
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
        except Exception as exc:
            logger.warning("Google Trends error for %s: %s", batch, exc)
            append_note(
                source_notes,
                source_id=SOURCE_ID,
                status="failed",
                reason="request_error",
                keywords=batch,
                error=str(exc),
            )
            continue

        if interest.empty:
            append_note(
                source_notes,
                source_id=SOURCE_ID,
                status="empty",
                keywords=batch,
            )
            continue

        for kw in batch:
            if kw not in interest.columns:
                continue
            series = interest[kw]
            recent = series.tail(4).mean()
            earlier = series.head(4).mean()
            momentum = ((recent - earlier) / max(earlier, 1)) * 100

            results.append({
                "source_id": SOURCE_ID,
                "source": SOURCE_ID,
                "keyword": kw,
                "title": kw,
                "current_interest": int(recent),
                "momentum": round(momentum, 1),
                "strength": STRONG if momentum > 50 else MEDIUM if momentum > 20 else WEAK,
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
                            "source_id": SOURCE_ID,
                            "source": "google_trends_rising",
                            "keyword": row["query"],
                            "title": row["query"],
                            "parent_keyword": kw,
                            "momentum": 0,
                            "strength": MEDIUM,
                        })
        except Exception:
            pass

    return results
