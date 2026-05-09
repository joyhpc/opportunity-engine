#!/usr/bin/env python3
"""24h快速验证器 — "Building IS Validation" 方法论

整合 2025-2026 最佳实践:
- YC MVT (最小可行测试): 验证原子单元，不验证整个产品
- 7层隐形验证法: 落地页→反向访谈→社交信号→预售
- Indie Hacker 速度: 用AI工具2周内出MVP，构建即验证

Usage:
    python3 idea_validator.py --generate "AI编程教育平台"
    python3 idea_validator.py --checklist
    python3 idea_validator.py --track my_validation.yaml
    python3 idea_validator.py --demo
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ── 验证框架 ──────────────────────────────────────────────

VALIDATION_PLAYBOOK = {
    "name": "24h 快速验证 Playbook",
    "phases": [
        {
            "id": "signal",
            "name": "信号确认 (2h)",
            "day": 0,
            "tasks": [
                {
                    "id": "pain_search",
                    "name": "痛点饮水坑搜索",
                    "duration": "1h",
                    "description": "在 Reddit/HN/知乎/G2 搜索目标用户抱怨",
                    "tool": "pain_miner.py --reddit 'subreddit1,subreddit2' --keywords 'frustrated,hate'",
                    "pass_criteria": "找到 ≥ 5 个独立用户主动求解同一问题",
                    "fail_action": "考虑换方向或换目标用户群",
                },
                {
                    "id": "existing_solutions",
                    "name": "现有方案扫描",
                    "duration": "1h",
                    "description": "找到用户目前在用什么替代方案（越差越好=机会越大）",
                    "tool": "competitor_matrix.py --mode quick",
                    "pass_criteria": "现有方案有明显缺陷，用户表达过不满",
                    "fail_action": "如果现有方案已经很好，Kill",
                },
            ],
        },
        {
            "id": "test_page",
            "name": "落地页测试 (4h)",
            "day": 0,
            "tasks": [
                {
                    "id": "value_prop",
                    "name": "一句话价值主张",
                    "duration": "30min",
                    "description": "写出: 我帮[谁]解决[什么痛]，通过[什么方式]，比[现有方案]好在[哪里]",
                    "pass_criteria": "能在一句话内说清楚，不需要解释",
                    "fail_action": "如果说不清楚，机会可能不够聚焦",
                },
                {
                    "id": "landing_page",
                    "name": "Ghost 落地页",
                    "duration": "2h",
                    "description": "用 Carrd/Framer/GrapesJS 做一页，含标题+痛点+方案+CTA(邮箱/预付费)",
                    "tool": "Carrd.co (免费) 或 GrapesJS (开源)",
                    "pass_criteria": "页面上线，CTA 可点击",
                    "fail_action": "N/A — 必须完成",
                },
                {
                    "id": "demo_video",
                    "name": "2分钟演示视频",
                    "duration": "1h",
                    "description": "用 Loom 录一个 '如果这个产品存在，它会这样工作' 的视频",
                    "tool": "Loom (免费) 或手机录屏",
                    "pass_criteria": "视频清晰展示核心价值",
                    "fail_action": "如果录不出来，说明你自己也不清楚产品是什么",
                },
            ],
        },
        {
            "id": "distribution",
            "name": "分发测试 (Day 1-3)",
            "day": 1,
            "tasks": [
                {
                    "id": "community_post",
                    "name": "社区发帖",
                    "duration": "2h",
                    "description": "发到 3-5 个目标社区: r/SideProject, IndieHackers, 相关Discord, Twitter/X, 知乎",
                    "pass_criteria": "至少 1 个帖子获得 > 10 条有意义的回复",
                    "fail_action": "换社区或换角度重新发",
                },
                {
                    "id": "reverse_interview",
                    "name": "反向访谈 ×5",
                    "duration": "每次30min",
                    "description": "找 5 个目标用户，不推销，只问: '你现在怎么处理[这个问题]？最烦的是什么？'",
                    "pass_criteria": "≥ 3/5 人确认痛点真实且愿意听你的方案",
                    "fail_action": "如果 < 3/5 确认，痛点可能是伪需求",
                },
            ],
        },
        {
            "id": "commitment",
            "name": "承诺测试 (Day 3-7)",
            "day": 3,
            "tasks": [
                {
                    "id": "presale",
                    "name": "预售/付费意愿测试",
                    "duration": "持续",
                    "description": "在落地页加入 Stripe/Gumroad 预售按钮，或直接问 '如果今天上线，你会付$X/月吗？'",
                    "tool": "Stripe Payment Links (免费) 或 Gumroad",
                    "pass_criteria": "≥ 3 人预付费，或 ≥ 10 人明确口头承诺",
                    "fail_action": "如果0人付费，产品可能nice-to-have而非must-have",
                },
                {
                    "id": "waitlist_quality",
                    "name": "等待列表质量",
                    "duration": "持续",
                    "description": "分析注册邮箱质量: 公司邮箱 vs 临时邮箱，回复率",
                    "pass_criteria": "注册 > 50 人，或公司邮箱占比 > 30%",
                    "fail_action": "注册少不一定是坏事，关注转化率而非绝对数",
                },
            ],
        },
        {
            "id": "build",
            "name": "构建即验证 (Day 7-14)",
            "day": 7,
            "tasks": [
                {
                    "id": "mvp_build",
                    "name": "AI加速MVP构建",
                    "duration": "7天",
                    "description": "用 Cursor/Claude Code 构建最小可用产品。只做核心功能的原子单元。",
                    "tool": "Cursor + Claude Code + Supabase + Vercel",
                    "pass_criteria": "核心功能可用，可给真实用户试用",
                    "fail_action": "如果7天做不出来，砍功能范围",
                },
                {
                    "id": "first_users",
                    "name": "首批用户试用",
                    "duration": "持续",
                    "description": "邀请等待列表中最积极的 10 人试用",
                    "pass_criteria": "≥ 3 人自发回来使用第二次",
                    "fail_action": "如果没人回来，产品没有 'magic moment'",
                },
            ],
        },
    ],
    "kill_criteria": {
        "day_3": "社区零反馈 + 无人确认痛点 → Kill",
        "day_7": "0 预付费 + 等待列表 < 10 → Kill",
        "day_14": "MVP 无人自发回访 → Pivot 或 Kill",
        "day_30": "< 10 活跃用户 → Kill",
    },
}


def generate_validation_plan(idea: str) -> str:
    """为一个想法生成完整验证计划"""
    plan = VALIDATION_PLAYBOOK
    lines = [
        f"# 24h 快速验证计划",
        f"**想法**: {idea}",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**总周期**: 14 天（可在 Day 3 或 Day 7 提前 Kill）",
        "",
        "---",
        "",
    ]

    start_date = datetime.now()

    for phase in plan["phases"]:
        phase_date = start_date + timedelta(days=phase["day"])
        lines.extend([
            f"## Phase: {phase['name']}",
            f"开始日期: {phase_date.strftime('%Y-%m-%d')}",
            "",
        ])

        for task in phase["tasks"]:
            lines.extend([
                f"### [ ] {task['name']}",
                f"- **时长**: {task['duration']}",
                f"- **做什么**: {task['description']}",
            ])
            if "tool" in task:
                lines.append(f"- **工具**: `{task['tool']}`")
            lines.extend([
                f"- **通过标准**: {task['pass_criteria']}",
                f"- **失败处理**: {task['fail_action']}",
                "",
            ])

    # Kill 红线
    lines.extend([
        "---",
        "## Kill 红线",
        "",
        "| 时间点 | Kill 条件 |",
        "|--------|----------|",
    ])
    for day, condition in plan["kill_criteria"].items():
        lines.append(f"| {day.replace('_', ' ').title()} | {condition} |")

    # Solo Founder 工具栈
    lines.extend([
        "",
        "## Solo Founder 工具栈",
        "",
        "| 功能 | 工具 | 成本 |",
        "|------|------|------|",
        "| 落地页 | Carrd / Framer | 免费/低价 |",
        "| 演示视频 | Loom | 免费 |",
        "| 支付 | Stripe Payment Links | 免手续费到付 |",
        "| Auth + DB | Supabase | 免费层 |",
        "| 部署 | Vercel | 免费层 |",
        "| AI 编码 | Cursor + Claude Code | $20/月 |",
        "| 邮件 | Resend | 免费层 |",
        "| 分析 | PostHog | 免费层(1M事件/月) |",
        "| 痛点挖掘 | pain_miner.py | 免费 |",
        "| 评分 | opportunity_scorer.py | 免费 |",
    ])

    return "\n".join(lines)


def print_checklist():
    """打印通用验证检查清单"""
    lines = [
        "# 快速验证检查清单",
        "",
        "## Day 0: 信号确认",
        "- [ ] 在 Reddit/HN 找到 ≥5 个用户主动求解同一问题",
        "- [ ] 确认现有方案有明显缺陷",
        "- [ ] 写出一句话价值主张",
        "- [ ] 上线 Ghost 落地页 + CTA",
        "- [ ] 录制 2 分钟演示视频",
        "",
        "## Day 1-3: 分发测试",
        "- [ ] 发帖到 3-5 个目标社区",
        "- [ ] 完成 5 次反向访谈",
        "- [ ] ≥3/5 人确认痛点真实",
        "",
        "## Day 3-7: 承诺测试",
        "- [ ] 上线预售/付费按钮",
        "- [ ] ≥3 人预付费 或 ≥10 人口头承诺",
        "- [ ] 等待列表 ≥ 50 人",
        "",
        "## Day 7-14: 构建即验证",
        "- [ ] 用 AI 工具 7 天内构建 MVP",
        "- [ ] 邀请 10 人试用",
        "- [ ] ≥3 人自发回来使用第二次",
        "",
        "## Kill 红线",
        "- Day 3: 社区零反馈 + 无人确认痛点 → Kill",
        "- Day 7: 0 预付费 + 等待列表 < 10 → Kill",
        "- Day 14: MVP 无人自发回访 → Pivot 或 Kill",
        "- Day 30: < 10 活跃用户 → Kill",
        "",
        "## 通过标准",
        "如果 Day 14 时满足以下全部条件，恭喜：",
        "1. ≥ 10 人付费或强承诺",
        "2. ≥ 3 人自发回访（无提醒）",
        "3. 至少 1 人自发推荐给朋友",
        "→ 你有了 Product-Market Fit 的早期信号。进入商业计划阶段。",
    ]
    return "\n".join(lines)


def track_validation(filepath: str) -> str:
    """追踪验证进度"""
    p = Path(filepath)
    if not p.exists():
        # 创建空追踪文件
        tracking = {
            "idea": "待填写",
            "started": datetime.now().strftime("%Y-%m-%d"),
            "status": "in_progress",
            "phases": {
                "signal": {"status": "pending", "notes": ""},
                "test_page": {"status": "pending", "notes": ""},
                "distribution": {"status": "pending", "notes": ""},
                "commitment": {"status": "pending", "notes": ""},
                "build": {"status": "pending", "notes": ""},
            },
            "metrics": {
                "pain_signals_found": 0,
                "interviews_done": 0,
                "interviews_confirmed": 0,
                "waitlist_signups": 0,
                "prepaid_users": 0,
                "return_users": 0,
            },
            "decision": "",
        }
        p.write_text(
            yaml.dump(tracking, allow_unicode=True, default_flow_style=False)
            if yaml else json.dumps(tracking, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return f"✅ 验证追踪文件已创建: {filepath}\n编辑此文件更新进度，然后重新运行 --track 查看状态。"

    content = p.read_text(encoding="utf-8")
    data = yaml.safe_load(content) if yaml else json.loads(content)

    m = data.get("metrics", {})
    lines = [
        f"# 验证进度: {data.get('idea', '未命名')}",
        f"开始日期: {data.get('started', '—')}",
        "",
        "## 关键指标",
        f"| 指标 | 当前 | 目标 | 状态 |",
        f"|------|------|------|------|",
        f"| 痛点信号 | {m.get('pain_signals_found', 0)} | ≥5 | {'✅' if m.get('pain_signals_found', 0) >= 5 else '⬜'} |",
        f"| 访谈完成 | {m.get('interviews_done', 0)} | ≥5 | {'✅' if m.get('interviews_done', 0) >= 5 else '⬜'} |",
        f"| 访谈确认 | {m.get('interviews_confirmed', 0)} | ≥3 | {'✅' if m.get('interviews_confirmed', 0) >= 3 else '⬜'} |",
        f"| 等待列表 | {m.get('waitlist_signups', 0)} | ≥50 | {'✅' if m.get('waitlist_signups', 0) >= 50 else '⬜'} |",
        f"| 预付费 | {m.get('prepaid_users', 0)} | ≥3 | {'✅' if m.get('prepaid_users', 0) >= 3 else '⬜'} |",
        f"| 回访用户 | {m.get('return_users', 0)} | ≥3 | {'✅' if m.get('return_users', 0) >= 3 else '⬜'} |",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="24h快速验证器 — Building IS Validation",
    )
    parser.add_argument("--generate", type=str, metavar="IDEA",
                        help="为想法生成完整验证计划")
    parser.add_argument("--checklist", action="store_true",
                        help="打印通用验证检查清单")
    parser.add_argument("--track", type=str, metavar="FILE",
                        help="追踪验证进度 (YAML/JSON)")
    parser.add_argument("--demo", action="store_true", help="演示模式")
    parser.add_argument("-o", "--output", type=str, help="输出文件")

    args = parser.parse_args()

    if args.demo:
        output = generate_validation_plan("AI 编程教育平台 — 面向中文市场的交互式编程学习")
    elif args.generate:
        output = generate_validation_plan(args.generate)
    elif args.checklist:
        output = print_checklist()
    elif args.track:
        output = track_validation(args.track)
    else:
        parser.print_help()
        return

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"✅ 保存到: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
