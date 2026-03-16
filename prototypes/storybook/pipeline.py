#!/usr/bin/env python3
"""AI 童话绘本原型 — 最小可行 Pipeline

验证目标：
1. 故事生成质量（年龄适配、个性化深度、叙事完整性）
2. 插画 prompt 可用性（角色描述锚定、场景可生成性）
3. 端到端速度（3 分钟内完成？）
4. PDF 组装可行性
5. 发现隐性问题
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class ChildProfile:
    name: str
    age: int
    gender: str  # "boy" / "girl" / "non-binary"
    appearance: dict = field(default_factory=dict)
    # e.g. {"skin": "light brown", "hair": "curly black", "eyes": "brown",
    #        "glasses": True, "special": "wheelchair"}
    personality: list[str] = field(default_factory=list)
    # e.g. ["shy", "loves dinosaurs", "afraid of the dark"]
    family: dict = field(default_factory=dict)
    # e.g. {"parents": ["妈妈", "爸爸"], "siblings": ["姐姐小雪"],
    #        "pets": ["金毛犬旺旺"]}
    language: str = "zh"  # "zh", "en", "zh-en"


@dataclass
class StoryConfig:
    theme: str  # e.g. "勇敢上学记", "黑夜冒险", "新弟弟来了"
    pages: int = 12
    style: str = "watercolor"  # "watercolor", "flat_cartoon", "ink_painting"
    mood: str = "warm"  # "warm", "adventurous", "funny", "gentle"


@dataclass
class PageContent:
    page_num: int
    text: str
    illustration_prompt: str
    emotion: str  # 该页情感基调


@dataclass
class Storybook:
    child: ChildProfile
    config: StoryConfig
    pages: list[PageContent] = field(default_factory=list)
    character_anchor: str = ""  # 角色外貌锚定描述（全局复用）
    generation_time_sec: float = 0
    issues: list[str] = field(default_factory=list)  # 验证中发现的问题


# ---------------------------------------------------------------------------
# 年龄约束
# ---------------------------------------------------------------------------

AGE_CONSTRAINTS = {
    # (min_age, max_age): {词汇量, 句长, 页数范围, 叙事结构}
    (2, 3): {
        "vocab_level": "toddler",
        "max_words_per_page": 15,
        "sentence_length": "3-5 words per sentence",
        "narrative": "repetitive pattern with rhyme",
        "themes": "animals, colors, shapes, family, daily routines",
        "avoid": "complex emotions, conflict, scary elements",
        "pages": (8, 12),
    },
    (4, 5): {
        "vocab_level": "preschool",
        "max_words_per_page": 40,
        "sentence_length": "6-10 words per sentence",
        "narrative": "simple problem → attempt → resolution",
        "themes": "friendship, courage, exploration, emotions, sharing",
        "avoid": "death, divorce, complex moral dilemmas",
        "pages": (12, 20),
    },
    (6, 8): {
        "vocab_level": "early_reader",
        "max_words_per_page": 80,
        "sentence_length": "10-15 words per sentence",
        "narrative": "three-act structure with character growth",
        "themes": "adventure, fairness, identity, learning from mistakes",
        "avoid": "graphic violence, heavy trauma without resolution",
        "pages": (20, 32),
    },
}


def get_age_constraints(age: int) -> dict:
    for (lo, hi), constraints in AGE_CONSTRAINTS.items():
        if lo <= age <= hi:
            return constraints
    return AGE_CONSTRAINTS[(4, 5)]  # default


# ---------------------------------------------------------------------------
# 角色锚定描述生成
# ---------------------------------------------------------------------------

def build_character_anchor(child: ChildProfile) -> str:
    """生成角色视觉锚定描述，用于所有插画 prompt。"""
    parts = []
    a = child.appearance

    # 年龄外貌
    age_desc = f"a {child.age}-year-old"
    if child.gender == "boy":
        age_desc += " boy"
    elif child.gender == "girl":
        age_desc += " girl"
    else:
        age_desc += " child"
    parts.append(age_desc)

    # 肤色
    if a.get("skin"):
        parts.append(f"with {a['skin']} skin")

    # 发型
    if a.get("hair"):
        parts.append(f"{a['hair']} hair")

    # 眼睛
    if a.get("eyes"):
        parts.append(f"{a['eyes']} eyes")

    # 特殊特征
    if a.get("glasses"):
        parts.append("wearing round glasses")
    if a.get("special"):
        parts.append(a["special"])

    # 服装默认
    parts.append("wearing a colorful t-shirt and shorts")

    anchor = ", ".join(parts)
    # 加上名字标记
    anchor = f"[CHARACTER: {child.name}] {anchor}"
    return anchor


# ---------------------------------------------------------------------------
# 故事生成（Claude API）
# ---------------------------------------------------------------------------

STORY_SYSTEM_PROMPT = """You are a master children's picture book author.
You create stories that are age-appropriate, emotionally resonant, and
deeply personalized to the specific child.

