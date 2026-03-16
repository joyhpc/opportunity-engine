#!/usr/bin/env python3
"""AI 童话绘本原型 v2 — tool_use + WeasyPrint + Flux API

迭代修复：
1. tool_use 强制结构化输出 → 消除 JSON 解析失败
2. WeasyPrint HTML/CSS 排版 → 中文支持 + 图文混排
3. Flux API 真实插画生成 → 验证角色一致性
4. 插画 prompt 精简 → <77 token 适配 SD/Flux
"""

from __future__ import annotations

import json
import os
import sys
import time
import base64
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

OUTPUT_DIR = Path(__file__).parent / "output_v2"

# ---------------------------------------------------------------------------
# 数据模型（同 v1）
# ---------------------------------------------------------------------------

@dataclass
class ChildProfile:
    name: str
    age: int
    gender: str
    appearance: dict = field(default_factory=dict)
    personality: list[str] = field(default_factory=list)
    family: dict = field(default_factory=dict)
    language: str = "zh"
    outfit: str = ""  # 固定服装描述，确保跨页一致

@dataclass
class StoryConfig:
    theme: str
    pages: int = 12
    style: str = "watercolor"
    mood: str = "warm"

@dataclass
class PageContent:
    page_num: int
    text: str
    illustration_prompt: str
    emotion: str
    image_path: Optional[str] = None

@dataclass
class Storybook:
    child: ChildProfile
    config: StoryConfig
    pages: list[PageContent] = field(default_factory=list)
    character_anchor: str = ""
    generation_time_sec: float = 0
    issues: list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# 年龄约束
# ---------------------------------------------------------------------------

AGE_CONSTRAINTS = {
    (2, 3): {
        "vocab_level": "toddler",
        "max_words_per_page": 15,
        "sentence_length": "3-5 words per sentence",
        "narrative": "repetitive pattern with rhyme",
        "themes": "animals, colors, shapes, family, daily routines",
        "avoid": "complex emotions, conflict, scary elements",
    },
    (4, 5): {
        "vocab_level": "preschool",
        "max_words_per_page": 40,
        "sentence_length": "6-10 words per sentence",
        "narrative": "simple problem → attempt → resolution",
        "themes": "friendship, courage, exploration, emotions, sharing",
        "avoid": "death, divorce, complex moral dilemmas",
    },
    (6, 8): {
        "vocab_level": "early_reader",
        "max_words_per_page": 80,
        "sentence_length": "10-15 words per sentence",
        "narrative": "three-act structure with character growth",
        "themes": "adventure, fairness, identity, learning from mistakes",
        "avoid": "graphic violence, heavy trauma without resolution",
    },
}

def get_age_constraints(age: int) -> dict:
    for (lo, hi), c in AGE_CONSTRAINTS.items():
        if lo <= age <= hi:
            return c
    return AGE_CONSTRAINTS[(4, 5)]


def build_character_anchor(child: ChildProfile) -> str:
    parts = []
    a = child.appearance
    age_desc = f"a {child.age}-year-old"
    if child.gender == "boy":
        age_desc += " boy"
    elif child.gender == "girl":
        age_desc += " girl"
    else:
        age_desc += " child"
    parts.append(age_desc)
    if a.get("skin"):
        parts.append(f"{a['skin']} skin")
    if a.get("hair"):
        parts.append(f"{a['hair']} hair")
    if a.get("eyes"):
        parts.append(f"{a['eyes']} eyes")
    if a.get("glasses"):
        parts.append("round glasses")
    if a.get("special"):
        parts.append(a["special"])
    return ", ".join(parts)


def build_short_anchor(child: ChildProfile) -> str:
    """精简版角色锚定 — 用于插画 prompt（含固定服装）。"""
    a = child.appearance
    parts = []
    if child.gender == "boy":
        parts.append(f"{child.age}yo boy")
    elif child.gender == "girl":
        parts.append(f"{child.age}yo girl")
    else:
        parts.append(f"{child.age}yo child")
    if a.get("skin"):
        parts.append(a["skin"])
    if a.get("hair"):
        parts.append(a["hair"])
    if a.get("glasses"):
        parts.append("glasses")
    if a.get("special"):
        parts.append(a["special"])
    # 固定服装 — 解决跨页服装漂移
    if child.outfit:
        parts.append(child.outfit)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# 故事生成 — tool_use 方式
