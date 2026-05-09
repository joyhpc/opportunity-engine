#!/usr/bin/env python3
"""市场规模估算器 — TAM/SAM/SOM 计算框架

支持自顶向下和自底向上两种方法，输出结构化估算报告。

Usage:
    python3 market_sizer.py --method topdown --market-size 50B --segment-pct 15 --geo-pct 30
    python3 market_sizer.py --method bottomup --users 500000 --price 29.99 --frequency 12 --capture-pct 2
    python3 market_sizer.py --interactive
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class MarketEstimate:
    """市场规模估算结果"""
    method: str
    tam: float          # Total Addressable Market
    sam: float          # Serviceable Addressable Market
    som: float          # Serviceable Obtainable Market
    tam_label: str
    sam_label: str
    som_label: str
    assumptions: list
    confidence: str     # 高/中/低
    currency: str = "USD"

    def format_value(self, val: float) -> str:
        if val >= 1e9:
            return f"${val/1e9:.1f}B"
        elif val >= 1e6:
            return f"${val/1e6:.1f}M"
        elif val >= 1e3:
            return f"${val/1e3:.0f}K"
        return f"${val:.0f}"


def topdown_estimate(market_size: float, segment_pct: float,
                     geo_pct: float, capture_pct: float = 5,
                     growth_rate: float = 0) -> MarketEstimate:
    """自顶向下估算

    TAM = 整体市场规模
    SAM = TAM × 细分市场比例 × 地域比例
    SOM = SAM × 可获取比例
    """
    tam = market_size
    sam = tam * (segment_pct / 100) * (geo_pct / 100)
    som = sam * (capture_pct / 100)

    assumptions = [
        f"整体市场规模: ${market_size/1e9:.1f}B（来源需标注）",
        f"目标细分市场占比: {segment_pct}%",
        f"目标地域占比: {geo_pct}%",
        f"预期市场份额: {capture_pct}%（3年内）",
    ]
    if growth_rate > 0:
        assumptions.append(f"年增长率: {growth_rate}%")

    est = MarketEstimate(
        method="自顶向下 (Top-Down)",
        tam=tam, sam=sam, som=som,
        tam_label="整体市场容量",
        sam_label="可服务市场（细分×地域）",
        som_label="可获取市场（3年目标）",
        assumptions=assumptions,
        confidence="中" if market_size < 1e10 else "低",
    )
    return est


def bottomup_estimate(target_users: int, price_per_unit: float,
                      frequency: int = 1, capture_pct: float = 2,
                      potential_users_total: int = None) -> MarketEstimate:
    """自底向上估算

    SOM = 目标用户数 × 客单价 × 频次 × 可获取比例
    SAM = 潜在用户总数 × 客单价 × 频次
    TAM = SAM × 扩展倍数
    """
    annual_revenue_per_user = price_per_unit * frequency
    total_potential = potential_users_total or (target_users * 20)

    som = target_users * annual_revenue_per_user * (capture_pct / 100)
    sam = total_potential * annual_revenue_per_user
    tam = sam * 3  # 假设周边市场是直接市场的3倍

    assumptions = [
        f"目标用户群: {target_users:,} 人",
        f"客单价: ${price_per_unit:.2f}/次",
        f"年购买频次: {frequency}次",
        f"年人均价值: ${annual_revenue_per_user:.2f}",
        f"潜在用户总数: {total_potential:,}",
        f"预期获取率: {capture_pct}%",
    ]

    est = MarketEstimate(
        method="自底向上 (Bottom-Up)",
        tam=tam, sam=sam, som=som,
        tam_label="广义市场（含周边）",
        sam_label="直接可服务用户 × ARPU",
        som_label="预期获取用户 × ARPU",
        assumptions=assumptions,
        confidence="中",
    )
    return est


def cross_validate(td: MarketEstimate, bu: MarketEstimate) -> dict:
    """交叉验证两种方法的一致性"""
    sam_ratio = td.sam / bu.sam if bu.sam > 0 else float("inf")
    som_ratio = td.som / bu.som if bu.som > 0 else float("inf")

    consistency = "一致" if 0.5 < sam_ratio < 2.0 else "有偏差" if 0.2 < sam_ratio < 5.0 else "严重偏离"

    return {
        "sam_ratio": round(sam_ratio, 2),
        "som_ratio": round(som_ratio, 2),
        "consistency": consistency,
        "recommendation": (
            "两种方法结果接近，估算可信度较高" if consistency == "一致"
            else "两种方法有偏差，建议复查假设" if consistency == "有偏差"
            else "⚠️ 两种方法严重偏离，需重新评估假设"
        ),
    }


def format_report(estimates: list[MarketEstimate], validation: dict = None) -> str:
    """生成 Markdown 格式估算报告"""
    lines = [
        "# 市场规模估算报告",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for est in estimates:
        lines.extend([
            f"## {est.method}",
            "",
            "| 层级 | 说明 | 规模 |",
            "|------|------|------|",
            f"| **TAM** | {est.tam_label} | {est.format_value(est.tam)} |",
            f"| **SAM** | {est.sam_label} | {est.format_value(est.sam)} |",
            f"| **SOM** | {est.som_label} | {est.format_value(est.som)} |",
            "",
            f"置信度: **{est.confidence}**",
            "",
            "### 关键假设",
        ])
        for i, a in enumerate(est.assumptions, 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    if validation:
        lines.extend([
            "## 交叉验证",
            f"- SAM 比值 (TD/BU): {validation['sam_ratio']}x",
            f"- SOM 比值 (TD/BU): {validation['som_ratio']}x",
            f"- 一致性: **{validation['consistency']}**",
            f"- 建议: {validation['recommendation']}",
            "",
        ])

    lines.extend([
        "## ⚠️ 注意事项",
        "- TAM/SAM/SOM 是粗略估算，用于判断量级而非精确数字",
        "- 所有市场数据来源需在决策前验证",
        "- 建议在 pt decision 中记录最终采纳的估算数字及依据",
    ])

    return "\n".join(lines)


def interactive_mode():
    """交互模式引导用户完成估算"""
    print("=" * 50)
    print("  市场规模估算器 — 交互模式")
    print("=" * 50)
    print()

    # 自顶向下
    print("── 自顶向下估算 ──")
    try:
        ms = float(input("整体市场规模（美元，如 5e9 = 50亿）: "))
        seg = float(input("目标细分市场占比（%）: "))
        geo = float(input("目标地域占比（%）: "))
        cap = float(input("预期市场份额（%，默认5）: ") or "5")
    except (ValueError, EOFError):
        print("输入无效", file=sys.stderr)
        return
    td = topdown_estimate(ms, seg, geo, cap)

    # 自底向上
    print("\n── 自底向上估算 ──")
    try:
        users = int(input("目标用户群规模: "))
        price = float(input("客单价（美元）: "))
        freq = int(input("年购买频次: "))
        bcap = float(input("预期获取率（%，默认2）: ") or "2")
    except (ValueError, EOFError):
        print("输入无效", file=sys.stderr)
        return
    bu = bottomup_estimate(users, price, freq, bcap)

    validation = cross_validate(td, bu)
    report = format_report([td, bu], validation)
    print("\n" + report)


def main():
    parser = argparse.ArgumentParser(
        description="市场规模估算器 — TAM/SAM/SOM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="method")

    # 自顶向下
    td = sub.add_parser("topdown", help="自顶向下估算")
    td.add_argument("--market-size", type=float, required=True, help="整体市场规模（美元）")
    td.add_argument("--segment-pct", type=float, required=True, help="目标细分占比（%）")
    td.add_argument("--geo-pct", type=float, required=True, help="目标地域占比（%）")
    td.add_argument("--capture-pct", type=float, default=5, help="预期份额（%，默认5）")

    # 自底向上
    bu = sub.add_parser("bottomup", help="自底向上估算")
    bu.add_argument("--users", type=int, required=True, help="目标用户数")
    bu.add_argument("--price", type=float, required=True, help="客单价（美元）")
    bu.add_argument("--frequency", type=int, default=12, help="年购买频次（默认12）")
    bu.add_argument("--capture-pct", type=float, default=2, help="获取率（%，默认2）")

    # 交互模式
    sub.add_parser("interactive", help="交互引导模式")

    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("-o", "--output", type=str, help="输出文件")

    args = parser.parse_args()

    if args.method == "interactive":
        interactive_mode()
        return

    if args.method == "topdown":
        est = topdown_estimate(args.market_size, args.segment_pct,
                               args.geo_pct, args.capture_pct)
    elif args.method == "bottomup":
        est = bottomup_estimate(args.users, args.price,
                                args.frequency, args.capture_pct)
    else:
        parser.print_help()
        return

    if args.format == "json":
        output = json.dumps(asdict(est), ensure_ascii=False, indent=2)
    else:
        output = format_report([est])

    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"✅ 保存到: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
