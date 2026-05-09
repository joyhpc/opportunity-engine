#!/usr/bin/env python3
"""竞品分析矩阵生成器

从 YAML/JSON 数据生成竞品对比矩阵，支持快速模式和深度模式。

Usage:
    python3 competitor_matrix.py --mode quick --data competitors.yaml
    python3 competitor_matrix.py --mode deep --data competitors.yaml --output report.md
    python3 competitor_matrix.py --demo
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ── 数据模型 ──────────────────────────────────────────────
DEMO_DATA = {
    "opportunity": "AI 编程助手",
    "dimensions": ["产品成熟度", "定价", "技术壁垒", "用户体验", "生态集成"],
    "competitors": [
        {
            "name": "GitHub Copilot",
            "type": "直接竞品",
            "scores": {"产品成熟度": 9, "定价": 6, "技术壁垒": 9, "用户体验": 8, "生态集成": 9},
            "pricing": "$10-39/月",
            "strengths": ["VS Code 深度集成", "GitHub 生态", "海量训练数据"],
            "weaknesses": ["隐私争议", "闭源", "企业定价高"],
            "users": "1.3M+",
        },
        {
            "name": "Cursor",
            "type": "直接竞品",
            "scores": {"产品成熟度": 7, "定价": 7, "技术壁垒": 7, "用户体验": 9, "生态集成": 6},
            "pricing": "$20-40/月",
            "strengths": ["优秀的 UX", "快速迭代", "多模型支持"],
            "weaknesses": ["VS Code fork 依赖", "小团队"],
            "users": "~500K",
        },
        {
            "name": "Claude Code",
            "type": "直接竞品",
            "scores": {"产品成熟度": 6, "定价": 5, "技术壁垒": 9, "用户体验": 8, "生态集成": 7},
            "pricing": "按 token 计费",
            "strengths": ["强推理能力", "Agent 模式", "终端原生"],
            "weaknesses": ["API 成本高", "新产品"],
            "users": "快速增长",
        },
    ],
}


def load_data(path: str) -> dict:
    """从 YAML 或 JSON 加载竞品数据"""
    p = Path(path)
    content = p.read_text(encoding="utf-8")

    if p.suffix in (".yaml", ".yml"):
        if yaml is None:
            print("⚠️  PyYAML 未安装: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
        return yaml.safe_load(content)
    else:
        return json.loads(content)


def generate_quick_matrix(data: dict) -> str:
    """快速竞争定位矩阵（简表）"""
    lines = [
        "# 竞品快速对比矩阵",
        f"机会领域: **{data['opportunity']}**",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    dims = data["dimensions"]
    comps = data["competitors"]

    # 表头
    header = "| 维度 | " + " | ".join(c["name"] for c in comps) + " |"
    sep = "|------|" + "|".join("------" for _ in comps) + "|"
    lines.extend([header, sep])

    # 分数行
    for dim in dims:
        row = f"| {dim} |"
        for c in comps:
            score = c["scores"].get(dim, "—")
            bar = "█" * score + "░" * (10 - score) if isinstance(score, int) else "—"
            row += f" {score}/10 |"
        lines.append(row)

    # 总分
    row = "| **总分** |"
    for c in comps:
        total = sum(c["scores"].get(d, 0) for d in dims)
        row += f" **{total}/{len(dims)*10}** |"
    lines.append(row)

    lines.extend(["", "## 定价对比"])
    for c in comps:
        lines.append(f"- **{c['name']}**: {c.get('pricing', '未知')}")

    return "\n".join(lines)


def generate_deep_matrix(data: dict) -> str:
    """深度竞品分析报告"""
    lines = [
        "# 竞品深度分析报告",
        f"机会领域: **{data['opportunity']}**",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"分析竞品数: {len(data['competitors'])}",
        "",
    ]

    # 快速矩阵
    lines.append(generate_quick_matrix(data))
    lines.append("")

    # 详细拆解
    lines.append("---")
    lines.append("## 逐项深度拆解")

    for c in data["competitors"]:
        lines.extend([
            "",
            f"### {c['name']}",
            f"- **类型**: {c.get('type', '—')}",
            f"- **定价**: {c.get('pricing', '—')}",
            f"- **用户量**: {c.get('users', '—')}",
            "",
            "**优势:**",
        ])
        for s in c.get("strengths", []):
            lines.append(f"  - ✅ {s}")
        lines.append("\n**劣势:**")
        for w in c.get("weaknesses", []):
            lines.append(f"  - ❌ {w}")

        # 雷达图数据（文字版）
        dims = data["dimensions"]
        lines.extend(["", "**能力雷达:**"])
        for dim in dims:
            score = c["scores"].get(dim, 0)
            bar = "█" * score + "░" * (10 - score)
            lines.append(f"  {dim:10s} [{bar}] {score}/10")

    # 差异化机会
    lines.extend([
        "",
        "---",
        "## 差异化机会识别",
        "",
    ])

    dims = data["dimensions"]
    comps = data["competitors"]
    for dim in dims:
        scores = [c["scores"].get(dim, 0) for c in comps]
        avg = sum(scores) / len(scores)
        if avg < 7:
            lines.append(f"- 🎯 **{dim}** (竞品均分 {avg:.1f}/10): 有差异化空间")

    # 总结建议
    lines.extend([
        "",
        "## 进入策略建议",
        "基于竞品分析，建议关注:",
        "1. 竞品得分较低的维度 → 差异化切入点",
        "2. 竞品定价偏高的区间 → 价格竞争机会",
        "3. 用户高频抱怨的痛点 → 产品改进方向",
    ])

    return "\n".join(lines)


def generate_positioning_map(data: dict, x_dim: str = None, y_dim: str = None) -> str:
    """2×2 竞争定位图（ASCII 版）"""
    dims = data["dimensions"]
    comps = data["competitors"]

    if not x_dim:
        x_dim = dims[0]
    if not y_dim:
        y_dim = dims[1] if len(dims) > 1 else dims[0]

    lines = [
        f"# 竞争定位图",
        f"X轴: {x_dim}  |  Y轴: {y_dim}",
        "",
        f"  {y_dim} ↑",
        "  10 │",
    ]

    # 简单 ASCII 定位
    grid = {}
    for c in comps:
        x = c["scores"].get(x_dim, 5)
        y = c["scores"].get(y_dim, 5)
        grid[(x, y)] = c["name"][:8]

    for y in range(10, 0, -1):
        row = f"  {y:2d} │"
        for x in range(1, 11):
            if (x, y) in grid:
                row += f" [{grid[(x, y)]}]"
            else:
                row += "  ·"
        lines.append(row)

    lines.append("     └" + "─" * 40 + "→ " + x_dim)
    lines.append("      1   2   3   4   5   6   7   8   9  10")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="竞品分析矩阵生成器")
    parser.add_argument("--mode", choices=["quick", "deep", "position"],
                        default="quick", help="分析模式")
    parser.add_argument("--data", type=str, help="竞品数据文件 (YAML/JSON)")
    parser.add_argument("--demo", action="store_true", help="使用演示数据")
    parser.add_argument("-o", "--output", type=str, help="输出文件路径")
    parser.add_argument("--x-dim", type=str, help="定位图X轴维度")
    parser.add_argument("--y-dim", type=str, help="定位图Y轴维度")

    args = parser.parse_args()

    if args.demo:
        data = DEMO_DATA
    elif args.data:
        data = load_data(args.data)
    else:
        parser.print_help()
        print("\n提示: 使用 --demo 查看示例输出", file=sys.stderr)
        return

    if args.mode == "quick":
        report = generate_quick_matrix(data)
    elif args.mode == "deep":
        report = generate_deep_matrix(data)
    elif args.mode == "position":
        report = generate_positioning_map(data, args.x_dim, args.y_dim)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✅ 保存到: {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
