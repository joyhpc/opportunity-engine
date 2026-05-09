#!/usr/bin/env python3
"""财务模型工具 — 单位经济 + 盈亏平衡 + 敏感性分析

从假设参数出发，生成完整的财务预测和可视化报告。

Usage:
    python3 financial_model.py --mode rough --revenue-monthly 10000 --cogs-pct 30 --opex 5000
    python3 financial_model.py --mode full --config model_config.yaml
    python3 financial_model.py --demo
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class UnitEconomics:
    """单位经济模型"""
    arpu: float           # Average Revenue Per User (monthly)
    cac: float            # Customer Acquisition Cost
    cogs_per_user: float  # Cost of Goods Sold per user (monthly)
    churn_rate: float     # Monthly churn rate (%)

    @property
    def ltv(self) -> float:
        """Customer Lifetime Value"""
        if self.churn_rate <= 0:
            return self.arpu * 120  # cap at 10 years
        monthly_margin = self.arpu - self.cogs_per_user
        return monthly_margin / (self.churn_rate / 100)

    @property
    def ltv_cac_ratio(self) -> float:
        return self.ltv / self.cac if self.cac > 0 else float("inf")

    @property
    def payback_months(self) -> float:
        monthly_margin = self.arpu - self.cogs_per_user
        return self.cac / monthly_margin if monthly_margin > 0 else float("inf")

    @property
    def gross_margin_pct(self) -> float:
        return ((self.arpu - self.cogs_per_user) / self.arpu * 100) if self.arpu > 0 else 0


@dataclass
class ProjectionConfig:
    """预测配置"""
    months: int = 36
    initial_users: int = 0
    monthly_new_users: int = 100
    user_growth_rate: float = 10  # 月增长率(%)
    arpu: float = 29.99
    cac: float = 50.0
    cogs_pct: float = 20.0
    monthly_opex: float = 5000.0
    opex_growth_rate: float = 5.0  # 月增长率(%)


def project_revenue(config: ProjectionConfig) -> list[dict]:
    """生成月度收入预测"""
    rows = []
    users = config.initial_users
    monthly_new = config.monthly_new_users
    opex = config.monthly_opex
    churn_rate = 5.0  # 默认月流失率

    for month in range(1, config.months + 1):
        # 用户增长
        new_users = int(monthly_new)
        churned = int(users * churn_rate / 100)
        users = users + new_users - churned

        # 收入
        revenue = users * config.arpu
        cogs = revenue * config.cogs_pct / 100
        gross_profit = revenue - cogs
        cac_spend = new_users * config.cac
        total_cost = cogs + opex + cac_spend
        net_income = revenue - total_cost

        rows.append({
            "month": month,
            "users": users,
            "new_users": new_users,
            "churned": churned,
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "opex": round(opex, 2),
            "cac_spend": round(cac_spend, 2),
            "net_income": round(net_income, 2),
            "cumulative_income": 0,  # filled below
        })

        # 增长
        monthly_new *= (1 + config.user_growth_rate / 100)
        opex *= (1 + config.opex_growth_rate / 100 / 12)  # 月化

    # 累计
    cumulative = 0
    for row in rows:
        cumulative += row["net_income"]
        row["cumulative_income"] = round(cumulative, 2)

    return rows


def find_breakeven(projection: list[dict]) -> int | None:
    """找盈亏平衡月份"""
    for row in projection:
        if row["net_income"] > 0:
            return row["month"]
    return None


def sensitivity_analysis(base_config: ProjectionConfig,
                         param: str, variations: list[float]) -> list[dict]:
    """敏感性分析 — 关键参数变动对NPV的影响"""
    results = []
    for var in variations:
        config = ProjectionConfig(**{
            k: v for k, v in base_config.__dict__.items()
        })
        setattr(config, param, var)
        proj = project_revenue(config)

        # 简单NPV (年折现率12%, 月化)
        monthly_rate = 0.12 / 12
        npv = sum(
            row["net_income"] / (1 + monthly_rate) ** row["month"]
            for row in proj
        )
        breakeven = find_breakeven(proj)
        final_users = proj[-1]["users"]
        final_revenue = proj[-1]["revenue"]

        results.append({
            "param_value": var,
            "npv": round(npv, 2),
            "breakeven_month": breakeven,
            "final_users": final_users,
            "final_monthly_revenue": round(final_revenue, 2),
        })

    return results


def format_value(val: float) -> str:
    if abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    elif abs(val) >= 1e3:
        return f"${val/1e3:.1f}K"
    return f"${val:.0f}"


def format_rough_report(ue: UnitEconomics) -> str:
    """粗算模式报告"""
    lines = [
        "# 单位经济模型（粗算）",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 核心指标",
        f"| 指标 | 值 | 评价 |",
        f"|------|-----|------|",
        f"| ARPU (月) | ${ue.arpu:.2f} | — |",
        f"| CAC | ${ue.cac:.2f} | — |",
        f"| LTV | ${ue.ltv:.2f} | — |",
        f"| **LTV/CAC** | **{ue.ltv_cac_ratio:.1f}x** | {'🟢 健康' if ue.ltv_cac_ratio > 3 else '🟡 一般' if ue.ltv_cac_ratio > 1 else '🔴 危险'} |",
        f"| 回收期 | {ue.payback_months:.1f} 月 | {'🟢' if ue.payback_months < 6 else '🟡' if ue.payback_months < 12 else '🔴'} |",
        f"| 毛利率 | {ue.gross_margin_pct:.0f}% | {'🟢' if ue.gross_margin_pct > 60 else '🟡' if ue.gross_margin_pct > 40 else '🔴'} |",
        f"| 月流失率 | {ue.churn_rate:.1f}% | {'🟢' if ue.churn_rate < 3 else '🟡' if ue.churn_rate < 5 else '🔴'} |",
        "",
        "## 红线检查",
    ]

    checks = [
        ("LTV/CAC > 3", ue.ltv_cac_ratio > 3),
        ("毛利率 > 50%", ue.gross_margin_pct > 50),
        ("回收期 < 12月", ue.payback_months < 12),
        ("月流失率 < 5%", ue.churn_rate < 5),
    ]
    for label, passed in checks:
        lines.append(f"- {'✅' if passed else '❌'} {label}")

    all_pass = all(p for _, p in checks)
    lines.extend([
        "",
        f"**结论**: {'🟢 单位经济模型健康，建议继续' if all_pass else '⚠️ 存在风险项，需进一步验证'}",
    ])

    return "\n".join(lines)


def format_full_report(config: ProjectionConfig, projection: list[dict],
                       ue: UnitEconomics) -> str:
    """完整财务报告"""
    breakeven = find_breakeven(projection)

    lines = [
        "# 财务模型完整报告",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"预测期: {config.months} 个月",
        "",
        format_rough_report(ue),
        "",
        "---",
        "",
        "## 月度预测摘要（季度视图）",
        "",
        "| 季度 | 用户数 | 月收入 | 月净利 | 累计净利 |",
        "|------|--------|--------|--------|----------|",
    ]

    for row in projection:
        if row["month"] % 3 == 0:  # 每季度显示
            lines.append(
                f"| Q{row['month']//3} (M{row['month']}) | "
                f"{row['users']:,} | "
                f"{format_value(row['revenue'])} | "
                f"{format_value(row['net_income'])} | "
                f"{format_value(row['cumulative_income'])} |"
            )

    lines.extend([
        "",
        f"### 盈亏平衡: {'第 ' + str(breakeven) + ' 个月' if breakeven else '未在预测期内达到'}",
        "",
    ])

    # 增长曲线（ASCII）
    lines.extend(["## 用户增长曲线", ""])
    max_users = max(r["users"] for r in projection)
    for i in range(0, len(projection), 3):
        row = projection[i]
        bar_len = int(row["users"] / max(max_users, 1) * 40)
        lines.append(f"M{row['month']:2d} | {'█' * bar_len} {row['users']:,}")

    # 敏感性分析
    lines.extend([
        "",
        "## 敏感性分析",
        "",
        "### ARPU 变动影响",
        "| ARPU | NPV | 盈亏平衡月 |",
        "|------|-----|-----------|",
    ])

    arpu_vars = [config.arpu * m for m in [0.6, 0.8, 1.0, 1.2, 1.5]]
    arpu_results = sensitivity_analysis(config, "arpu", arpu_vars)
    for r in arpu_results:
        lines.append(
            f"| ${r['param_value']:.2f} | {format_value(r['npv'])} | "
            f"{'M' + str(r['breakeven_month']) if r['breakeven_month'] else 'N/A'} |"
        )

    lines.extend([
        "",
        "### CAC 变动影响",
        "| CAC | NPV | 盈亏平衡月 |",
        "|-----|-----|-----------|",
    ])

    cac_vars = [config.cac * m for m in [0.5, 0.75, 1.0, 1.5, 2.0]]
    cac_results = sensitivity_analysis(config, "cac", cac_vars)
    for r in cac_results:
        lines.append(
            f"| ${r['param_value']:.2f} | {format_value(r['npv'])} | "
            f"{'M' + str(r['breakeven_month']) if r['breakeven_month'] else 'N/A'} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="财务模型工具")
    parser.add_argument("--mode", choices=["rough", "full"], default="rough")
    parser.add_argument("--demo", action="store_true", help="演示模式")
    parser.add_argument("--config", type=str, help="配置文件 (YAML/JSON)")

    # 粗算模式参数
    parser.add_argument("--arpu", type=float, default=29.99, help="月ARPU")
    parser.add_argument("--cac", type=float, default=50, help="获客成本")
    parser.add_argument("--cogs-pct", type=float, default=20, help="COGS占比(%)")
    parser.add_argument("--churn", type=float, default=5, help="月流失率(%)")

    # 完整模式参数
    parser.add_argument("--months", type=int, default=36, help="预测月数")
    parser.add_argument("--initial-users", type=int, default=0)
    parser.add_argument("--monthly-new-users", type=int, default=100)
    parser.add_argument("--user-growth-rate", type=float, default=10)
    parser.add_argument("--monthly-opex", type=float, default=5000)

    parser.add_argument("-o", "--output", type=str)
    args = parser.parse_args()

    if args.demo:
        args.arpu = 39.99
        args.cac = 60
        args.cogs_pct = 15
        args.churn = 4
        args.mode = "full"
        args.monthly_new_users = 50
        args.user_growth_rate = 15
        args.monthly_opex = 3000

    ue = UnitEconomics(
        arpu=args.arpu,
        cac=args.cac,
        cogs_per_user=args.arpu * args.cogs_pct / 100,
        churn_rate=args.churn,
    )

    if args.mode == "rough":
        report = format_rough_report(ue)
    else:
        config = ProjectionConfig(
            months=args.months,
            initial_users=args.initial_users,
            monthly_new_users=args.monthly_new_users,
            user_growth_rate=args.user_growth_rate,
            arpu=args.arpu,
            cac=args.cac,
            cogs_pct=args.cogs_pct,
            monthly_opex=args.monthly_opex,
        )
        projection = project_revenue(config)
        report = format_full_report(config, projection, ue)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✅ 保存到: {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
