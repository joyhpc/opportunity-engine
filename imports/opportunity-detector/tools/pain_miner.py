#!/usr/bin/env python3
"""痛点挖掘器 — 从 Reddit/HN 评论中挖掘用户真实痛点

核心理念 (YC): "找到用户的'痛点饮水坑' — 人们主动求解的地方"
不是你觉得痛，是用户自己在喊痛。

Usage:
    python3 pain_miner.py --reddit "SaaS,startups" --keywords "frustrating,hate,wish,need"
    python3 pain_miner.py --hn --keywords "broken,annoying,why cant"
    python3 pain_miner.py --reddit "teachers,education" --keywords "waste time,tedious" --top 20
    python3 pain_miner.py --demo
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# 痛点信号词（中英文）
PAIN_SIGNALS_EN = [
    "frustrated", "frustrating", "annoying", "hate", "broken",
    "wish there was", "why can't", "waste of time", "tedious",
    "painful", "nightmare", "impossible", "ridiculous", "terrible",
    "need a better", "looking for", "any alternatives", "switched from",
    "gave up on", "can't believe", "so tired of", "fed up",
    "does anyone know", "help me find", "recommendation for",
]

PAIN_SIGNALS_ZH = [
    "太难用", "垃圾", "坑", "浪费时间", "有没有替代",
    "求推荐", "怎么解决", "崩溃", "受不了", "吐槽",
    "为什么不能", "太贵了", "太慢了", "bug太多",
]

PAIN_SEVERITY = {
    "actively_seeking": {"weight": 10, "keywords": [
        "looking for", "any alternatives", "recommendation", "switched from",
        "求推荐", "有没有替代",
    ]},
    "strong_emotion": {"weight": 8, "keywords": [
        "hate", "nightmare", "impossible", "gave up", "fed up",
        "崩溃", "受不了", "垃圾",
    ]},
    "frustration": {"weight": 6, "keywords": [
        "frustrated", "annoying", "tedious", "painful",
        "太难用", "浪费时间", "吐槽",
    ]},
    "wish": {"weight": 4, "keywords": [
        "wish there was", "why can't", "need a better",
        "为什么不能",
    ]},
}


def classify_severity(text: str) -> tuple[str, int]:
    """对文本进行痛点严重度分类"""
    text_lower = text.lower()
    for level, config in PAIN_SEVERITY.items():
        for kw in config["keywords"]:
            if kw.lower() in text_lower:
                return level, config["weight"]
    return "mild", 2


def extract_pain_signals(text: str) -> list[str]:
    """从文本中提取匹配的痛点信号词"""
    text_lower = text.lower()
    found = []
    for signal in PAIN_SIGNALS_EN + PAIN_SIGNALS_ZH:
        if signal.lower() in text_lower:
            found.append(signal)
    return found


# ── Reddit 挖掘 ──────────────────────────────────────────
def mine_reddit(subreddits: list[str], keywords: list[str] = None,
                limit: int = 50) -> list[dict]:
    """从 Reddit 子版块中挖掘痛点"""
    if requests is None:
        print("⚠️  requests 未安装: pip install requests", file=sys.stderr)
        return []

    headers = {"User-Agent": "PainMiner/1.0"}
    results = []

    for sub in subreddits:
        # 搜索痛点关键词
        search_terms = keywords or ["frustrated", "hate", "looking for alternative"]
        for term in search_terms:
            try:
                resp = requests.get(
                    f"https://www.reddit.com/r/{sub}/search.json",
                    params={"q": term, "sort": "relevance", "limit": min(limit, 25),
                            "restrict_sr": "on", "t": "year"},
                    headers=headers, timeout=10,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for post in data.get("data", {}).get("children", []):
                    d = post["data"]
                    title = d.get("title", "")
                    selftext = d.get("selftext", "")[:500]
                    full_text = f"{title} {selftext}"

                    signals = extract_pain_signals(full_text)
                    if not signals and not keywords:
                        continue

                    severity, weight = classify_severity(full_text)

                    results.append({
                        "source": f"reddit/r/{sub}",
                        "title": title,
                        "text": selftext[:300] if selftext else "",
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                        "score": d.get("score", 0),
                        "comments": d.get("num_comments", 0),
                        "severity": severity,
                        "severity_weight": weight,
                        "signals": signals,
                        "search_term": term,
                    })
            except Exception as e:
                print(f"⚠️  Reddit r/{sub} 搜索 '{term}' 失败: {e}", file=sys.stderr)

    # 去重（基于URL）
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    return sorted(unique, key=lambda x: x["severity_weight"], reverse=True)


# ── HackerNews 挖掘 ──────────────────────────────────────
def mine_hackernews(keywords: list[str] = None, limit: int = 30) -> list[dict]:
    """从 HackerNews 搜索 API 挖掘痛点"""
    if requests is None:
        print("⚠️  requests 未安装: pip install requests", file=sys.stderr)
        return []

    results = []
    search_terms = keywords or ["frustrated with", "why is", "looking for alternative"]

    for term in search_terms:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": term, "tags": "story", "hitsPerPage": min(limit, 20)},
                timeout=10,
            )
            data = resp.json()
            for hit in data.get("hits", []):
                title = hit.get("title", "")
                severity, weight = classify_severity(title)
                signals = extract_pain_signals(title)

                results.append({
                    "source": "hackernews",
                    "title": title,
                    "text": "",
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                    "score": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                    "severity": severity,
                    "severity_weight": weight,
                    "signals": signals,
                    "search_term": term,
                })
        except Exception as e:
            print(f"⚠️  HN 搜索 '{term}' 失败: {e}", file=sys.stderr)

    return sorted(results, key=lambda x: x["severity_weight"], reverse=True)


# ── 分析与聚类 ────────────────────────────────────────────
def cluster_pains(results: list[dict]) -> dict:
    """对挖掘到的痛点进行简单聚类分析"""
    severity_counts = Counter(r["severity"] for r in results)
    signal_counts = Counter(s for r in results for s in r.get("signals", []))
    source_counts = Counter(r["source"] for r in results)

    # 高价值痛点 = 高严重度 + 高参与度
    high_value = [
        r for r in results
        if r["severity_weight"] >= 8 or (r["severity_weight"] >= 6 and r.get("comments", 0) > 10)
    ]

    return {
        "total_signals": len(results),
        "severity_distribution": dict(severity_counts),
        "top_signal_words": signal_counts.most_common(10),
        "source_distribution": dict(source_counts),
        "high_value_count": len(high_value),
        "high_value_pains": high_value[:10],
    }


def format_report(results: list[dict], analysis: dict, top_n: int = 20) -> str:
    """生成痛点挖掘报告"""
    lines = [
        "# 痛点挖掘报告",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"总信号数: {analysis['total_signals']}",
        f"高价值痛点: {analysis['high_value_count']}",
        "",
    ]

    # 严重度分布
    lines.extend([
        "## 严重度分布",
        "| 级别 | 数量 | 说明 |",
        "|------|------|------|",
    ])
    severity_labels = {
        "actively_seeking": "🔴 主动求解 (10分)",
        "strong_emotion": "🟠 强烈情绪 (8分)",
        "frustration": "🟡 明确不满 (6分)",
        "wish": "🟢 期望改善 (4分)",
        "mild": "⚪ 轻微提及 (2分)",
    }
    for level, label in severity_labels.items():
        count = analysis["severity_distribution"].get(level, 0)
        if count > 0:
            lines.append(f"| {label} | {count} | |")

    # 高频痛点信号词
    if analysis["top_signal_words"]:
        lines.extend(["", "## 高频痛点信号词"])
        for word, count in analysis["top_signal_words"]:
            lines.append(f"- **\"{word}\"** × {count}")

    # 高价值痛点详情
    lines.extend(["", "## 高价值痛点 (Top)", ""])
    for i, r in enumerate(results[:top_n], 1):
        severity_icon = {"actively_seeking": "🔴", "strong_emotion": "🟠",
                         "frustration": "🟡", "wish": "🟢"}.get(r["severity"], "⚪")
        lines.extend([
            f"### {i}. {severity_icon} {r['title'][:80]}",
            f"- **来源**: {r['source']} | ▲{r['score']} 💬{r['comments']}",
            f"- **严重度**: {r['severity']} ({r['severity_weight']}/10)",
            f"- **信号词**: {', '.join(r['signals']) if r['signals'] else '关键词匹配'}",
            f"- **链接**: {r['url']}",
        ])
        if r.get("text"):
            lines.append(f"- **摘要**: {r['text'][:200]}...")
        lines.append("")

    # 机会洞察
    lines.extend([
        "---",
        "## 机会洞察",
        "",
        "### 如何使用这份报告",
        "1. **关注🔴主动求解类** — 这些人正在找解决方案，是最佳早期用户",
        "2. **看评论数** — 高评论 = 共鸣强，不是个别现象",
        "3. **去原帖看回复** — 了解人们目前在用什么替代方案",
        "4. **反向访谈** — 联系发帖者，问 \"你现在怎么解决这个问题的？\"",
        "",
        "### 下一步",
        "- 将高价值痛点录入 `pt poc --add \"验证: [痛点描述]\" --metric \"[红线指标]\"`",
        "- 用 `opportunity_scorer.py` 对痛点对应的机会进行评分",
    ])

    return "\n".join(lines)


def run_demo() -> tuple[list[dict], dict]:
    """演示模式 — 使用模拟数据"""
    demo_results = [
        {
            "source": "reddit/r/SaaS", "title": "I'm so frustrated with Notion's pricing",
            "text": "We're a 50-person team and Notion just doubled their price...",
            "url": "https://reddit.com/r/SaaS/example1", "score": 342, "comments": 87,
            "severity": "strong_emotion", "severity_weight": 8,
            "signals": ["frustrated"], "search_term": "frustrated",
        },
        {
            "source": "reddit/r/startups", "title": "Looking for alternatives to Intercom - too expensive",
            "text": "We're paying $500/mo for Intercom and it feels like overkill for our stage...",
            "url": "https://reddit.com/r/startups/example2", "score": 156, "comments": 43,
            "severity": "actively_seeking", "severity_weight": 10,
            "signals": ["looking for", "any alternatives"], "search_term": "looking for alternative",
        },
        {
            "source": "hackernews", "title": "Why can't invoicing software just be simple?",
            "text": "", "url": "https://news.ycombinator.com/item?id=example3",
            "score": 89, "comments": 67, "severity": "frustration", "severity_weight": 6,
            "signals": ["why can't"], "search_term": "why can't",
        },
        {
            "source": "reddit/r/Entrepreneur", "title": "Gave up on Shopify, built my own solution",
            "text": "After 2 years of fighting with Shopify's limitations for digital products...",
            "url": "https://reddit.com/r/Entrepreneur/example4", "score": 521, "comments": 134,
            "severity": "actively_seeking", "severity_weight": 10,
            "signals": ["gave up on"], "search_term": "gave up on",
        },
        {
            "source": "reddit/r/SaaS", "title": "Any good open source CRM? Salesforce is a nightmare",
            "text": "Small team, 200 contacts, Salesforce is massive overkill...",
            "url": "https://reddit.com/r/SaaS/example5", "score": 234, "comments": 56,
            "severity": "actively_seeking", "severity_weight": 10,
            "signals": ["nightmare", "any alternatives"], "search_term": "looking for alternative",
        },
        {
            "source": "hackernews", "title": "I wish there was a simpler way to do A/B testing",
            "text": "", "url": "https://news.ycombinator.com/item?id=example6",
            "score": 45, "comments": 23, "severity": "wish", "severity_weight": 4,
            "signals": ["wish there was"], "search_term": "wish there was",
        },
        {
            "source": "reddit/r/webdev", "title": "Hate how complicated deployment has become",
            "text": "Remember when you could just FTP files? Now it's Docker, K8s, CI/CD...",
            "url": "https://reddit.com/r/webdev/example7", "score": 892, "comments": 245,
            "severity": "strong_emotion", "severity_weight": 8,
            "signals": ["hate"], "search_term": "hate",
        },
    ]
    analysis = cluster_pains(demo_results)
    return demo_results, analysis


def main():
    parser = argparse.ArgumentParser(
        description="痛点挖掘器 — 从社区评论中发现赚钱机会",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --reddit "SaaS,startups" --keywords "frustrated,hate,alternative"
  %(prog)s --hn --keywords "broken,annoying"
  %(prog)s --reddit "teachers" --keywords "waste time" --top 30
  %(prog)s --demo
        """
    )
    parser.add_argument("--reddit", type=str, help="Reddit 子版块（逗号分隔）")
    parser.add_argument("--hn", action="store_true", help="搜索 HackerNews")
    parser.add_argument("--keywords", type=str, help="搜索关键词（逗号分隔，默认使用内置痛点词）")
    parser.add_argument("--top", type=int, default=20, help="显示 Top N 条（默认20）")
    parser.add_argument("--demo", action="store_true", help="演示模式")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("-o", "--output", type=str, help="输出文件路径")

    args = parser.parse_args()

    if args.demo:
        results, analysis = run_demo()
    else:
        keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
        results = []

        if args.reddit:
            subs = [s.strip() for s in args.reddit.split(",")]
            print(f"🔍 挖掘 Reddit: {subs}...", file=sys.stderr)
            results.extend(mine_reddit(subs, keywords, args.top))

        if args.hn:
            print(f"🔍 挖掘 HackerNews...", file=sys.stderr)
            results.extend(mine_hackernews(keywords, args.top))

        if not results and not (args.reddit or args.hn):
            parser.print_help()
            return

        analysis = cluster_pains(results)

    if args.format == "json":
        output = json.dumps({"results": results, "analysis": analysis},
                            ensure_ascii=False, indent=2)
    else:
        output = format_report(results, analysis, args.top)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"✅ 报告已保存: {args.output}", file=sys.stderr)
    else:
        print(output)

    print(f"\n📊 挖掘统计: 总{analysis['total_signals']}条, 高价值{analysis['high_value_count']}条",
          file=sys.stderr)


if __name__ == "__main__":
    main()
