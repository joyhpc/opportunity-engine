#!/usr/bin/env python3
"""报告生成器 — 汇总各阶段输出，生成完整机会评估报告

从各工具的输出文件中汇总信息，生成结构化 Markdown 报告。

Usage:
    python3 report_generator.py --opportunity "AI编程助手" --stage screen --input-dir ./outputs/
    python3 report_generator.py --demo
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


STAGE_TITLES = {
    "sense": "机会感知报告",
    "screen": "初筛评估报告",
    "analyze": "深度分析报告",
    "validate": "验证结果报告",
    "plan": "商业计划书",
    "launch": "执行启动报告",
    "monitor": "运营监控报告",
    "full": "机会全面评估报告",
}

STAGE_SECTIONS = {
    "sense": [
        ("趋势信号", "trend_scan.md"),
        ("行业信息", "industry_feed.md"),
        ("社交聆听", "social_listening.md"),
        ("技术扫描", "patent_tech_scan.md"),
        ("机会简报", "opportunity_brief.md"),
    ],
    "screen": [
        ("市场规模", "market_sizing.md"),
        ("竞争扫描", "competition_scan.md"),
        ("能力匹配", "capability_match.md"),
        ("经济模型", "rough_economics.md"),
        ("评分卡", "scorecard.md"),
    ],
    "analyze": [
        ("市场深度分析", "market_deep_dive.md"),
        ("竞品拆解", "competitor_analysis.md"),
        ("价值链", "value_chain.md"),
        ("风险评估", "risk_assessment.md"),
        ("财务模型", "financial_model.md"),
    ],
    "validate": [
        ("关键假设", "hypothesis_list.md"),
        ("MVP方案", "mvp_design.md"),
        ("测试数据", "mvp_results.md"),
        ("验证结论", "validation_verdict.md"),
    ],
    "plan": [
        ("商业模式", "business_model.md"),
        ("市场策略", "go_to_market.md"),
        ("资源计划", "resource_plan.md"),
        ("风险缓解", "risk_mitigation.md"),
    ],
}


def generate_report(opportunity: str, stage: str, input_dir: str = None,
                    sections_data: dict = None) -> str:
    """生成阶段报告"""
    title = STAGE_TITLES.get(stage, f"{stage} 报告")
    lines = [
        f"# {title}",
        f"**机会**: {opportunity}",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**阶段**: {stage.upper()}",
        "",
        "---",
        "",
    ]

    sections = STAGE_SECTIONS.get(stage, [])

    for section_title, filename in sections:
        lines.append(f"## {section_title}")
        lines.append("")

        # 尝试从文件读取
        content = None
        if input_dir:
            filepath = Path(input_dir) / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")

        # 或从传入数据读取
        if not content and sections_data:
            content = sections_data.get(filename, None)

        if content:
            lines.append(content)
        else:
            lines.append(f"*待补充 — 请运行对应工具生成 `{filename}`*")

        lines.append("")

    # 决策摘要
    lines.extend([
        "---",
        "",
        "## 决策摘要",
        "",
        "| 项目 | 状态 |",
        "|------|------|",
    ])

    for section_title, filename in sections:
        filepath = Path(input_dir) / filename if input_dir else None
        status = "✅ 已完成" if (filepath and filepath.exists()) else "⬜ 待完成"
        lines.append(f"| {section_title} | {status} |")

    lines.extend([
        "",
        "## 下一步",
        f"使用 `cd ~/project-tracker && python3 pt status` 查看当前进度",
        f"使用 `cd ~/project-tracker && python3 pt done <task_id>` 标记完成",
    ])

    return "\n".join(lines)


def generate_full_report(opportunity: str, input_dir: str) -> str:
    """生成全面评估报告（汇总所有阶段）"""
    lines = [
        f"# {opportunity} — 全面评估报告",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]

    for stage in ["sense", "screen", "analyze", "validate", "plan"]:
        stage_dir = Path(input_dir) / stage if input_dir else None
        if stage_dir and stage_dir.exists():
            lines.append(generate_report(opportunity, stage, str(stage_dir)))
        else:
            lines.extend([
                f"## {STAGE_TITLES.get(stage, stage)}",
                f"*阶段未完成*",
                "",
            ])

    return "\n".join(lines)


def generate_demo_report() -> str:
    """演示报告"""
    return generate_report(
        opportunity="AI 编程教育平台",
        stage="screen",
        sections_data={
            "market_sizing.md": """### TAM/SAM/SOM 估算
| 层级 | 规模 | 方法 |
|------|------|------|
| TAM | $15.2B | 全球在线教育市场 × 编程教育占比 |
| SAM | $2.3B | 亚太区 × 成人编程教育 |
| SOM | $23M | 预期1%市场份额（3年） |

置信度: 中（基于 Statista + HolonIQ 数据）""",

            "competition_scan.md": """### 竞争格局
- **直接竞品**: Codecademy, freeCodeCamp, Scrimba
- **间接竞品**: Udemy, Coursera (编程课程)
- **新进入者**: AI-native 编程教学工具

竞争强度: 中高（红海但有AI差异化空间）""",

            "capability_match.md": """### 能力差距分析
| 能力 | 现状 | 需求 | 差距 |
|------|------|------|------|
| AI/ML | ★★★★ | ★★★★ | 无 |
| 教育设计 | ★★ | ★★★★ | 需补齐 |
| 前端开发 | ★★★ | ★★★ | 匹配 |
| 运营推广 | ★ | ★★★ | 需外部支持 |""",

            "rough_economics.md": """### 粗算经济模型
- ARPU: $19.99/月
- CAC: $35（社交媒体+SEO）
- LTV: $240（12个月平均留存）
- LTV/CAC: 6.9x ✅
- 毛利率: 85% ✅""",

            "scorecard.md": """### 初筛评分
| 维度 | 权重 | 得分 |
|------|------|------|
| 市场吸引力 | 30% | 7.3/10 |
| 竞争态势 | 20% | 5.7/10 |
| 能力匹配 | 20% | 6.0/10 |
| 经济可行性 | 30% | 8.0/10 |

**综合: 69/100 → 🟡 MAYBE — 建议深入验证差异化优势**""",
        }
    )


def main():
    parser = argparse.ArgumentParser(description="机会评估报告生成器")
    parser.add_argument("--opportunity", type=str, help="机会名称")
    parser.add_argument("--stage", choices=list(STAGE_TITLES.keys()), help="报告阶段")
    parser.add_argument("--input-dir", type=str, help="输入文件目录")
    parser.add_argument("--demo", action="store_true", help="生成演示报告")
    parser.add_argument("-o", "--output", type=str, help="输出文件")

    args = parser.parse_args()

    if args.demo:
        report = generate_demo_report()
    elif args.opportunity and args.stage:
        if args.stage == "full":
            report = generate_full_report(args.opportunity, args.input_dir)
        else:
            report = generate_report(args.opportunity, args.stage, args.input_dir)
    else:
        parser.print_help()
        return

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✅ 保存到: {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