# ---------------------------------------------------------------------------

STORY_TOOL = {
    "name": "create_storybook",
    "description": "Create a personalized children's picture book with page-by-page text and illustration prompts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page_num": {"type": "integer", "description": "Page number starting from 1"},
                        "text": {"type": "string", "description": "Story text for this page"},
                        "scene": {"type": "string", "description": "Brief scene description: setting, action, key objects (max 50 words)"},
                        "emotion": {"type": "string", "description": "Emotional tone of this page"},
                    },
                    "required": ["page_num", "text", "scene", "emotion"],
                },
            },
        },
        "required": ["pages"],
    },
}

SYSTEM_PROMPT = """You are a master children's picture book author. Create deeply personalized stories.

RULES:
- The child IS the main character — use their name throughout
- Naturally include their personality traits, interests, and family members
- Each page: story text + brief scene description (setting + action + objects)
- Positive arc: child grows or learns something by the end
- NEVER include violence, scary unresolved elements, or inappropriate content
- Use single quotes for dialogue within text
"""


def generate_story_tooluse(child: ChildProfile, config: StoryConfig) -> tuple[list[PageContent], list[str]]:
    """Generate story using Claude tool_use — guaranteed structured output."""
    issues = []

    try:
        import anthropic
    except ImportError:
        issues.append("CRITICAL: anthropic not installed")
        return [], issues

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        issues.append("CRITICAL: ANTHROPIC_API_KEY not set")
        return [], issues

    client = anthropic.Anthropic(api_key=api_key)
    constraints = get_age_constraints(child.age)
    anchor = build_character_anchor(child)
    short_anchor = build_short_anchor(child)

    family_desc = ""
    if child.family:
        parts = []
        for role, members in child.family.items():
            if isinstance(members, list) and members:
                parts.append(f"{role}: {', '.join(members)}")
        family_desc = "; ".join(parts)

    lang_name = {"zh": "Chinese (简体中文)", "en": "English", "zh-en": "bilingual Chinese then English"}[child.language]

    user_prompt = f"""Create a {config.pages}-page children's picture book.

CHILD: {child.name}, age {child.age}. Looks: {anchor}
Personality: {', '.join(child.personality) or 'curious and kind'}
Family: {family_desc or 'not specified'}

THEME: {config.theme} | MOOD: {config.mood}
LANGUAGE for text: {lang_name}

CONSTRAINTS:
- Max {constraints['max_words_per_page']} words per page
- {constraints['sentence_length']}
- Narrative: {constraints['narrative']}
- Good themes: {constraints['themes']}
- Avoid: {constraints['avoid']}

Use the create_storybook tool to output the story."""

    start = time.time()
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[STORY_TOOL],
            tool_choice={"type": "tool", "name": "create_storybook"},
            messages=[{"role": "user", "content": user_prompt}],
        )
        elapsed = time.time() - start
        issues.append(f"INFO: Story generation took {elapsed:.1f}s")

        # Extract tool use result — guaranteed structured!
        tool_block = None
        for block in response.content:
            if block.type == "tool_use":
                tool_block = block
                break

        if not tool_block:
            issues.append("CRITICAL: No tool_use block in response")
            return [], issues

        pages_data = tool_block.input.get("pages", [])

        # Build illustration prompts from scenes
        style_map = {
            "watercolor": "soft watercolor 2D illustration, hand-painted children's picture book art, pastel colors, NOT a photograph, NOT 3D render, NOT realistic",
            "flat_cartoon": "flat 2D vector cartoon illustration, bold bright colors, clean lines, cel-shaded, NOT a photograph, NOT 3D render, NOT realistic",
            "ink_painting": "traditional Chinese ink wash painting 2D illustration, minimalist brushwork, rice paper texture, NOT a photograph, NOT 3D render, NOT realistic",
        }
        style_suffix = style_map.get(config.style, "children's book illustration")

        pages = []
        for p in pages_data:
            # Compose illustration prompt: anchor + scene + style + negative
            scene = p.get("scene", "")
            illus_prompt = (
                f"2D illustrated children's book page, {style_suffix}, "
                f"{short_anchor}, {scene}, "
                f"no text, no words, no letters, no watermark"
            )
            # Truncate if too long
            if len(illus_prompt) > 350:
                illus_prompt = illus_prompt[:347] + "..."

            pages.append(PageContent(
                page_num=p["page_num"],
                text=p["text"],
                illustration_prompt=illus_prompt,
                emotion=p.get("emotion", "neutral"),
            ))

        # ── 质量检查 ──
        if len(pages) != config.pages:
            issues.append(f"ISSUE: Requested {config.pages} pages, got {len(pages)}")

        name_parts = child.name.split("/")
        all_text = " ".join(pg.text for pg in pages)
        for name_part in name_parts:
            count = all_text.count(name_part)
            if count < 3:
                issues.append(f"ISSUE: Name '{name_part}' only appears {count} times")

        emotions = [pg.emotion for pg in pages]
        if len(set(emotions)) < 3:
            issues.append(f"ISSUE: Low emotion variety: {set(emotions)}")

        if elapsed > 30:
            issues.append(f"WARNING: Slow generation ({elapsed:.1f}s)")

        # Token usage
        usage = response.usage
        issues.append(f"INFO: Tokens — input: {usage.input_tokens}, output: {usage.output_tokens}")

        return pages, issues

    except Exception as e:
        elapsed = time.time() - start
        issues.append(f"CRITICAL: API error: {e}")
        issues.append(f"INFO: Failed after {elapsed:.1f}s")
        return [], issues


