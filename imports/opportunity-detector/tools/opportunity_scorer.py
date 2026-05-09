#!/usr/bin/env python3
"""机会评分系统 v2 — YC/a16z 标准 + 红线检查 + 多维加权

v2 改进 (基于 2025-2026 最佳实践):
- 新增"验证强度"维度 (YC MVT 方法: 10人付费测试)
- 新增"AI-Native 潜力"维度 (a16z: 是否重构系统而非只是自动化)
- 红线检查: 任一红线触发 → 强制 Kill，不看总分
- 建议输出: 基于得分分布给出具体下一步行动

Usage:
    python3 opportunity_scorer.py --interactive
    python3 opportunity_scorer.py --data opportunity.yaml
    python3 opportunity_scorer.py --demo
    python3 opportunity_scorer.py --demo --framework v1   # 使用旧版评分框架
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ── 评分框架 v2 ──────────────────────────────────────────
FRAMEWORK_V2 = {
    "name": "机会评估评分卡 v2 (YC/a16z 标准)",
    "dimensions": [
        {
            "id": "market",
            "name": "市场吸引力",
            "weight": 25,
            "criteria": [
                {"id": "tam_size", "name": "市场规模", "description": "TAM > $1B = 10, > $100M = 7, > $10M = 4, < $10M = 2"},
                {"id": "growth", "name": "增长速度", "description": "CAGR > 20% = 10, > 10% = 7, > 5% = 4, < 5% = 2"},
                {"id": "timing", "name": "进入时机", "description": "早期增长 = 10, 主流增长 = 7, 成熟期 = 4, 衰退 = 1"},
            ],
        },
        {
            "id": "competition",
            "name": "竞争态势",
            "weight": 15,
            "criteria": [
                {"id": "intensity", "name": "竞争强度", "description": "蓝海 = 10, 少量竞品 = 7, 红海 = 3, 巨头垄断 = 1"},
                {"id": "barrier", "name": "进入壁垒", "description": "低壁垒 = 10（容易进入）, 中 = 6, 高 = 3"},
                {"id": "moat_potential", "name": "护城河潜力", "description": "强网络效应/数据壁垒 = 10, 品牌/规模 = 6, 弱 = 2"},
            ],
        },
        {
            "id": "capability",
            "name": "能力匹配",
            "weight": 15,
            "criteria": [
                {"id": "skill_match", "name": "技能匹配度", "description": "核心技能已具备 = 10, 需少量学习 = 7, 需大量学习 = 3"},
                {"id": "resource_need", "name": "资源需求", "description": "Solo可做 = 10, 需1-2人 = 7, 需团队 = 4, 需融资 = 2"},
                {"id": "time_to_market", "name": "上市时间", "description": "< 2周 = 10, < 1月 = 8, < 3月 = 5, > 3月 = 2"},
            ],
        },
        {
            "id": "economics",
            "name": "经济可行性",
            "weight": 25,
            "criteria": [
                {"id": "ltv_cac", "name": "LTV/CAC 比", "description": "LTV/CAC > 5 = 10, > 3 = 8, > 1 = 5, < 1 = 1"},
                {"id": "margin", "name": "毛利率", "description": "> 80% = 10, > 60% = 8, > 40% = 5, < 40% = 2"},
                {"id": "payback", "name": "回收期", "description": "< 1月 = 10, < 3月 = 8, < 6月 = 5, > 6月 = 2"},
            ],
        },
        {
            "id": "validation",
            "name": "验证强度 (YC MVT)",
            "weight": 10,
            "criteria": [
                {"id": "pain_evidence", "name": "痛点证据", "description": "用户主动求解 = 10, 访谈确认 = 7, 推测 = 3, 无证据 = 1"},
                {"id": "willingness_to_pay", "name": "付费意愿", "description": "已收到钱 = 10, 口头承诺 = 6, 调研说愿意 = 3, 未验证 = 1"},
                {"id": "mvt_result", "name": "最小可行测试", "description": "10+人付费 = 10, 5+人付费 = 7, 有注册 = 4, 未测试 = 1"},
            ],
        },
        {
            "id": "ai_native",
            "name": "AI-Native 潜力 (a16z)",
            "weight": 10,
            "criteria": [
                {"id": "system_rethink", "name": "系统重构度", "description": "彻底重构体验 = 10, 显著改进 = 7, 锦上添花 = 4, 不相关 = 5"},
                {"id": "data_loop", "name": "数据飞轮", "description": "使用越多越智能 = 10, 有数据积累 = 6, 无数据壁垒 = 3"},
                {"id": "compound_advantage", "name": "复利优势", "description": "AI强化商业模式 = 10, AI降低成本 = 7, AI可选 = 4"},
            ],
        },
    ],
    "thresholds": {
        "go": 70,
        "maybe": 50,
        "kill": 50,
    },
    # v2 新增: 红线检查 — 任一触发即 Kill，不看总分
    "redlines": [
        {"id": "no_pain", "name": "无真实痛点", "condition": "pain_evidence <= 2", "message": "找不到用户主动求解的证据，机会可能是伪需求"},
        {"id": "no_margin", "name": "毛利过低", "condition": "margin <= 2", "message": "毛利率 < 40%，难以支撑增长"},
        {"id": "giant_moat", "name": "巨头壁垒", "condition": "intensity <= 1 and barrier <= 3", "message": "巨头垄断且壁垒高，正面攻击几乎不可能"},
        {"id": "too_slow", "name": "上市太慢", "condition": "time_to_market <= 2 and resource_need <= 3", "message": "需要大量资源且耗时长，Solo founder 不适合"},
    ],
}

# v1 框架保留向后兼容
FRAMEWORK_V1 = {
    "name": "机会评估评分卡 v1",
    "dimensions": [
        {
            "id": "market", "name": "市场吸引力", "weight": 30,
            "criteria": [
                {"id": "tam_size", "name": "市场规模", "description": "TAM > $1B = 10, > $100M = 7, > $10M = 4, < $10M = 2"},
                {"id": "growth", "name": "增长速度", "description": "CAGR > 20% = 10, > 10% = 7, > 5% = 4, < 5% = 2"},
                {"id": "timing", "name": "进入时机", "description": "早期增长 = 10, 主流增长 = 7, 成熟期 = 4, 衰退 = 1"},
            ],
        },
        {
            "id": "competition", "name": "竞争态势", "weight": 20,
            "criteria": [
                {"id": "intensity", "name": "竞争强度", "description": "蓝海 = 10, 少量竞品 = 7, 红海 = 3, 巨头垄断 = 1"},
                {"id": "barrier", "name": "进入壁垒", "description": "低壁垒 = 10, 中 = 6, 高 = 3"},
                {"id": "moat_potential", "name": "护城河潜力", "description": "强可防御性 = 10, 中 = 6, 弱 = 2"},
            ],
        },
        {
            "id": "capability", "name": "能力匹配", "weight": 20,
            "criteria": [
                {"id": "skill_match", "name": "技能匹配度", "description": "核心技能已具备 = 10, 需少量学习 = 7, 需大量学习 = 3"},
                {"id": "resource_need", "name": "资源需求", "description": "低投入 = 10, 中等 = 6, 高投入 = 3"},
                {"id": "time_to_market", "name": "上市时间", "description": "< 1月 = 10, < 3月 = 7, < 6月 = 4, > 6月 = 2"},
            ],
        },
        {
            "id": "economics", "name": "经济可行性", "weight": 30,
            "criteria": [
                {"id": "ltv_cac", "name": "LTV/CAC 比", "description": "LTV/CAC > 5 = 10, > 3 = 8, > 1 = 5, < 1 = 1"},
                {"id": "margin", "name": "毛利率", "description": "> 80% = 10, > 60% = 8, > 40% = 5, < 40% = 2"},
                {"id": "payback", "name": "回收期", "description": "< 3月 = 10, < 6月 = 7, < 12月 = 4, > 12月 = 2"},
            ],
        },
    ],
    "thresholds": {"go": 70, "maybe": 50, "kill": 50},
}

FRAMEWORKS = {"v1": FRAMEWORK_V1, "v2": FRAMEWORK_V2}


@dataclass
class ScoringResult:
    opportunity_name: str
    total_score: float
    max_score: float
    percentage: float
    dimension_scores: dict
    verdict: str
    details: list
    redline_violations: list = field(default_factory=list)
    weakest_dimension: str = ""
    strongest_dimension: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))


def check_redlines(scores: dict, redlines: list) -> list[dict]:
    """检查红线 — 任一触发即强制 Kill"""
    violations = []
    for rl in redlines:
        # 简单条件解析: "field <= N" 或 "field1 <= N and field2 <= M"
        parts = rl["condition"].split(" and ")
        all_triggered = True
        for part in parts:
            tokens = part.strip().split()
            if len(tokens) == 3:
                field_id, op, threshold = tokens[0], tokens[1], int(tokens[2])
                value = scores.get(field_id, 5)
                if op == "<=" and not (value <= threshold):
                    all_triggered = False
                elif op == "<" and not (value < threshold):
                    all_triggered = False
                elif op == ">=" and not (value >= threshold):
                    all_triggered = False
            else:
                all_triggered = False

        if all_triggered:
            violations.append({
                "id": rl["id"],
                "name": rl["name"],
                "message": rl["message"],
            })

    return violations


def score_opportunity(name: str, scores: dict, framework: dict = None) -> ScoringResult:
    """计算机会综合得分"""
    fw = framework or FRAMEWORK_V2
    dimension_scores = {}
    details = []
    total_weighted = 0
    max_weighted = 0

    for dim in fw["dimensions"]:
        dim_scores = []
        for crit in dim["criteria"]:
            score = scores.get(crit["id"], 5)
            score = max(1, min(10, score))
            dim_scores.append(score)
            details.append({
                "dimension": dim["name"],
                "criterion": crit["name"],
                "score": score,
                "max": 10,
            })

        dim_avg = sum(dim_scores) / len(dim_scores)
        dim_weighted = dim_avg * dim["weight"] / 100
        dimension_scores[dim["name"]] = {
            "average": round(dim_avg, 1),
            "weight": dim["weight"],
            "weighted": round(dim_weighted, 1),
        }
        total_weighted += dim_weighted
        max_weighted += 10 * dim["weight"] / 100

    percentage = (total_weighted / max_weighted) * 100 if max_weighted > 0 else 0

    # 红线检查
    redline_violations = []
    if "redlines" in fw:
        redline_violations = check_redlines(scores, fw["redlines"])

    # 最弱/最强维度
    sorted_dims = sorted(dimension_scores.items(), key=lambda x: x[1]["average"])
    weakest = sorted_dims[0][0] if sorted_dims else ""
    strongest = sorted_dims[-1][0] if sorted_dims else ""

    # 判定
    if redline_violations:
        verdict = f"🔴 KILL — 触发 {len(redline_violations)} 条红线"
    else:
        thresholds = fw.get("thresholds", FRAMEWORK_V2["thresholds"])
        if percentage >= thresholds["go"]:
            verdict = "🟢 GO — 值得深入"
        elif percentage >= thresholds["maybe"]:
            verdict = "🟡 MAYBE — 需更多验证"
        else:
            verdict = "🔴 KILL — 建议放弃"

    return ScoringResult(
        opportunity_name=name,
        total_score=round(total_weighted, 1),
        max_score=round(max_weighted, 1),
        percentage=round(percentage, 1),
        dimension_scores=dimension_scores,
        verdict=verdict,
        details=details,
        redline_violations=redline_violations,
        weakest_dimension=weakest,
        strongest_dimension=strongest,
    )


def format_report(result: ScoringResult) -> str:
    """生成评分报告"""
    lines = [
        "# 机会评分报告",
        f"**机会**: {result.opportunity_name}",
        f"**时间**: {result.timestamp}",
        "",
        f"## 综合评分: {result.percentage:.0f}/100",
        f"### {result.verdict}",
        "",
    ]

    # 红线告警
    if result.redline_violations:
        lines.extend([
            "## 红线告警",
            "",
        ])
        for v in result.redline_violations:
            lines.append(f"- **{v['name']}**: {v['message']}")
        lines.extend([
            "",
            "> 红线触发 = 强制 Kill。总分再高也不改变此判定。",
            "> 除非你有独特洞察能证明红线条件不适用，否则建议立即停止。",
            "",
        ])

    # 维度得分
    lines.extend([
        "## 维度得分",
        "",
        "| 维度 | 权重 | 均分 | 加权得分 | 可视化 |",
        "|------|------|------|---------|--------|",
    ])

    for dim_name, ds in result.dimension_scores.items():
        bar_len = int(ds["average"])
        bar = "█" * bar_len + "░" * (10 - bar_len)
        marker = " ← 最弱" if dim_name == result.weakest_dimension else ""
        lines.append(
            f"| {dim_name} | {ds['weight']}% | {ds['average']}/10 | {ds['weighted']:.1f} | {bar} |{marker}"
        )

    lines.extend(["", "## 详细评分", ""])

    current_dim = None
    for d in result.details:
        if d["dimension"] != current_dim:
            current_dim = d["dimension"]
            lines.append(f"### {current_dim}")
        score = d["score"]
        indicator = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
        lines.append(f"- {indicator} {d['criterion']}: **{score}/10**")

    # 行动建议
    lines.extend(["", "## 下一步行动", ""])

    if result.redline_violations:
        lines.extend([
            "1. **立即停止投入**，记录学习要点",
            "2. 用 `pt decision --add \"Kill: 红线触发\"` 记录决策",
            "3. 用 `pt skip` 跳过后续节点",
            "4. 转向评估下一个机会",
        ])
    elif result.percentage >= 70:
        lines.extend([
            f"最弱维度: **{result.weakest_dimension}** — 优先补强此维度",
            "",
            "1. 识别关键假设，设计最小可行测试 (MVT)",
            "2. 如未做付费测试: 48h内做一个落地页+预付费测试",
            "3. 目标: 30天内获得10个付费用户承诺",
            "4. 用 `pt done ms_screen` 通过初筛门禁",
        ])
    elif result.percentage >= 50:
        lines.extend([
            f"最弱维度: **{result.weakest_dimension}** — 这是决定 Go/Kill 的关键",
            "",
            "1. 设定2周时间盒，专攻最弱维度",
            "2. 做一个最小验证: 落地页 or 反向访谈 or 社区发帖",
            "3. 2周后重新评分，分数不变则 Kill",
        ])
    else:
        lines.extend([
            "1. 除非有独特洞察（如内部信息/独特资源），否则 Kill",
            "2. 用 `pt decision --add \"Kill: 评分 {:.0f}/100\"` 记录".format(result.percentage),
            "3. 记录学习: 这个机会教会了什么？",
        ])

    return "\n".join(lines)


def interactive_scoring():
    """交互式评分"""
    print("=" * 60)
    print("  机会评分系统 v2 — YC/a16z 标准")
    print("=" * 60)

    name = input("\n机会名称: ").strip() or "未命名机会"
    scores = {}

    fw = FRAMEWORK_V2
    for dim in fw["dimensions"]:
        print(f"\n── {dim['name']} (权重 {dim['weight']}%) ──")
        for crit in dim["criteria"]:
            print(f"  {crit['name']}: {crit['description']}")
            while True:
                try:
                    s = input(f"  评分 (1-10): ").strip()
                    s = int(s)
                    if 1 <= s <= 10:
                        scores[crit["id"]] = s
                        break
                except (ValueError, EOFError):
                    pass
                print("  请输入 1-10 的整数")

    result = score_opportunity(name, scores)
    report = format_report(result)
    print("\n" + report)

    save = input("\n保存报告? (y/N): ").strip().lower()
    if save == "y":
        fname = f"scorecard_{name.replace(' ', '_')}.md"
        Path(fname).write_text(report, encoding="utf-8")
        print(f"✅ 已保存: {fname}")


def main():
    parser = argparse.ArgumentParser(description="机会评分系统 v2 (YC/a16z 标准)")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    parser.add_argument("--demo", action="store_true", help="演示模式")
    parser.add_argument("--data", type=str, help="评分数据文件 (YAML/JSON)")
    parser.add_argument("--name", type=str, default="未命名机会", help="机会名称")
    parser.add_argument("--framework", choices=["v1", "v2"], default="v2", help="评分框架版本")
    parser.add_argument("-o", "--output", type=str, help="输出文件")

    args = parser.parse_args()
    fw = FRAMEWORKS.get(args.framework, FRAMEWORK_V2)

    if args.interactive:
        interactive_scoring()
        return

    if args.demo:
        demo_scores = {
            # 市场
            "tam_size": 7, "growth": 8, "timing": 9,
            # 竞争
            "intensity": 6, "barrier": 7, "moat_potential": 5,
            # 能力
            "skill_match": 8, "resource_need": 7, "time_to_market": 6,
            # 经济
            "ltv_cac": 7, "margin": 8, "payback": 6,
            # 验证强度 (v2)
            "pain_evidence": 7, "willingness_to_pay": 4, "mvt_result": 3,
            # AI-Native (v2)
            "system_rethink": 8, "data_loop": 6, "compound_advantage": 7,
        }
        result = score_opportunity("AI 编程助手 — 企业版", demo_scores, fw)
    elif args.data:
        p = Path(args.data)
        content = p.read_text(encoding="utf-8")
        if p.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
        result = score_opportunity(
            data.get("name", args.name),
            data.get("scores", {}),
            data.get("framework", fw),
        )
    else:
        parser.print_help()
        return

    report = format_report(result)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✅ 保存到: {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
