#!/usr/bin/env python3
"""趋势扫描器 — 多源信号采集工具

使用 pytrends + web API 扫描 Google Trends、HackerNews、Reddit 等
信号源的热度变化，输出结构化信号清单。

Usage:
    python3 trend_scanner.py --keywords "AI agent,MCP,vibe coding" --period 3m
    python3 trend_scanner.py --hn-top 30 --reddit "startup,SaaS"
    python3 trend_scanner.py --keywords "无人机,低空经济" --geo CN
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None


# ── Google Trends ─────────────────────────────────────────
def scan_google_trends(keywords: list[str], timeframe: str = "today 3-m",
                       geo: str = "") -> list[dict]:
    """扫描 Google Trends 获取关键词热度变化"""
    if TrendReq is None:
        print("⚠️  pytrends 未安装: pip install pytrends", file=sys.stderr)
        return []

    pytrends = TrendReq(hl="zh-CN", tz=480)
    results = []

    # 每次最多5个关键词
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo=geo)

        # 趋势数据
        interest = pytrends.interest_over_time()
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
                "current_interest": int(recent),
                "momentum_pct": round(momentum, 1),
                "signal_strength": "强" if momentum > 50 else "中" if momentum > 20 else "弱",
                "timeframe": timeframe,
                "geo": geo or "全球",
            })

        # 相关上升查询
        try:
            related = pytrends.related_queries()
            for kw in batch:
                if kw in related and related[kw]["rising"] is not None:
                    top_rising = related[kw]["rising"].head(5)
                    for _, row in top_rising.iterrows():
                        results.append({
                            "source": "google_trends_rising",
                            "keyword": row["query"],
                            "parent_keyword": kw,
                            "value": str(row["value"]),
                            "signal_strength": "中",
                        })
        except Exception:
            pass

    return results


# ── HackerNews ────────────────────────────────────────────
def scan_hackernews(top_n: int = 30) -> list[dict]:
    """扫描 HackerNews Top Stories"""
    if requests is None:
        print("⚠️  requests 未安装: pip install requests", file=sys.stderr)
        return []

    results = []
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10
        )
        story_ids = resp.json()[:top_n]

        for sid in story_ids:
            item = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                timeout=5
            ).json()
            if not item:
                continue
            results.append({
                "source": "hackernews",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "signal_strength": "强" if item.get("score", 0) > 200 else "中" if item.get("score", 0) > 50 else "弱",
                "time": datetime.fromtimestamp(item.get("time", 0)).isoformat(),
            })
    except Exception as e:
        print(f"⚠️  HN 扫描失败: {e}", file=sys.stderr)

    return results


# ── Reddit ────────────────────────────────────────────────
def scan_reddit(subreddits: list[str], limit: int = 10) -> list[dict]:
    """扫描 Reddit 子版块热帖"""
    if requests is None:
        print("⚠️  requests 未安装: pip install requests", file=sys.stderr)
        return []

    results = []
    headers = {"User-Agent": "OpportunityDetector/1.0"}

    for sub in subreddits:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}",
                headers=headers, timeout=10
            )
            data = resp.json()
            for post in data.get("data", {}).get("children", []):
                d = post["data"]
                results.append({
                    "source": f"reddit/r/{sub}",
                    "title": d.get("title", ""),
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "score": d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                    "signal_strength": "强" if d.get("score", 0) > 500 else "中" if d.get("score", 0) > 100 else "弱",
                })
        except Exception as e:
            print(f"⚠️  Reddit r/{sub} 扫描失败: {e}", file=sys.stderr)

    return results


# ── 输出 ──────────────────────────────────────────────────
def format_report(signals: list[dict], format: str = "markdown") -> str:
    """格式化信号报告"""
    if format == "json":
        return json.dumps(signals, ensure_ascii=False, indent=2)

    lines = [
        f"# 趋势扫描报告",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"信号总数: {len(signals)}",
        "",
    ]

    # 按来源分组
    by_source = {}
    for s in signals:
        src = s["source"]
        by_source.setdefault(src, []).append(s)

    for source, items in by_source.items():
        lines.append(f"## {source}")
        lines.append(f"| 信号强度 | 内容 | 指标 |")
        lines.append(f"|---------|------|------|")
        for item in sorted(items, key=lambda x: {"强": 0, "中": 1, "弱": 2}.get(x.get("signal_strength", "弱"), 3)):
            strength = item.get("signal_strength", "—")
            if "keyword" in item:
                content = item["keyword"]
                metric = f"热度={item.get('current_interest', '—')}, 动量={item.get('momentum_pct', '—')}%"
            elif "title" in item:
                content = item["title"][:60]
                metric = f"▲{item.get('score', 0)} 💬{item.get('comments', 0)}"
            else:
                content = str(item)
                metric = ""
            lines.append(f"| {strength} | {content} | {metric} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="趋势扫描器 — 多源信号采集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --keywords "AI agent,MCP protocol"
  %(prog)s --hn-top 20
  %(prog)s --reddit "startup,SaaS,Entrepreneur"
  %(prog)s --keywords "低空经济" --geo CN --format json
        """
    )
    parser.add_argument("--keywords", type=str, help="Google Trends 关键词（逗号分隔）")
    parser.add_argument("--period", type=str, default="today 3-m",
                        help="时间范围 (默认: today 3-m)")
    parser.add_argument("--geo", type=str, default="", help="地区代码 (如 CN, US)")
    parser.add_argument("--hn-top", type=int, help="HackerNews Top N 条")
    parser.add_argument("--reddit", type=str, help="Reddit 子版块（逗号分隔）")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("-o", "--output", type=str, help="输出文件路径")

    args = parser.parse_args()
    all_signals = []

    if args.keywords:
        kws = [k.strip() for k in args.keywords.split(",")]
        print(f"🔍 扫描 Google Trends: {kws}...", file=sys.stderr)
        all_signals.extend(scan_google_trends(kws, args.period, args.geo))

    if args.hn_top:
        print(f"🔍 扫描 HackerNews Top {args.hn_top}...", file=sys.stderr)
        all_signals.extend(scan_hackernews(args.hn_top))

    if args.reddit:
        subs = [s.strip() for s in args.reddit.split(",")]
        print(f"🔍 扫描 Reddit: {subs}...", file=sys.stderr)
        all_signals.extend(scan_reddit(subs))

    if not all_signals and not (args.keywords or args.hn_top or args.reddit):
        parser.print_help()
        return

    report = format_report(all_signals, args.format)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✅ 报告已保存: {args.output}", file=sys.stderr)
    else:
        print(report)

    # 统计摘要
    strong = sum(1 for s in all_signals if s.get("signal_strength") == "强")
    medium = sum(1 for s in all_signals if s.get("signal_strength") == "中")
    print(f"\n📊 信号统计: 强={strong} 中={medium} 弱={len(all_signals)-strong-medium}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