# ---------------------------------------------------------------------------
# 插画生成 — Flux API (via Replicate or BFL)
# ---------------------------------------------------------------------------

def generate_illustrations(book: Storybook) -> list[str]:
    """Generate illustrations using Google Imagen 4 API."""
    issues = []

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        issues.append("INFO: No GEMINI_API_KEY set. Skipping illustration generation.")
        issues.append("INFO: export GEMINI_API_KEY=AIza...")
        return issues

    try:
        from google import genai
    except ImportError:
        issues.append("CRITICAL: google-genai not installed: pip install google-genai")
        return issues

    client = genai.Client(api_key=api_key)
    img_dir = OUTPUT_DIR / f"{book.child.name}_images"
    img_dir.mkdir(parents=True, exist_ok=True)

    model = "imagen-4.0-fast-generate-001"  # $0.02/image, ~4s

    def _gen_one(page: PageContent) -> tuple[int, Optional[str], str]:
        try:
            r = client.models.generate_images(
                model=model,
                prompt=page.illustration_prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="3:4",  # portrait for picture books
                ),
            )
            if r.generated_images:
                img_bytes = r.generated_images[0].image.image_bytes
                img_path = img_dir / f"page_{page.page_num:02d}.png"
                img_path.write_bytes(img_bytes)
                return page.page_num, str(img_path), f"INFO: P{page.page_num} OK ({len(img_bytes)//1024}KB)"
            return page.page_num, None, f"ISSUE: P{page.page_num} no image returned"
        except Exception as e:
            err = str(e)[:120]
            return page.page_num, None, f"ISSUE: P{page.page_num} failed: {err}"

    # Generate sequentially (Imagen has strict rate limits)
    start = time.time()
    for page in book.pages:
        page_num, img_path, issue = _gen_one(page)
        issues.append(issue)
        if img_path:
            page.image_path = img_path
        time.sleep(0.5)  # Rate limit buffer

    elapsed = time.time() - start
    success = sum(1 for p in book.pages if p.image_path)
    issues.append(f"INFO: Generated {success}/{len(book.pages)} illustrations in {elapsed:.1f}s ({model})")
    if success > 0:
        cost = success * 0.02
        issues.append(f"INFO: Estimated cost: ${cost:.2f}")

    return issues


# ---------------------------------------------------------------------------
# PDF 组装 — WeasyPrint
# ---------------------------------------------------------------------------