RULES:
1. The child IS the main character — use their exact name throughout
2. Include their specific traits, interests, and family members naturally
3. Every page must have BOTH text AND a detailed illustration description
4. The illustration description must reference the CHARACTER ANCHOR exactly
5. Stories must have a positive arc — the child grows or learns something
6. NEVER include: violence, scary monsters that aren't resolved, death,
   inappropriate content, stereotypes
7. Cultural sensitivity: respect all backgrounds, avoid assumptions

CRITICAL OUTPUT RULES:
- Output ONLY a valid JSON array, nothing else
- NO markdown, NO code fences, NO commentary before or after the JSON
- Inside JSON strings: use single quotes (') not double quotes (") for dialogue
- Inside JSON strings: NO literal newlines — keep each text/prompt as one line
- Escape any special characters properly for valid JSON
"""


def generate_story(child: ChildProfile, config: StoryConfig) -> tuple[list[PageContent], list[str]]:
    """Generate a personalized story using Claude API.

    Returns (pages, issues_found).
    """
    issues = []

    try:
        import anthropic
    except ImportError:
        issues.append("CRITICAL: anthropic package not installed")
        return [], issues

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        issues.append("CRITICAL: ANTHROPIC_API_KEY not set")
        return _generate_mock_story(child, config), issues

    client = anthropic.Anthropic(api_key=api_key)
    constraints = get_age_constraints(child.age)
    anchor = build_character_anchor(child)

    # 家庭描述
    family_desc = ""
    if child.family:
        parts = []
        if child.family.get("parents"):
            parts.append(f"Parents: {', '.join(child.family['parents'])}")
        if child.family.get("siblings"):
            parts.append(f"Siblings: {', '.join(child.family['siblings'])}")
        if child.family.get("pets"):
            parts.append(f"Pets: {', '.join(child.family['pets'])}")
        family_desc = "; ".join(parts)

    user_prompt = f"""Create a {config.pages}-page children's picture book story.

CHILD PROFILE:
- Name: {child.name}
- Age: {child.age}
- Character anchor (use in EVERY illustration): {anchor}
- Personality: {', '.join(child.personality) if child.personality else 'curious and kind'}
- Family: {family_desc or 'not specified'}
- Language: {"Chinese (简体中文)" if child.language == "zh" else "English" if child.language == "en" else "Bilingual Chinese-English"}

STORY THEME: {config.theme}
MOOD: {config.mood}
ART STYLE: {config.style}

AGE CONSTRAINTS:
- Vocabulary level: {constraints['vocab_level']}
- Max words per page: {constraints['max_words_per_page']}
- Sentence structure: {constraints['sentence_length']}
- Narrative structure: {constraints['narrative']}
- Appropriate themes: {constraints['themes']}
- Avoid: {constraints['avoid']}

OUTPUT FORMAT (JSON array):
[
  {{
    "page_num": 1,
    "text": "Story text for this page in {child.language}",
    "illustration_prompt": "Detailed scene description. MUST start with the character anchor: '{anchor}'. Describe: setting, action, objects, lighting, composition. Style: {config.style}.",
    "emotion": "the emotional tone of this page (e.g., excited, nervous, proud)"
  }},
  ...
]

IMPORTANT:
- Page 1: introduce {child.name} and their world
- Middle pages: build the adventure/challenge
- Last page: warm resolution, {child.name} has grown
- EVERY illustration_prompt MUST begin with the exact character anchor
- Text should be in {child.language}
- Keep text within {constraints['max_words_per_page']} words per page
"""

    start = time.time()
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=STORY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        elapsed = time.time() - start

        # Parse response
        content = response.content[0].text

        # Try to extract JSON from response — handle LLM output quirks
        try:
            pages_data = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON array in the response
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                raw_json = match.group()
                # Fix common LLM JSON issues:
                # 1. Unescaped newlines in strings
                raw_json = re.sub(r'(?<!\\)\n(?=[^"]*"[,\]\}])', '\\n', raw_json)
                # 2. Trailing commas
                raw_json = re.sub(r',\s*([}\]])', r'\1', raw_json)
                try:
                    pages_data = json.loads(raw_json)
                except json.JSONDecodeError:
                    # Last resort: try line-by-line repair
                    issues.append(f"ISSUE: JSON repair needed. Attempting line-by-line parse...")
                    # Save raw for debugging
                    debug_path = Path(__file__).parent / "output" / f"debug_raw_{child.name}.txt"
                    debug_path.parent.mkdir(exist_ok=True)
                    debug_path.write_text(content, encoding="utf-8")
                    issues.append(f"INFO: Raw response saved to {debug_path}")
                    return _generate_mock_story(child, config), issues
            else:
                issues.append(f"ISSUE: No JSON array found in response")
                debug_path = Path(__file__).parent / "output" / f"debug_raw_{child.name}.txt"
                debug_path.parent.mkdir(exist_ok=True)
                debug_path.write_text(content, encoding="utf-8")
                issues.append(f"INFO: Raw response saved to {debug_path}")
                return _generate_mock_story(child, config), issues

        pages = []
        for p in pages_data:
            page = PageContent(
                page_num=p["page_num"],
                text=p["text"],
                illustration_prompt=p["illustration_prompt"],
                emotion=p.get("emotion", "neutral"),
            )
            pages.append(page)

        # ── 验证检查 ──
        # 1. 页数是否正确
        if len(pages) != config.pages:
            issues.append(f"ISSUE: Requested {config.pages} pages, got {len(pages)}")

        # 2. 每页字数检查
        for p in pages:
            word_count = len(p.text.split()) if child.language == "en" else len(p.text)
            if child.language == "en" and word_count > constraints["max_words_per_page"]:
                issues.append(f"ISSUE: Page {p.page_num} has {word_count} words (max {constraints['max_words_per_page']})")
            elif child.language == "zh" and word_count > constraints["max_words_per_page"] * 2:
                issues.append(f"ISSUE: Page {p.page_num} has {word_count} chars (too long for age {child.age})")

        # 3. 角色锚定是否被引用
        for p in pages:
            if child.name not in p.illustration_prompt and anchor not in p.illustration_prompt:
                issues.append(f"ISSUE: Page {p.page_num} illustration prompt missing character anchor")

        # 4. 名字一致性
        name_count = sum(1 for p in pages if child.name in p.text)
        if name_count < 3:
            issues.append(f"ISSUE: Child name '{child.name}' appears only {name_count} times in text")

        # 5. 生成时间
        issues.append(f"INFO: Story generation took {elapsed:.1f}s")
        if elapsed > 30:
            issues.append(f"WARNING: Generation too slow ({elapsed:.1f}s) — target is <15s")

        # 6. 情感弧线检查
        emotions = [p.emotion for p in pages]
        if len(set(emotions)) < 3:
            issues.append(f"ISSUE: Low emotional variety — only {len(set(emotions))} unique emotions: {set(emotions)}")

        # 7. 家庭成员是否出现
        if child.family:
            all_text = " ".join(p.text for p in pages)
            for member_list in child.family.values():
                if isinstance(member_list, list):
                    for member in member_list:
                        if member not in all_text:
                            issues.append(f"INFO: Family member '{member}' not mentioned in story")

        return pages, issues

    except Exception as e:
        issues.append(f"CRITICAL: API call failed: {e}")
        elapsed = time.time() - start
        issues.append(f"INFO: Failed after {elapsed:.1f}s")
        return _generate_mock_story(child, config), issues


def _generate_mock_story(child: ChildProfile, config: StoryConfig) -> list[PageContent]:
    """生成 mock 故事（无 API 时用于测试 pipeline）。"""
    anchor = build_character_anchor(child)
    pages = []
    mock_texts_zh = [
        f"在一个阳光明媚的早晨，{child.name}醒了过来。",
        f"今天是{child.name}第一天上幼儿园！",
        f"妈妈牵着{child.name}的手，走到了幼儿园门口。",
        f"{child.name}有一点点紧张，紧紧地抓着妈妈的手。",
        "一个小朋友走过来说：'你好！我叫小花，我们一起玩吧！'",
        f"{child.name}和小花一起画画、搭积木、唱歌。",
        f"午饭时间到了，{child.name}吃了最爱的西红柿炒蛋。",
        "下午，老师讲了一个关于勇敢小兔子的故事。",
        f"{child.name}想：'我也可以像小兔子一样勇敢！'",
        f"放学了，妈妈来接{child.name}。",
        f"回家的路上，{child.name}说：'妈妈，幼儿园真好玩！'",
        f"晚上，{child.name}抱着小熊，甜甜地睡着了。明天还要去幼儿园呢！",
    ]
    mock_emotions = [
        "peaceful", "excited", "warm", "nervous", "curious",
        "happy", "content", "engaged", "confident", "relieved",
        "proud", "peaceful",
    ]

    for i in range(min(config.pages, len(mock_texts_zh))):
        pages.append(PageContent(
            page_num=i + 1,
            text=mock_texts_zh[i],
            illustration_prompt=f"{anchor}, {config.style} style illustration, page {i+1} scene",
            emotion=mock_emotions[i] if i < len(mock_emotions) else "neutral",
        ))
    return pages


# ---------------------------------------------------------------------------
# PDF 组装
# ---------------------------------------------------------------------------

def assemble_pdf(book: Storybook, output_path: Path) -> list[str]:
    """组装绘本 PDF（纯文本+排版占位，无实际插画）。"""
    issues = []

    try:
        from reportlab.lib.pagesizes import landscape
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        issues.append("CRITICAL: reportlab not installed")
        return issues

    # 尝试注册中文字体
    zh_font = "Helvetica"
    zh_font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for fp in zh_font_paths:
        if Path(fp).exists():
            try:
                pdfmetrics.registerFont(TTFont("ZhFont", fp))
                zh_font = "ZhFont"
                break
            except Exception:
                continue

    if zh_font == "Helvetica" and book.child.language in ("zh", "zh-en"):
        issues.append("WARNING: No Chinese font found — PDF will show garbled text")

    # 页面尺寸: 10x8 inch (横版绘本)
    page_w, page_h = 10 * inch, 8 * inch
    c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))

    # 封面
    c.setFillColor(HexColor("#FFE4B5"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#8B4513"))
    c.setFont(zh_font, 36)
    title = f"《{book.config.theme}》"
    c.drawCentredString(page_w / 2, page_h * 0.6, title)
    c.setFont(zh_font, 18)
    c.drawCentredString(page_w / 2, page_h * 0.45, f"—— 专属于 {book.child.name} 的故事 ——")
    c.setFont(zh_font, 12)
    c.drawCentredString(page_w / 2, page_h * 0.3, "AI 童话绘本 · 原型版")
    c.showPage()

    # 内页
    for page in book.pages:
        # 上半部分：插画占位区
        c.setFillColor(HexColor("#F0F8FF"))
        c.rect(0.5 * inch, page_h * 0.4, page_w - 1 * inch, page_h * 0.55, fill=1, stroke=1)
        c.setFillColor(HexColor("#999999"))
        c.setFont("Helvetica", 10)
        c.drawCentredString(page_w / 2, page_h * 0.7, f"[Illustration Placeholder — Page {page.page_num}]")

        # 插画 prompt 小字（调试用）
        c.setFont("Helvetica", 6)
        prompt_short = page.illustration_prompt[:120] + "..."
        c.drawCentredString(page_w / 2, page_h * 0.62, prompt_short)

        # 下半部分：文本
        c.setFillColor(HexColor("#333333"))
        c.setFont(zh_font, 16)

        # 简单的文本换行
        text = page.text
        max_chars_per_line = 30 if book.child.language in ("zh", "zh-en") else 60
        lines = []
        while text:
            lines.append(text[:max_chars_per_line])
            text = text[max_chars_per_line:]

        y = page_h * 0.3
        for line in lines:
            c.drawCentredString(page_w / 2, y, line)
            y -= 24

        # 页码
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#AAAAAA"))
        c.drawCentredString(page_w / 2, 0.3 * inch, f"— {page.page_num} —")

        # 情感标记（调试用）
        c.setFont("Helvetica", 8)
        c.drawString(page_w - 1.5 * inch, 0.3 * inch, f"[{page.emotion}]")

        c.showPage()

    # 尾页
    c.setFillColor(HexColor("#FFE4B5"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#8B4513"))
    c.setFont(zh_font, 20)
    c.drawCentredString(page_w / 2, page_h * 0.6, "~ 故事结束 ~")
    c.setFont(zh_font, 14)
    c.drawCentredString(page_w / 2, page_h * 0.45, f"{book.child.name}，你是世界上最棒的！")
    c.showPage()

    c.save()
    issues.append(f"INFO: PDF saved to {output_path} ({len(book.pages) + 2} pages)")

    # 文件大小检查
    size_kb = output_path.stat().st_size / 1024
    issues.append(f"INFO: PDF size = {size_kb:.0f} KB")
    if size_kb > 5000:
        issues.append(f"WARNING: PDF too large ({size_kb:.0f}KB) — target <5MB for web delivery")

    return issues


# ---------------------------------------------------------------------------
# Main: 端到端验证
# ---------------------------------------------------------------------------

def run_validation():
    """运行完整验证管线。"""
    print("=" * 60)
    print("AI 童话绘本 — Pipeline 验证")
    print("=" * 60)

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # ── 测试用例 1: 中文，4 岁女孩，上幼儿园 ──
    test_cases = [
        {
            "name": "test_1_zh_preschool",
            "child": ChildProfile(
                name="小雨",
                age=4,
                gender="girl",
                appearance={
                    "skin": "warm beige",
                    "hair": "straight black with a red bow",
                    "eyes": "big dark brown",
                    "glasses": False,
                },
                personality=["shy but curious", "loves butterflies", "afraid of loud noises"],
                family={
                    "parents": ["妈妈", "爸爸"],
                    "siblings": [],
                    "pets": ["小白兔棉花糖"],
                },
                language="zh",
            ),
            "config": StoryConfig(
                theme="勇敢上学记",
                pages=12,
                style="watercolor",
                mood="warm",
            ),
        },
        {
            "name": "test_2_en_diverse",
            "child": ChildProfile(
                name="Aiden",
                age=6,
                gender="boy",
                appearance={
                    "skin": "dark brown",
                    "hair": "short curly black",
                    "eyes": "deep brown",
                    "glasses": True,
                    "special": "uses a wheelchair",
                },
                personality=["brave", "loves space", "always asks questions"],
                family={
                    "parents": ["Mom", "Dad"],
                    "siblings": ["baby sister Luna"],
                    "pets": ["cat named Rocket"],
                },
                language="en",
            ),
            "config": StoryConfig(
                theme="The Night Sky Adventure",
                pages=16,
                style="flat_cartoon",
                mood="adventurous",
            ),
        },
        {
            "name": "test_3_bilingual",
            "child": ChildProfile(
                name="美美/Mei-Mei",
                age=5,
                gender="girl",
                appearance={
                    "skin": "light",
                    "hair": "long black with bangs",
                    "eyes": "dark brown almond-shaped",
                },
                personality=["outgoing", "loves cooking with grandma", "bilingual"],
                family={
                    "parents": ["妈妈", "Daddy"],
                    "siblings": ["弟弟小杰/Jake"],
                    "pets": [],
                },
                language="zh-en",
            ),
            "config": StoryConfig(
                theme="中秋节的月亮 / The Moon Festival",
                pages=12,
                style="ink_painting",
                mood="gentle",
            ),
        },
    ]

    all_issues = {}

    for tc in test_cases:
        print(f"\n{'─' * 60}")
        print(f"测试: {tc['name']}")
        print(f"  孩子: {tc['child'].name}, {tc['child'].age}岁")
        print(f"  主题: {tc['config'].theme}")
        print(f"  画风: {tc['config'].style}")
        print(f"{'─' * 60}")

        total_start = time.time()

        # Step 1: 生成故事
        print("\n[Step 1] 生成故事...")
        pages, story_issues = generate_story(tc["child"], tc["config"])
        print(f"  → 生成 {len(pages)} 页")
        for issue in story_issues:
            print(f"  {issue}")

        # Step 2: 构建绘本对象
        book = Storybook(
            child=tc["child"],
            config=tc["config"],
            pages=pages,
            character_anchor=build_character_anchor(tc["child"]),
            issues=story_issues,
        )

        # Step 3: 组装 PDF
        print("\n[Step 2] 组装 PDF...")
        pdf_path = output_dir / f"{tc['name']}.pdf"
        pdf_issues = assemble_pdf(book, pdf_path)
        for issue in pdf_issues:
            print(f"  {issue}")

        # Step 4: 保存元数据
        meta_path = output_dir / f"{tc['name']}_meta.json"
        meta = {
            "child": asdict(tc["child"]),
            "config": asdict(tc["config"]),
            "character_anchor": book.character_anchor,
            "page_count": len(pages),
            "pages": [asdict(p) for p in pages],
            "issues": story_issues + pdf_issues,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        total_elapsed = time.time() - total_start
        all_issues[tc["name"]] = story_issues + pdf_issues + [
            f"INFO: Total pipeline time = {total_elapsed:.1f}s"
        ]

        print(f"\n  ⏱ 总耗时: {total_elapsed:.1f}s")

    # ── 汇总报告 ──
    print("\n" + "=" * 60)
    print("验证汇总报告")
    print("=" * 60)

    critical = []
    warnings = []
    info = []

    for test_name, issues in all_issues.items():
        for issue in issues:
            if issue.startswith("CRITICAL"):
                critical.append(f"[{test_name}] {issue}")
            elif issue.startswith("WARNING") or issue.startswith("ISSUE"):
                warnings.append(f"[{test_name}] {issue}")
            elif issue.startswith("INFO"):
                info.append(f"[{test_name}] {issue}")

    print(f"\n🔴 CRITICAL ({len(critical)}):")
    for c in critical:
        print(f"  {c}")

    print(f"\n🟡 WARNINGS/ISSUES ({len(warnings)}):")
    for w in warnings:
        print(f"  {w}")

    print(f"\n🔵 INFO ({len(info)}):")
    for i in info:
        print(f"  {i}")

    # 保存完整报告
    report_path = output_dir / "validation_report.json"
    report_path.write_text(json.dumps(all_issues, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整报告: {report_path}")

    return all_issues


if __name__ == "__main__":
    run_validation()