def assemble_pdf_weasy(book: Storybook, output_path: Path) -> list[str]:
    """用 WeasyPrint 生成带中文支持的 PDF。"""
    issues = []

    html_parts = [f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
@page {{
    size: 10in 8in;
    margin: 0;
}}
body {{
    font-family: 'Noto Serif CJK SC', 'Noto Sans CJK SC', serif;
    margin: 0;
    padding: 0;
}}
.page {{
    width: 10in;
    height: 8in;
    page-break-after: always;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}
.cover {{
    background: linear-gradient(135deg, #FFE4B5, #FFDAB9);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}}
.cover h1 {{
    font-size: 42pt;
    color: #8B4513;
    margin: 0;
}}
.cover .subtitle {{
    font-size: 18pt;
    color: #A0522D;
    margin-top: 20pt;
}}
.cover .tag {{
    font-size: 11pt;
    color: #CD853F;
    margin-top: 40pt;
}}
.inner {{
    background: #FFFEFA;
}}
.illus-area {{
    height: 58%;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #F8F6F0;
    border-bottom: 1px solid #E8E4D8;
}}
.illus-area img {{
    max-width: 95%;
    max-height: 95%;
    object-fit: contain;
}}
.placeholder {{
    color: #BBB;
    font-size: 11pt;
    text-align: center;
}}
.text-area {{
    height: 35%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 0 60pt;
}}
.text-area p {{
    font-size: 16pt;
    line-height: 2;
    color: #333;
    text-align: center;
    margin: 0;
}}
.page-num {{
    position: absolute;
    bottom: 10pt;
    width: 100%;
    text-align: center;
    font-size: 9pt;
    color: #CCC;
}}
.emotion-tag {{
    position: absolute;
    bottom: 10pt;
    right: 20pt;
    font-size: 8pt;
    color: #DDD;
}}
.endpage {{
    background: linear-gradient(135deg, #FFE4B5, #FFDAB9);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}}
.endpage h2 {{
    font-size: 28pt;
    color: #8B4513;
}}
.endpage p {{
    font-size: 16pt;
    color: #A0522D;
    margin-top: 10pt;
}}
</style>
</head>
<body>
"""]

    # Cover
    html_parts.append(f"""
<div class="page cover">
    <h1>《{book.config.theme}》</h1>
    <div class="subtitle">—— 专属于 {book.child.name} 的故事 ——</div>
    <div class="tag">AI 童话绘本 · 原型版</div>
</div>
""")

    # Inner pages
    for page in book.pages:
        if page.image_path and Path(page.image_path).exists():
            # Embed image as base64
            img_data = Path(page.image_path).read_bytes()
            b64 = base64.b64encode(img_data).decode()
            img_html = f'<img src="data:image/png;base64,{b64}" alt="Page {page.page_num}">'
        else:
            img_html = f'<div class="placeholder">[Illustration — Page {page.page_num}]<br><small>{page.illustration_prompt[:80]}...</small></div>'

        text_escaped = page.text.replace("&", "&amp;").replace("<", "&lt;")

        html_parts.append(f"""
<div class="page inner">
    <div class="illus-area">{img_html}</div>
    <div class="text-area"><p>{text_escaped}</p></div>
    <div class="page-num">— {page.page_num} —</div>
    <div class="emotion-tag">[{page.emotion}]</div>
</div>
""")

    # End page
    html_parts.append(f"""
<div class="page endpage">
    <h2>~ 故事结束 ~</h2>
    <p>{book.child.name}，你是世界上最棒的！</p>
</div>
</body></html>
""")

    html_content = "".join(html_parts)

    # Save HTML for debugging
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html_content, encoding="utf-8")
    issues.append(f"INFO: HTML saved to {html_path}")

    # Generate PDF
    try:
        from weasyprint import HTML
        start = time.time()
        HTML(string=html_content).write_pdf(str(output_path))
        elapsed = time.time() - start
        size_kb = output_path.stat().st_size / 1024
        issues.append(f"INFO: PDF saved to {output_path} ({size_kb:.0f} KB, {elapsed:.1f}s)")
    except Exception as e:
        issues.append(f"CRITICAL: WeasyPrint failed: {e}")

    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_validation():
    print("=" * 60)
    print("AI 童话绘本 v2 — Pipeline 验证")
    print("  tool_use + WeasyPrint + Flux API")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    test_cases = [
        {
            "name": "v2_zh_preschool",
            "child": ChildProfile(
                name="小雨",
                age=4,
                gender="girl",
                appearance={
                    "skin": "warm beige",
                    "hair": "straight black with red bow",
                    "eyes": "big dark brown",
                },
                personality=["shy but curious", "loves butterflies", "afraid of loud noises"],
                family={
                    "parents": ["妈妈", "爸爸"],
                    "pets": ["小白兔棉花糖"],
                },
                language="zh",
            ),
            "config": StoryConfig(theme="勇敢上学记", pages=12, style="watercolor", mood="warm"),
        },
        {
            "name": "v2_en_diverse",
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
            "config": StoryConfig(theme="The Night Sky Adventure", pages=16, style="flat_cartoon", mood="adventurous"),
        },
        {
            "name": "v2_bilingual",
            "child": ChildProfile(
                name="美美",
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
                    "siblings": ["弟弟小杰"],
                },
                language="zh-en",
            ),
            "config": StoryConfig(theme="中秋节的月亮", pages=12, style="ink_painting", mood="gentle"),
        },
    ]

    all_issues = {}

    for tc in test_cases:
        print(f"\n{'─' * 60}")
        print(f"测试: {tc['name']}")
        print(f"  {tc['child'].name}, {tc['child'].age}岁, {tc['config'].theme}")
        print(f"{'─' * 60}")

        total_start = time.time()

        # Step 1: Generate story
        print("\n[1/3] 生成故事 (tool_use)...")
        pages, story_issues = generate_story_tooluse(tc["child"], tc["config"])
        for issue in story_issues:
            print(f"  {issue}")

        if not pages:
            print("  ❌ 故事生成失败，跳过后续步骤")
            all_issues[tc["name"]] = story_issues
            continue

        print(f"  ✓ 生成 {len(pages)} 页")

        book = Storybook(
            child=tc["child"],
            config=tc["config"],
            pages=pages,
            character_anchor=build_character_anchor(tc["child"]),
        )

        # Step 2: Generate illustrations
        print("\n[2/3] 生成插画...")
        illus_issues = generate_illustrations(book)
        for issue in illus_issues:
            print(f"  {issue}")

        # Step 3: Assemble PDF
        print("\n[3/3] 组装 PDF (WeasyPrint)...")
        pdf_path = OUTPUT_DIR / f"{tc['name']}.pdf"
        pdf_issues = assemble_pdf_weasy(book, pdf_path)
        for issue in pdf_issues:
            print(f"  {issue}")

        total_elapsed = time.time() - total_start
        all_issues[tc["name"]] = story_issues + illus_issues + pdf_issues + [
            f"INFO: Total pipeline = {total_elapsed:.1f}s"
        ]
        print(f"\n  ⏱ 总耗时: {total_elapsed:.1f}s")

        # Save metadata
        meta = {
            "child": asdict(tc["child"]),
            "config": asdict(tc["config"]),
            "anchor": book.character_anchor,
            "short_anchor": build_short_anchor(tc["child"]),
            "pages": [asdict(p) for p in pages],
            "issues": all_issues[tc["name"]],
        }
        meta_path = OUTPUT_DIR / f"{tc['name']}_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("验证汇总")
    print("=" * 60)

    critical, warnings, info_items = [], [], []
    for name, issues in all_issues.items():
        for issue in issues:
            tagged = f"[{name}] {issue}"
            if "CRITICAL" in issue:
                critical.append(tagged)
            elif "WARNING" in issue or "ISSUE" in issue:
                warnings.append(tagged)
            else:
                info_items.append(tagged)

    print(f"\nCRITICAL ({len(critical)}):")
    for c in critical:
        print(f"  {c}")
    print(f"\nWARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  {w}")
    print(f"\nINFO ({len(info_items)}):")
    for i in info_items:
        print(f"  {i}")

    return all_issues


if __name__ == "__main__":
    run_validation()
