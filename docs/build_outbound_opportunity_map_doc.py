# -*- coding: utf-8 -*-
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).with_name("出海机会地图_初始调研版.docx")
VISUAL_DIR = Path(__file__).with_name("assets") / "outbound_opportunity_map"

BLUE = "173F5F"
BLUE_2 = "20639B"
PALE = "EAF2F8"
GRAY = "F4F6F8"
BORDER = "D7E1EA"
TEXT = "1F2933"
MUTED = "52616B"
WHITE = "FFFFFF"
GREEN = "1F7A4D"
AMBER = "8A5A00"
RED = "8A1F11"

OPPORTUNITY_NAMES = {
    "A1": "广告急救包",
    "A2": "展会资料包",
    "A3": "页面表达优化",
    "A4": "开发信内容包",
    "A5": "采购沟通包",
    "A6": "广告微诊断",
    "B1": "UGC brief",
    "B2": "素材批量测试",
    "B3": "Creator 小战役",
    "B4": "素材复盘看板",
    "B5": "Demo 本地化",
    "B6": "多平台素材包",
    "C1": "官网信任资产",
    "C2": "客户案例",
    "C3": "认证 FAQ",
    "C4": "工厂故事",
    "C5": "低碳叙事",
    "C6": "渠道招商包",
    "D1": "展前邀约",
    "D2": "代理开发序列",
    "D3": "渠道 onboarding",
    "D4": "销售培训材料",
    "D5": "报价模板",
    "D6": "展后跟进",
    "E1": "表达体检工具",
    "E2": "卖点 Hook 库",
    "E3": "AI 本地化流程",
    "E4": "多 SKU 内容工厂",
    "E5": "月度监测",
    "E6": "UGC SOP",
    "F1": "海外 PR",
    "F2": "品牌全案",
    "F3": "长期账号",
    "F4": "表达培训",
    "F5": "广告代投",
    "F6": "创作者网络",
}

OPPORTUNITY_GROUP_NAMES = {
    "A1-A6": "A1-A6 快速付费入口组",
    "B1-B6": "B1-B6 广告与素材组",
    "C1-C6": "C1-C6 信任资产组",
    "D1-D6": "D1-D6 展会与销售支持组",
    "E1-E6": "E1-E6 工具与流程组",
    "F1-F6": "F1-F6 后置观察组",
    "D1-D2": "D1-D2 展会/渠道获客",
    "D2-D3": "D2-D3 渠道开发与培训",
}

CODE_COLUMN_HEADERS = {
    "编号",
    "对应机会",
    "对应机会（编号+名称）",
    "适用机会（编号+名称）",
    "关联编号",
    "关联机会（编号+名称）",
    "起点编号",
    "起点机会",
    "下游机会",
    "下游机会（编号+名称）",
    "可承接机会",
    "方向",
}

FORBIDDEN_DELIVERY_TERMS = [
    "表姐",
    "使用者视角",
    "上一版",
    "本版",
    "新版",
    "直观性",
    "信息入口过重",
    "原数据形态",
    "真实困惑",
    "我让你",
    "给某个人看",
    "过程话术",
]


def east_asia(run, font="Microsoft YaHei"):
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def margins(cell, top=100, start=105, bottom=100, end=105):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for key, value in [("top", top), ("start", start), ("bottom", bottom), ("end", end)]:
        node = tc_mar.find(qn(f"w:{key}"))
        if node is None:
            node = OxmlElement(f"w:{key}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def borders(table, color=BORDER):
    tbl_pr = table._tbl.tblPr
    tbl_borders = tbl_pr.first_child_found_in("w:tblBorders")
    if tbl_borders is None:
        tbl_borders = OxmlElement("w:tblBorders")
        tbl_pr.append(tbl_borders)
    for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        elem = tbl_borders.find(qn(f"w:{edge}"))
        if elem is None:
            elem = OxmlElement(f"w:{edge}")
            tbl_borders.append(elem)
        elem.set(qn("w:val"), "single")
        elem.set(qn("w:sz"), "6")
        elem.set(qn("w:space"), "0")
        elem.set(qn("w:color"), color)


def keep_row(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    cant_split.set(qn("w:val"), "true")
    tr_pr.append(cant_split)


def expand_opportunity_codes(value):
    text = str(value)
    for code, label in sorted(OPPORTUNITY_GROUP_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(code, label)

    def repl(match):
        code = match.group(0)
        label = OPPORTUNITY_NAMES.get(code)
        if not label:
            return code
        following = text[match.end() : match.end() + len(label) + 2].lstrip()
        if following.startswith(label):
            return code
        return f"{code} {label}"

    return re.sub(r"(?<![A-Z0-9])([A-F][1-6])(?![A-Z0-9])", repl, text)


def cell_text(cell, text, bold=False, color=TEXT, size=8.5):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.08
    r = p.add_run(str(text))
    r.bold = bold
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor.from_string(color)
    east_asia(r)


def style_table(table, header_fill=BLUE):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    borders(table)
    for ri, row in enumerate(table.rows):
        keep_row(row)
        for ci, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            margins(cell)
            if ri == 0:
                shade(cell, header_fill)
            elif ci == 0:
                shade(cell, GRAY)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.08
                for r in p.runs:
                    east_asia(r)
                    if r.font.size is None:
                        r.font.size = Pt(8.5)
                    if ri == 0:
                        r.bold = True
                        r.font.color.rgb = RGBColor.from_string(WHITE)
                    else:
                        r.font.color.rgb = RGBColor.from_string(TEXT)


def table(doc, headers, rows, widths=None, font_size=8.5):
    tbl = doc.add_table(rows=1, cols=len(headers))
    for i, h in enumerate(headers):
        cell_text(tbl.rows[0].cells[i], h, bold=True, color=WHITE, size=font_size)
        if widths:
            tbl.rows[0].cells[i].width = widths[i]
    for row in rows:
        cells = tbl.add_row().cells
        for i, val in enumerate(row):
            display_val = expand_opportunity_codes(val) if headers[i] in CODE_COLUMN_HEADERS else val
            cell_text(cells[i], display_val, bold=(i == 0), size=font_size)
            if widths:
                cells[i].width = widths[i]
    style_table(tbl)
    doc.add_paragraph()
    return tbl


def h1(doc, text):
    p = doc.add_heading(text, level=1)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(5)


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)


def para(doc, text, size=9.6, color=TEXT, bold=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor.from_string(color)
    r.bold = bold
    east_asia(r)
    return p


def bullets(doc, items, size=9.2):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(1.2)
        p.paragraph_format.line_spacing = 1.08
        r = p.add_run(item)
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor.from_string(TEXT)
        east_asia(r)


def callout(doc, title, body, fill=PALE, color=BLUE):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders(tbl, fill)
    c = tbl.cell(0, 0)
    shade(c, fill)
    margins(c, 135, 160, 135, 160)
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor.from_string(color)
    east_asia(r)
    p2 = c.add_paragraph()
    p2.paragraph_format.line_spacing = 1.15
    r2 = p2.add_run(body)
    r2.font.size = Pt(9.2)
    r2.font.color.rgb = RGBColor.from_string(TEXT)
    east_asia(r2)
    doc.add_paragraph()


def center_picture(doc, image_path, width=Cm(27.1)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run()
    r.add_picture(str(image_path), width=width)


def action_strip(doc, items, title="本页怎么用"):
    h2(doc, title)
    tbl = doc.add_table(rows=1, cols=len(items))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders(tbl, BORDER)
    for idx, (label, body, accent) in enumerate(items):
        cell = tbl.cell(0, idx)
        shade(cell, "F7FAFC")
        margins(cell, 180, 165, 180, 165)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(label)
        r.bold = True
        r.font.size = Pt(8.4)
        r.font.color.rgb = RGBColor.from_string(accent)
        east_asia(r)
        p2 = cell.add_paragraph()
        p2.paragraph_format.space_after = Pt(0)
        p2.paragraph_format.line_spacing = 1.1
        r2 = p2.add_run(body)
        r2.font.size = Pt(7.8)
        r2.font.color.rgb = RGBColor.from_string(TEXT)
        east_asia(r2)
    doc.add_paragraph()


def collect_doc_text(doc):
    parts = []
    parts.extend(p.text for p in doc.paragraphs)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def audit_delivery_text(doc):
    text = collect_doc_text(doc)
    found = [term for term in FORBIDDEN_DELIVERY_TERMS if term in text]
    if found:
        raise ValueError(f"Delivery text audit failed. Forbidden terms found: {', '.join(found)}")


def page(doc):
    if doc.paragraphs and not doc.paragraphs[-1].text.strip() and "<w:drawing" not in doc.paragraphs[-1]._element.xml:
        p = doc.paragraphs[-1]._element
        p.getparent().remove(p)
    doc.add_page_break()


def hx(color):
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for item in candidates:
        if item and Path(item).exists():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


def wrap_lines(draw, text, fnt, max_width):
    lines = []
    current = ""
    for ch in str(text):
        candidate = current + ch
        if ch == "\n":
            lines.append(current)
            current = ""
        elif draw.textlength(candidate, font=fnt) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = ch.strip()
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw, xy, text, fnt, fill, max_width, line_gap=8, anchor=None):
    x, y = xy
    lines = wrap_lines(draw, text, fnt, max_width)
    for line in lines:
        if anchor == "mm":
            draw.text((x, y), line, font=fnt, fill=fill, anchor="mm")
        else:
            draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def rounded(draw, box, fill, outline=None, width=2, radius=22):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, start, end, fill, width=5):
    draw.line([start, end], fill=fill, width=width)
    sx, sy = start
    ex, ey = end
    if abs(ex - sx) >= abs(ey - sy):
        direction = 1 if ex >= sx else -1
        pts = [(ex, ey), (ex - direction * 20, ey - 12), (ex - direction * 20, ey + 12)]
    else:
        direction = 1 if ey >= sy else -1
        pts = [(ex, ey), (ex - 12, ey - direction * 20), (ex + 12, ey - direction * 20)]
    draw.polygon(pts, fill=fill)


def draw_badge(draw, xy, label, fill, text_fill=WHITE, size=26):
    x, y = xy
    fnt = font(size, bold=True)
    pad_x, pad_y = 18, 8
    bbox = draw.textbbox((0, 0), label, font=fnt)
    w, h = bbox[2] - bbox[0] + pad_x * 2, bbox[3] - bbox[1] + pad_y * 2
    rounded(draw, (x, y, x + w, y + h), hx(fill), radius=16)
    draw.text((x + pad_x, y + pad_y - 2), label, font=fnt, fill=hx(text_fill))
    return x + w


def draw_card(draw, box, title, body, accent=BLUE, fill="FFFFFF", title_size=30, body_size=24):
    x1, y1, x2, y2 = box
    rounded(draw, box, hx(fill), outline=hx(BORDER), width=3, radius=24)
    draw.rectangle((x1, y1, x1 + 12, y2), fill=hx(accent))
    draw_wrapped(draw, (x1 + 30, y1 + 24), title, font(title_size, bold=True), hx(accent), x2 - x1 - 54, 7)
    draw_wrapped(draw, (x1 + 30, y1 + 72), body, font(body_size), hx(TEXT), x2 - x1 - 54, 8)


def save_visual_overview(path):
    img = Image.new("RGB", (2200, 1220), hx("FFFFFF"))
    draw = ImageDraw.Draw(img)
    draw.text((70, 58), "一页看懂：出海机会不是内容清单，而是销售表达资产的流动", font=font(46, True), fill=hx(BLUE))
    draw.text((72, 118), "先回答三个筛选问题：预算在哪里？从哪个交付物切入？付款验证怎么发生？", font=font(28), fill=hx(MUTED))

    draw.text((90, 205), "外部预算与需求证据", font=font(30, True), fill=hx(BLUE))
    left_cards = [
        ("外贸客户池", "2025 中国货物贸易 45.47 万亿元；民营企业占 57.3%"),
        ("跨境电商", "2025 中国跨境电商进出口 2.75 万亿元"),
        ("广告预算", "IAB/PwC：2025 美国互联网广告 2946 亿美元"),
        ("Creator/视频", "Creator 预算 370 亿美元；视频广告继续高增长"),
    ]
    y = 265
    for title, body in left_cards:
        draw_card(draw, (80, y, 585, y + 112), title, body, accent=BLUE_2, title_size=26, body_size=22)
        arrow(draw, (585, y + 56), (840, 560), hx(BORDER), width=5)
        y += 135

    center = (820, 420, 1380, 715)
    rounded(draw, center, hx(BLUE), radius=34)
    draw.text((1100, 482), "销售表达资产", font=font(48, True), fill=hx(WHITE), anchor="mm")
    draw_wrapped(
        draw,
        (875, 540),
        "把产品功能、使用场景、信任证据和 CTA 重组为海外买家看得懂、信得过、能行动的材料。",
        font(29),
        hx(WHITE),
        460,
        10,
    )
    draw_badge(draw, (955, 655), "表达核心能力", GREEN, size=24)

    draw.text((1525, 205), "连接到 4 类可收费机会", font=font(30, True), fill=hx(BLUE))
    right_cards = [
        ("获流量", "A1 广告急救包\nB2 短视频测试\nB6 平台素材包", GREEN),
        ("建信任", "C1 官网信任资产\nC2 客户案例\nC6 招商包", BLUE_2),
        ("促成交", "A3 页面优化\nA5 采购沟通\nD5 报价模板", AMBER),
        ("扩渠道/复购", "D1 展会邀约\nD6 展后跟进\nE5 月度监测", RED),
    ]
    positions = [(1510, 270), (1810, 270), (1510, 560), (1810, 560)]
    for (title, body, accent), (x, y) in zip(right_cards, positions):
        draw_card(draw, (x, y, x + 280, y + 210), title, body, accent=accent, title_size=27, body_size=22)
        arrow(draw, (1380, 565), (x, y + 105), hx(BORDER), width=5)

    rounded(draw, (300, 960, 1900, 1095), hx(PALE), outline=hx(PALE), radius=28)
    draw.text((340, 990), "第一轮入口", font=font(30, True), fill=hx(BLUE))
    x = 520
    for item, color in [("A1 广告急救包", GREEN), ("A2 展会资料包", GREEN), ("A3 页面表达优化", BLUE_2), ("A6 微诊断", AMBER)]:
        x = draw_badge(draw, (x, 985), item, color, size=25) + 22
    draw.text((340, 1050), "验证标准：定金 / 合同 / 明确采购流程，而不是兴趣、播放量或夸奖。", font=font(25), fill=hx(TEXT))
    img.save(path)


def save_priority_matrix(path):
    img = Image.new("RGB", (2200, 1280), hx("FFFFFF"))
    draw = ImageDraw.Draw(img)
    draw.text((70, 58), "优先级矩阵：先做右上角，不急着穷尽所有方向", font=font(46, True), fill=hx(BLUE))
    draw.text((72, 118), "横轴是 7-14 天内逼近付款的速度，纵轴是个人适配和收益潜力。", font=font(28), fill=hx(MUTED))

    left, top, right, bottom = 220, 220, 1940, 1080
    draw.rectangle((left, top, right, bottom), outline=hx(BORDER), width=4)
    mid_x = (left + right) // 2
    mid_y = (top + bottom) // 2
    draw.rectangle((mid_x, top, right, mid_y), fill=hx("E8F5EE"))
    draw.rectangle((left, top, mid_x, mid_y), fill=hx("FFF6E0"))
    draw.rectangle((mid_x, mid_y, right, bottom), fill=hx("EAF2F8"))
    draw.rectangle((left, mid_y, mid_x, bottom), fill=hx("F7F8FA"))
    draw.line((mid_x, top, mid_x, bottom), fill=hx(BORDER), width=3)
    draw.line((left, mid_y, right, mid_y), fill=hx(BORDER), width=3)
    draw.text((mid_x + 40, top + 28), "先做区", font=font(30, True), fill=hx(GREEN))
    draw.text((left + 30, top + 28), "后置高客单：先等证据", font=font(28, True), fill=hx(AMBER))
    draw.text((mid_x + 30, mid_y + 25), "入口型：可获客但要控边界", font=font(27, True), fill=hx(BLUE))
    draw.text((left + 30, mid_y + 25), "暂缓：慢、重、责任大", font=font(27, True), fill=hx(MUTED))
    draw.line((left, bottom, right + 55, bottom), fill=hx(TEXT), width=4)
    arrow(draw, (right, bottom), (right + 70, bottom), hx(TEXT), width=4)
    draw.line((left, bottom, left, top - 55), fill=hx(TEXT), width=4)
    arrow(draw, (left, top), (left, top - 75), hx(TEXT), width=4)
    draw.text((right - 330, bottom + 38), "验证速度 / 付款速度", font=font(28, True), fill=hx(TEXT))
    draw.text((28, top - 70), "能力适配 + 收益", font=font(28, True), fill=hx(TEXT))

    points = [
        ("A1", "广告急救包", 4.68, 4.63, GREEN),
        ("A2", "展会资料包", 4.58, 4.35, GREEN),
        ("A3", "页面表达优化", 4.10, 4.05, BLUE_2),
        ("A6", "微诊断", 4.30, 3.55, AMBER),
        ("B2", "短视频测试", 3.90, 4.30, GREEN),
        ("C1", "官网信任资产", 3.20, 4.05, BLUE_2),
        ("C2", "客户案例", 3.00, 3.85, BLUE_2),
        ("B1/B3", "UGC 小单", 3.05, 4.20, AMBER),
        ("F1", "海外 PR", 1.95, 3.70, RED),
        ("F2", "品牌全案", 1.55, 3.50, RED),
        ("F5", "广告代投", 1.50, 2.55, RED),
        ("F3", "长期账号", 1.20, 2.20, MUTED),
    ]
    label_offsets = {
        "A1": (38, 2),
        "A2": (38, -10),
        "A3": (36, 0),
        "A6": (34, -6),
        "B1/B3": (-18, -58),
        "B2": (34, -22),
        "C1": (34, 10),
        "C2": (-5, 24),
        "F1": (34, -26),
        "F2": (34, -24),
        "F5": (34, -22),
        "F3": (34, -20),
    }
    for code, name, sx, sy, color in points:
        x = left + int((sx - 1) / 4 * (right - left))
        y = bottom - int((sy - 1) / 4 * (bottom - top))
        draw.ellipse((x - 22, y - 22, x + 22, y + 22), fill=hx(color), outline=hx(WHITE), width=4)
        ox, oy = label_offsets.get(code, (30, -30))
        draw.text((x + ox, y + oy), code, font=font(26, True), fill=hx(color))
        draw.text((x + ox, y + oy + 32), name, font=font(22), fill=hx(TEXT))

    draw_wrapped(
        draw,
        (220, 1145),
        "读法：右上角不是“最终战略”，而是第一轮付费验证入口。左上角可能客单更高，但要等案例、资源和信任资产成熟后再进入。",
        font(28),
        hx(TEXT),
        1650,
    )
    img.save(path)


def save_pathway_funnel(path):
    img = Image.new("RGB", (2200, 1280), hx("FFFFFF"))
    draw = ImageDraw.Draw(img)
    draw.text((70, 58), "路径图：从一个触发点进入，再沿相邻机会升级", font=font(46, True), fill=hx(BLUE))
    draw.text((72, 118), "把 36 个节点压成三条路径，先确定下一步动作，再展开细表。", font=font(28), fill=hx(MUTED))

    lanes = [
        ("广告/页面线", [("A6", "微诊断"), ("A1", "广告急救包"), ("A3", "页面优化"), ("B4/E5", "复盘/监测")], GREEN),
        ("展会/销售线", [("A2/D1", "展前邀约"), ("D6", "展后跟进"), ("C2", "客户案例"), ("C1/C6", "官网/招商")], BLUE_2),
        ("UGC/素材线", [("B1", "Brief"), ("B2", "素材测试"), ("B3", "小战役"), ("E6", "SOP 系统")], AMBER),
    ]
    y = 230
    for lane, steps, color in lanes:
        draw.text((95, y + 42), lane, font=font(31, True), fill=hx(color))
        x = 390
        for i, (code, label) in enumerate(steps):
            draw_card(draw, (x, y, x + 285, y + 118), code, label, accent=color, title_size=28, body_size=24)
            if i < len(steps) - 1:
                arrow(draw, (x + 285, y + 59), (x + 355, y + 59), hx(color), width=5)
            x += 360
        y += 175

    draw.text((95, 760), "7 天验证漏斗", font=font(34, True), fill=hx(BLUE))
    funnel = [
        ("50 家名单", "只找已有海外动作的客户", 1250, BLUE_2),
        ("15 家高分", "广告/展会/页面/询盘证据明确", 980, BLUE),
        ("3 份报价", "3000 / 6800 两档，不给完整免费方案", 720, AMBER),
        ("1 个付款信号", "定金 / 合同 / 采购流程", 650, GREEN),
    ]
    cx, fy = 680, 825
    for i, (title, body, w, color) in enumerate(funnel):
        x1 = cx - w // 2
        x2 = cx + w // 2
        h = 68
        rounded(draw, (x1, fy, x2, fy + h), hx(color), radius=24)
        draw.text((x1 + 32, fy + 14), title, font=font(28, True), fill=hx(WHITE))
        draw.text((x1 + 260, fy + 20), body, font=font(22), fill=hx(WHITE))
        if i < len(funnel) - 1:
            arrow(draw, (cx, fy + h + 8), (cx, fy + h + 35), hx(BORDER), width=4)
        fy += 103

    draw_card(
        draw,
        (1370, 830, 2030, 1120),
        "闭环判断",
        "若第一个付款来自广告，就向页面和复盘加深；若来自展会，就向展后跟进和案例加深。不要同时推进所有节点。",
        accent=BLUE,
        fill=PALE,
        title_size=32,
        body_size=27,
    )
    img.save(path)


def build_visual_assets():
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    overview = VISUAL_DIR / "visual_overview.jpg"
    matrix = VISUAL_DIR / "priority_matrix.jpg"
    pathway = VISUAL_DIR / "pathway_funnel.jpg"
    save_visual_overview(overview)
    save_priority_matrix(matrix)
    save_pathway_funnel(pathway)
    return overview, matrix, pathway


def setup(doc):
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width = Cm(29.7)
    sec.page_height = Cm(21.0)
    sec.top_margin = Cm(1.05)
    sec.bottom_margin = Cm(0.95)
    sec.left_margin = Cm(1.1)
    sec.right_margin = Cm(1.1)
    sec.footer_distance = Cm(0.65)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(9.6)
    normal.font.color.rgb = RGBColor.from_string(TEXT)
    normal.paragraph_format.line_spacing = 1.12
    normal.paragraph_format.space_after = Pt(4)

    for name in ["Title", "Subtitle", "Heading 1", "Heading 2"]:
        s = styles[name]
        s.font.name = "Microsoft YaHei"
        s._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        s.font.color.rgb = RGBColor.from_string(BLUE)
    styles["Title"].font.size = Pt(22)
    styles["Title"].font.bold = True
    styles["Subtitle"].font.size = Pt(10)
    styles["Subtitle"].font.color.rgb = RGBColor.from_string(MUTED)
    styles["Heading 1"].font.size = Pt(14)
    styles["Heading 1"].font.bold = True
    styles["Heading 2"].font.size = Pt(10.5)
    styles["Heading 2"].font.bold = True

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run("出海机会地图 初始调研版")
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor.from_string(MUTED)
    east_asia(r)


READER_FIT_ROWS = [
    ["适合对象", "内容表达型个人、小团队或服务者：擅长策划、拍摄剪辑、视觉判断、访谈、项目交付和客户沟通。", "先卖“表达重组和材料修复”，不从账号运营、广告投放或资源撮合切入。"],
    ["最强能力", "把产品功能、买家场景、信任证据、视觉素材和行动号召重组为海外销售表达。", "广告、展会、页面、官网、开发信、报价材料都需要同一类能力。"],
    ["初期短板", "海外渠道、英文销售深度、平台规则、广告账户、欧美创作者池通常不是第一优势。", "首单不承诺投放结果、媒体发布、达人效果或长期账号增长。"],
    ["第一阶段目标", "用小额、短周期、交付边界清楚的服务包验证谁愿意付钱。", "7-14 天只看定金、合同、报价推进或采购流程，不看兴趣和夸奖。"],
]

RECOMMENDATION_ROWS = [
    ["最应该切入", "海外销售表达诊断 / 急救包 / 资料包", "客户已经在广告、展会、独立站、平台店铺、官网、外贸销售或渠道招商上花钱，但表达造成点击、询盘、信任或成交损耗。"],
    ["首轮机会", "A6 广告微诊断、A1 广告急救包、A2 展会资料包、A3 页面表达优化", "四个入口低资源依赖、边界清楚、材料可见、能在 7-14 天用定金或报价动作验证。"],
    ["不先做", "账号代运营、广告代投、海外 PR、品牌全案、达人资源网络、长期账号", "这些方向依赖渠道、账户、媒体、达人池或长期结果承诺，首轮容易拖成长方案和免费咨询。"],
    ["第一批客户", "已有海外动作、有预算口、有材料、有表达损耗、有短期触发点的企业", "优先找正在花钱但转化不清楚的人，而不是教育完全没有出海动作的人。"],
    ["升级逻辑", "诊断 -> 急救包/资料包 -> 页面/案例/报价模板 -> 月度复盘/SOP", "第一单确认触发场景后，沿相邻材料加深，不同时推进所有机会。"],
]

SERVICE_PACKAGE_ROWS = [
    ["A6 广告微诊断", "3000 元左右", "正在投广告或准备换市场的跨境卖家、外贸企业", "20 个竞品/评论/广告拆解，3 个表达阻塞点，10 条 hook 或素材角度", "低价入口；免费只给 3 个问题，完整诊断收费。"],
    ["A1 广告急救包", "6800 元左右", "已有 Meta/TikTok/Google/Amazon 广告但素材疲软的客户", "卖点重排、hook、脚本、分镜、1 版素材或素材改稿建议", "不承诺 ROI，不接账户代投，只修销售表达和素材结构。"],
    ["A2 展会资料包", "6800-12000 元", "30-45 天内参展、有展位、有产品页但邀约弱的外贸企业", "邀约信、展会短片脚本、产品页改写、展后跟进材料", "时间压力强，适合快速收定金和排交付。"],
    ["A3 页面表达优化", "6800-15000 元", "Amazon/Shopify/独立站或 B2B 官网已有访问但转化弱的客户", "标题、卖点、场景图文、FAQ、CTA、信任说明", "只先修 1 个 SKU 或 1 个落地页，避免整站免费方案。"],
]

FIRST_CLIENT_ROWS = [
    ["跨境卖家", "Amazon、Shopify、独立站、TikTok Shop 已上架；有广告、评论或页面数据。", "广告烧钱但素材和页面转化弱；愿意为 3000/6800 元试单。", "A6 广告微诊断、A1 广告急救包、A3 页面表达优化"],
    ["外贸工厂/设备企业", "已有官网、询盘、认证、展会计划或海外客户案例。", "产品复杂但官网、报价、FAQ、案例讲不清；老板或外贸负责人能决策。", "A2 展会资料包、A3 页面表达优化、C1 官网信任资产"],
    ["参展企业", "已订展位或确定参展日期，手上有名单、产品资料、宣传册或样片。", "展前 30-45 天缺邀约和资料；展后 7-14 天缺分层跟进。", "A2 展会资料包、D1 展前邀约、D6 展后跟进"],
    ["渠道招商客户", "有成熟产品，正在找代理商、经销商或区域伙伴。", "招商页、开发信、报价解释和渠道 FAQ 不统一。", "A3 页面表达优化、C6 渠道招商包、D5 报价模板"],
]

NOT_FIRST_ROWS = [
    ["账号代运营 / 长期账号", "周期长，验证慢，容易把目标变成涨粉和播放量。", "有首批案例、明确月费预算、内容机制稳定后再考虑。"],
    ["广告代投", "责任边界重，需要账户、投放能力、预算控制和数据归因。", "先卖 A6 广告微诊断、A1 广告急救包、B4 素材复盘，再判断是否合作代投方。"],
    ["海外 PR", "依赖媒体资源、新闻窗口、英文表达和品牌证据。", "先沉淀 C1 官网信任资产、C2 客户案例、C4 工厂故事。"],
    ["品牌全案", "客单可能高，但首轮容易变成完整免费方案和长期抽象讨论。", "等有 2-3 个付费案例后，把方法论打包为升级服务。"],
    ["达人撮合 / 创作者网络", "依赖海外创作者池、合同、授权、排期和效果验收。", "先卖 B1 UGC brief 与素材验收，小范围验证后再扩资源网络。"],
    ["多 SKU 内容工厂", "流程重、交付量大，需要稳定客户和模板体系。", "先用 A1/A3/B2 证明付款，再升级 E4 多 SKU 内容工厂。"],
]

VALIDATION_SPRINT_ROWS = [
    ["第 1-2 天", "建立 50 家名单", "只收已有海外动作的客户：广告、参展、平台店铺、官网、开发信、询盘、代理招商至少命中一项。", "50 家可联系名单，每家标注预算口和触发证据。"],
    ["第 3-4 天", "筛出 15 家高分客户", "看四个信号：有预算口、有表达损耗、有材料、有 7-14 天付款窗口。", "15 家高分客户，附 1 个最适合服务包。"],
    ["第 5-7 天", "发出 3 份报价", "每个有效客户给 3000/6800 两档，不继续免费讲完整方案。", "3 份报价或采购沟通，明确本周是否能付定金。"],
    ["第 8-14 天", "拿 1 个付款信号", "定金、合同、采购流程、明确预算负责人四选一；口头兴趣不算。", "1 个付费/采购信号，或者清楚知道哪个触发场景不成立。"],
]

UPGRADE_PATH_ROWS = [
    ["诊断入口", "A6 广告微诊断", "A1 广告急救包、A3 页面表达优化", "客户愿意为问题定位付钱，就继续卖具体修复。"],
    ["广告入口", "A1 广告急救包", "B2 短视频素材测试、B4 素材复盘、E5 月度监测", "素材表现需要持续复盘，可形成月度服务。"],
    ["展会入口", "A2 展会资料包 / D1 展前邀约", "D6 展后跟进、C2 客户案例、C1 官网信任资产", "展前材料带来展后跟进，跟进再沉淀案例和官网资产。"],
    ["页面入口", "A3 页面表达优化", "C3 认证 FAQ、D5 报价模板、E2 卖点 Hook 库", "页面问题会暴露 FAQ、报价解释和卖点体系缺口。"],
    ["渠道入口", "C6 渠道招商包", "D2 代理开发序列、D3 渠道 onboarding、D4 销售培训材料", "招商材料跑通后，渠道需要持续培训和跟进资料。"],
]

CURRENT_2026_ROWS = [
    ["中国外贸窗口仍在", "2026 前 4 个月货物贸易 16.23 万亿元，增长 14.9%；出口 9.33 万亿元，增长 11.3%；4 月单月增长 14.2%。", "客户不是只在复盘 2025，而是在 2026 继续扩市场、参展、换区域和推新品。", "A2 展会资料包、D1 展前邀约、A3 页面表达优化"],
    ["出口结构更复杂", "2026 前 4 个月机电产品出口 5.92 万亿元，增长 17.6%，占出口 63.5%；电动汽车、锂电池、风电机组和工业机器人出口高增。", "复杂产品更需要把参数、场景、认证、交付风险和采购理由讲清楚。", "C1 官网信任资产、C3 认证 FAQ、A5 采购沟通包"],
    ["独立站商家仍在增长", "Shopify Q1 2026 GMV 达 1007.43 亿美元，收入 31.70 亿美元，同比增长 34%；商家解决方案收入 24.20 亿美元。", "独立站商家仍为页面、支付、转化和商家服务付费，适合从页面表达和转化摩擦切入。", "A3 页面表达优化、E5 月度监测、C3 认证 FAQ"],
    ["平台卖家继续买广告", "Amazon Q1 2026 第三方卖家服务 415.78 亿美元，增长 14%；广告服务 172.43 亿美元，增长 24%。", "平台卖家的广告和卖家服务预算仍在，广告素材、Listing 和复盘能直接嵌入预算口。", "A1 广告急救包、B2 素材批量测试、B4 素材复盘看板"],
    ["B2B 买家更自助", "Gartner 2026：67% B2B 买家偏好无销售代表体验；45% 在近期采购中使用 AI。", "官网、FAQ、案例、报价解释要能让买家和 AI 工具自助理解，而不是只靠销售口头解释。", "C1 官网信任资产、A4 开发信内容包、D5 报价模板"],
    ["采购决策更需要证据", "Forrester 2026：B2B 购买由 GenAI 搜索启动，并涉及 13 名内部利益相关者和 9 名外部影响者。", "销售材料要能被多角色转述、验证和降风险；案例、证言、认证和价值解释更重要。", "C2 客户案例、C3 认证 FAQ、D4 销售培训材料"],
]


SCREENING_ROWS = [
    ["海外动作", "广告投放、参展、平台店铺、官网、开发信、代理招商至少命中一项。", "没有任何海外动作、没有渠道预算，还需要从零教育市场。"],
    ["表达损耗", "有点击、询盘、展会名单、店铺访问或社媒曝光，但页面、素材、报价、信任说明转化弱。", "没有流量、没有询盘、没有素材，问题还停留在“想出海”。"],
    ["可用材料", "能提供产品、评论、竞品、广告、询盘、客户案例、认证或报价材料。", "不愿给材料，只要求免费策略、完整方案或结果承诺。"],
    ["付款窗口", "7-14 天内能推进定金、报价、合同、采购流程或明确预算负责人。", "只有兴趣、点赞、涨粉、口头合作，没有付费动作。"],
]


COVER_ACTIONS = [
    ("首轮推荐", "卖海外销售表达诊断、急救包、资料包，先做 A6/A1/A2/A3。", GREEN),
    ("客户选择", "找已有海外动作、有预算口、有材料、有表达损耗的人。", BLUE),
    ("付款验证", "7-14 天只看定金、合同、报价推进或采购流程。", AMBER),
]

UX_ACTIONS = [
    ("预算口", "广告、展会、平台店铺、官网、销售开发、渠道招商至少命中一项。", BLUE),
    ("损耗点", "页面、素材、报价、信任、跟进或 FAQ 中至少有一个明确问题。", GREEN),
    ("交付物", "诊断、急救包、资料包、报价模板、案例或复盘看板能在短周期交付。", BLUE_2),
    ("付款信号", "用 50 名单、15 高分、3 报价、1 付款信号结束第一轮验证。", AMBER),
]

UX_CHECKPOINT_ACTIONS = [
    ("不做泛内容", "没有预算口和交付物的内容建议，不进入首轮。", RED),
    ("不做资源承诺", "达人、媒体、代投、账号增长先不作为成交承诺。", AMBER),
    ("不做完整免费方案", "免费只指出问题，不交付完整策略和文案。", BLUE),
    ("不拖长验证", "7-14 天没有定金、报价或采购推进，就换触发场景。", GREEN),
]

SYSTEM_ACTIONS = [
    ("不要散卖", "所有机会都挂到同一条收入链路：选买家、定卖点、建信任、获流量、促成交。", BLUE),
    ("先找预算口", "广告、展会、店铺、官网、销售开发、渠道招商，比“客户应该做内容”更真实。", GREEN),
    ("先小后大", "先卖微诊断、急救包、资料包，再升级到案例、官网、渠道和复盘系统。", AMBER),
]

OPPORTUNITY_ACTIONS = {
    "A": [
        ("先做", "A1 广告急救包、A2 展会资料包、A3 页面优化、A6 微诊断。", GREEN),
        ("组合", "A6 找问题，A1/A3 改表达，A2 抢时间窗口。", BLUE),
        ("付款信号", "定金、报价、展会前改稿、页面改版排期。", AMBER),
        ("边界", "不承诺投放结果，不接代运营，不免费做完整方案。", RED),
    ],
    "B": [
        ("先做", "B1 brief、B2 素材测试、B6 多平台素材包。", GREEN),
        ("组合", "从广告预算进入，用素材表现复盘沉淀为 B4 看板。", BLUE),
        ("付款信号", "愿意付小额测试费，能提供历史素材和投放反馈。", AMBER),
        ("边界", "不先承诺达人资源和爆款，只卖测试结构。", RED),
    ],
    "C": [
        ("先做", "C1 官网信任资产、C2 客户案例、C6 渠道招商包。", GREEN),
        ("组合", "案例和证言先沉淀，再支撑官网、开发信、代理招商。", BLUE),
        ("付款信号", "愿意安排采访、提供客户证据、明确招商或获客目标。", AMBER),
        ("边界", "没有事实证据时不做空泛品牌故事。", RED),
    ],
    "D": [
        ("先做", "D1 展前邀约、D5 报价模板、D6 展后跟进。", GREEN),
        ("组合", "展会前抢邀约，展会后用跟进和报价材料推进成交。", BLUE),
        ("付款信号", "参展日期明确、名单已有、需要马上发资料。", AMBER),
        ("边界", "不替客户承担销售结果，只承接表达和跟进材料。", RED),
    ],
    "E": [
        ("先做", "E2 卖点库、E5 月度监测、E6 内容 SOP。", GREEN),
        ("组合", "把第一轮交付沉淀成可复用模板，再卖持续优化。", BLUE),
        ("付款信号", "客户复购、要求团队复用、愿意按月维护。", AMBER),
        ("边界", "首轮没有付费证据前，不先做重系统。", RED),
    ],
    "F": [
        ("先观察", "F1 PR、F2 品牌全案、F3 长期账号、F5 广告代投。", AMBER),
        ("升级条件", "有案例、资源池、英文销售深度和明确复购后再进入。", BLUE),
        ("付款信号", "客户愿为策略、渠道或长期维护支付更高预算。", GREEN),
        ("边界", "不把资源型、结果型、长期型承诺放进第一轮。", RED),
    ],
}

RELATION_ACTIONS = [
    ("起点", "从 A6/A1/A2/A3 这些低边界入口进入，而不是先卖完整链路。", GREEN),
    ("加深", "一旦付款来自广告，就加深页面和素材复盘；来自展会，就加深跟进和案例。", BLUE),
    ("产品化", "把一次性交付沉淀为卖点库、案例库、报价模板和 SOP。", AMBER),
]

ABILITY_ACTIONS = [
    ("最强能力", "把产品、场景、卖点和证据重组为销售表达，而不是泛泛做内容。", GREEN),
    ("交付手段", "视频、素材、采访、脚本都是交付形式，商业入口仍然要绑定预算口。", BLUE),
    ("需要补齐", "平台规则、英文销售、广告账户和海外资源池先做知识补丁。", AMBER),
    ("先不承诺", "账号运营、代投、海外 PR、达人网络暂不放进首轮交付。", RED),
]

VALIDATION_ACTIONS = [
    ("名单", "只找已有海外动作的客户，避免教育完全没有预算的人。", BLUE),
    ("报价", "每个有效客户给 3000/6800 两档，不继续免费讲方案。", AMBER),
    ("成交", "以定金、合同、采购流程为成功标准。", GREEN),
    ("复盘", "记录触发场景、拒绝原因和复购潜力，用真实反馈更新地图。", BLUE_2),
]

SOURCE_ACTIONS = [
    ("不是背书清单", "来源只说明预算、渠道和行为趋势存在，不直接证明某个客户会买单。", BLUE),
    ("用于筛选", "每条数据都要转成预算口、触发场景、适用客户和不适用边界。", GREEN),
    ("用于验证", "最后仍以定金、报价、合同或采购流程判断机会是否成立。", AMBER),
]


MARKET_SIGNAL_ROWS = [
    ["2026 外贸窗口", "2026 前 4 个月中国货物贸易 16.23 万亿元，增长 14.9%；出口 9.33 万亿元，增长 11.3%；4 月单月增长 14.2%。", "客户正在扩市场、参展、换区域和推新品，适合用短周期服务包切入。", "参展工厂、新品卖家、贸易商", "A2/D1/D6/A3"],
    ["民营企业", "2025 民营企业进出口 26.04 万亿元，占中国外贸 57.3%；2026 Q1 民企外贸占比仍为 57.3%。", "大量老板型、决策链短的客户存在，适合小额诊断和定金试单。", "民营制造、DTC、跨境卖家", "A1/A2/A3/C1"],
    ["2026 区域多元", "2026 前 4 个月中国与东盟贸易 2.75 万亿元，增长 15.7%；与欧盟贸易 2.01 万亿元，增长 13.2%；与共建“一带一路”经济体贸易 8.28 万亿元，增长 13.5%。", "机会不是只做欧美；多区域意味着素材、本地化、报价和信任说明都要分场景。", "新市场拓展客户", "B6/D1/D5"],
    ["跨境电商", "2025 中国跨境电商进出口 2.75 万亿元，较 2020 年增长 69.7%。", "卖家已有平台、支付、物流和广告预算，服务应嵌入这些预算口。", "Amazon/Shopify/独立站卖家", "A1/A3/B2/B6"],
    ["2026 复杂产品", "2026 前 4 个月机电产品出口 5.92 万亿元，增长 17.6%，占出口 63.5%；电动汽车、锂电池、风电机组、工业机器人出口高增。", "复杂产品更需要把参数、场景、证据和信任讲清楚。", "设备、工具、新能源、材料", "C1/C3/A5"],
    ["Shopify 2026 Q1", "Shopify Q1 2026 GMV 1007.43 亿美元，收入 31.70 亿美元，同比增长 34%；商家解决方案收入 24.20 亿美元。", "独立站商家持续为平台、支付、页面和转化付费。", "Shopify/独立站品牌", "A3/B2/E5"],
    ["Amazon 2026 Q1", "Amazon Q1 2026 第三方卖家服务 415.78 亿美元，增长 14%；广告服务 172.43 亿美元，增长 24%。", "卖家把钱花在平台服务和广告上，可从广告损耗、页面损耗切入。", "Amazon 卖家、供应链品牌", "A1/A3/B4"],
    ["数字广告预算", "IAB/PwC：2025 美国互联网广告收入 2946 亿美元，增长 13.9%；Amazon 2026 Q1 广告服务仍增长 24%。", "内容不是泛传播，而是广告预算里的创意资产。", "投放型卖家、品牌", "A1/B2/B6"],
    ["Creator 预算", "IAB：美国 creator ad spend 2025 年预计 370 亿美元，增长 26%；48% 买家视为 must buy。", "UGC/达人不是虚荣指标，是品牌预算项；但资源和归因复杂。", "DTC、消费品、工具类", "B1/B3/B6"],
    ["社媒注意力", "DataReportal/GWI：2026 年社媒用户身份 57.9 亿；典型用户每周在社媒和视频 feed 花 18 小时 36 分钟。", "社媒仍是认知入口，但要把指标锁到询盘、转化和付款。", "广告型、内容型客户", "B2/B5/E5"],
]

BUYER_BEHAVIOR_ROWS = [
    ["B2B 自助研究", "Gartner 2026：67% B2B 买家偏好无销售代表体验；45% 在近期采购中使用 AI。", "开发信和官网不能泛泛介绍，要给买家自查、自证、可被 AI 和采购团队快速理解的材料。", "销售表达弱但有官网/外联的企业", "C1/A4"],
    ["买方网络扩大", "Forrester 2026：B2B 购买由 GenAI 搜索启动，并涉及 13 名内部利益相关者和 9 名外部影响者。", "案例、证言、FAQ、报价解释要能被多角色转述和验证。", "复杂 B2B、工业品、高客单服务", "C2/C3/D5"],
    ["信息不一致", "Gartner：69% B2B 买家认为销售组织网站与销售提供的信息不一致。", "官网、销售话术、报价材料必须统一，否则信任会掉。", "多销售人员、多渠道获客企业", "C1/D5"],
    ["卖家仍有价值", "Gartner：买家在判断产品是否适合自己公司时，仍偏好寻求销售输入。", "服务机会在“场景适配、异议处理、采购解释”，不是搬运公开信息。", "高客单 B2B、工业品", "A5/D4"],
    ["工业买家线上化", "BigCommerce 2025 工业买家报告：超过 60% 买家在线购买，数字渠道约占三分之一购买。", "B2B 页面、产品信息、报价路径和自助资料会影响成交。", "工业品、设备、零部件", "C1/A3/A5"],
    ["配送影响转化", "DHL 2025：81% 购物者缺少偏好配送选项会弃购；79% 因退货流程不符合预期离开。", "页面表达要把交付、退换、物流、关税风险提前讲清。", "跨境零售、DTC", "A3/C3"],
    ["社交购买", "DHL 2025：70% 全球消费者预计到 2030 年主要通过社媒购物；82% 受病毒趋势和社交热度影响。", "短视频和 UGC 可以成为购买入口，但必须连接到清晰产品页和信任证据。", "消费品、工具、小家电", "B2/B5/A3"],
    ["AI 购物期待", "DHL 2025：7 成购物者希望零售商提供 AI 购物工具；37% 已使用语音购物。", "卖点库、FAQ、场景问答和结构化素材会变得更重要。", "SKU 多、问题多的卖家", "E2/E4"],
    ["结账摩擦", "Baymard 2025：18% 美国网购者因结账流程过长/复杂而弃购；平均结账流程 23.48 个表单元素。", "转化问题未必是广告问题，可能是页面、流程和信任摩擦。", "独立站、DTC", "A3/E5"],
    ["结账优化潜力", "Baymard：仅通过结账设计改进，大型电商平均可提升约 35% 转化率。", "可以卖“页面/结账/FAQ 诊断”，但不能承诺整体 ROI。", "已有流量但转化低客户", "A3/E5"],
    ["支付本地化", "Stripe：动态展示相关本地支付方式可提升转化；不同国家支付偏好差异大。", "跨境页面和报价材料需要解释付款方式、币种、费用和风险。", "跨境独立站、数字服务", "C3/D5"],
]

APPLICABILITY_SIGNAL_ROWS = [
    ["已有预算", "客户已经在广告、展会、平台店铺、官网、开发信、渠道招商中花钱。", "适用：能把服务嵌入现有预算；不适用：完全没有出海动作还要被教育。", "A1/A2/A3/C1/D1"],
    ["已有流量但损耗", "有广告点击、展会名单、询盘、店铺访问或社媒曝光，但转化差。", "适用：做诊断、页面表达、素材测试；不适用：只有想法没有流量。", "A1/A3/B2/E5"],
    ["有明确触发时间", "新品发布、参展前 30-45 天、换市场、平台招商、报价推进。", "适用：短周期资料包；不适用：长期品牌愿景但无时间点。", "A2/D1/D6"],
    ["有可验证证据", "能提供产品、评论、竞品、广告、询盘、客户案例、认证或报价材料。", "适用：服务者能重组表达；不适用：客户不愿给材料，只要免费策略。", "A6/C2/C3"],
    ["客单价支持服务费", "客户一次订单或获客价值足以覆盖 3000/6800 元试单。", "适用：B2B、设备、DTC 高毛利；不适用：低客单且无复购。", "A5/C1/D5"],
    ["决策链短", "老板、市场负责人、外贸负责人能直接确认预算和材料。", "适用：民营企业、小团队；不适用：多部门审批且预算不明。", "A1/A2/A6"],
    ["表达是瓶颈", "产品本身可卖，但卖点、场景、信任、FAQ、报价解释混乱。", "适用：销售表达资产；不适用：产品、价格、供应链本身没有竞争力。", "A3/C1/C2/D5"],
    ["能沉淀复购", "一次交付后能形成卖点库、案例库、模板、月度监测或 SOP。", "适用：可升级；不适用：一次性低价杂活。", "E2/E5/E6"],
    ["资源依赖低", "不需要先有海外达人池、媒体关系、代投账户或长期运营团队。", "适用：轻交付；不适用：PR、代投、长期账号首轮承诺。", "F1/F3/F5"],
    ["付款信号明确", "定金、合同、报价推进、采购流程、明确预算负责人。", "适用：进入下一轮；不适用：点赞、兴趣、涨粉、口头合作。", "全机会筛选"],
]

CORE_EXTRACTION_ROWS = [
    ["核心机会", "销售表达资产，而不是泛内容、泛账号、泛投放。", "市场数据证明预算存在；买家行为证明表达/信任/自助资料影响成交。", "广告、展会、页面、官网、开发信、报价、招商材料"],
    ["最佳客户", "已有海外动作但表达损耗明显的民营企业、跨境卖家、B2B 工厂。", "私营外贸占比高，平台/广告/展会/数字渠道都已有预算口。", "先找“正在花钱但花得不清楚”的客户"],
    ["首轮入口", "A1 广告急救包、A2 展会资料包、A3 页面表达优化、A6 广告微诊断，而不是 F 类资源型或长期型机会。", "首轮必须低资源依赖、交付边界清楚、7-14 天可验证。", "广告急救包、展会资料包、页面优化、微诊断"],
    ["升级路径", "从一次性诊断和资料包，升级到案例、官网、报价模板、素材复盘和 SOP。", "买家行为显示自助研究、信任一致性、转化摩擦都需要持续资产。", "C1/C2/D5/E5/E6"],
    ["不适用边界", "没有预算口、没有材料、没有时间点、没有决策人、要求结果承诺的客户。", "这类客户会把服务拖入教育市场、免费方案或资源承诺。", "先排除，再销售"],
]


DATA_ROWS = [
    ["中国外贸总盘", "2025 年中国货物贸易进出口 45.47 万亿元，同比增长 3.8%；与 190 多个国家和地区贸易增长。", "出海客户池不是小众创业者，而是大量有出口动作的企业；服务切口要绑定现有贸易动作。", "展会、B2B 官网、销售资料、代理招商"],
    ["民营企业主力", "2025 年民营企业进出口 26.04 万亿元，占中国外贸 57.3%。", "大量决策链较短的老板型客户存在，适合用小额诊断和定金试单进入。", "表达体检、展会包、Listing/官网优化"],
    ["跨境电商规模", "海关初步统计：2025 年中国跨境电商进出口 2.75 万亿元，比 2020 年增长 69.7%。", "跨境卖家已经有平台、广告、物流、支付等预算；服务应嵌入这些预算口。", "广告素材、Listing、UGC、素材工厂"],
    ["2026 开局", "2026 年一季度中国货物进出口 11.84 万亿元，同比增长 15%；出口 6.85 万亿元，进口 4.99 万亿元。", "如果客户近期在扩品、参展、换市场，销售表达和资料升级会有时间压力。", "展会资料、开发信、渠道包"],
    ["Shopify 商家生态", "Shopify 2025 年 GMV 3784 亿美元，同比增长 29%；收入 116 亿美元，同比增长 30%。", "独立站商家持续付费给平台、支付和商家服务；CRO、页面表达和素材测试有预算基础。", "落地页、转化诊断、产品页表达"],
    ["Amazon 卖家生态", "Amazon 2025 年第三方卖家服务收入 1722 亿美元，广告服务收入 686 亿美元。", "平台卖家为流量、履约和转化持续付费；可从“广告损耗”和“页面损耗”切入。", "Amazon Listing、广告素材、评论洞察"],
    ["美国数字广告", "IAB/PwC：2025 年美国互联网广告收入 2946 亿美元，同比增长 13.9%；视频同比增长 25.4%。", "内容不是泛传播，而是广告预算中的创意资产；小团队可卖“创意与表达改良”。", "短视频变体、广告脚本、素材测试"],
    ["Creator 预算", "IAB：美国 Creator ad spend 2025 年预计 370 亿美元，较 2024 年增长 26%；48% 买家视为 must buy。", "UGC/KOL 是预算项，但碎片化和匹配难是痛点；前期可做小战役和 brief。", "UGC brief、达人撮合、授权素材"],
    ["数字服务贸易", "UNCTAD：2024 年可数字交付产品贸易增长 10%，占全球服务出口 56%。", "远程交付的咨询、创意、营销、内容生产本身就是出海服务的一部分。", "远程诊断、素材包、模板库"],
    ["社媒注意力", "DataReportal/GWI：2026 报告显示全球社媒用户身份 56.6 亿；社媒和视频 feed 每周约 18 小时 36 分钟。", "社媒仍是买家认知入口，但应把指标锁到询盘、转化和付款，避免只追播放量。", "广告/UGC、客户教育、渠道内容"],
]

PROFILE_ROWS = [
    ["已知优势", "传媒策划、拍摄剪辑、视觉判断、项目交付、客户沟通", "适合把复杂产品变成买家看得懂、信得过、能行动的销售表达。"],
    ["可迁移能力", "脚本、分镜、采访、案例包装、品牌叙事、快速交付", "可以覆盖广告、展会、官网、Listing、开发信、代理招商等多个节点。"],
    ["初期短板", "海外渠道、英文销售深度、平台规则、广告投放账户、欧美创作者池", "不要一开始承诺代运营、投放结果或大型 KOL 网络；先卖边界清楚的交付物。"],
    ["商业入口", "老板已有海外销售动作，但表达、信任、素材或转化受损", "先找已有预算的人，不教育完全没有出海动作的人。"],
    ["验证原则", "7-14 天内拿定金、合同、采购流程或明确预算负责人", "兴趣、夸奖、涨粉、播放量不算验证成功。"],
]

SYSTEM_ROWS = [
    ["1. 选市场/选买家", "行业、国家、平台、竞品、评论、广告库", "市场洞察、竞品拆解、类目判断", "D1/D5"],
    ["2. 定卖点/定场景", "产品功能、使用场景、买家语言、差异化证据", "卖点库、表达词库、hook 库", "A1/A3/E2"],
    ["3. 建立信任", "官网、Listing、案例、认证、工厂故事、FAQ", "信任资产、案例、证言、FAQ", "C1-C6"],
    ["4. 获取流量", "搜索、社媒、达人、广告、展会、LinkedIn", "广告素材、UGC、达人、开发内容", "B1-B6/D1-D2"],
    ["5. 转化成交", "落地页、询盘、邮件、报价前沟通、采购异议", "CRO、销售资料、报价解释、异议处理", "A2/A4/A5/D4-D5"],
    ["6. 渠道扩张", "代理商、分销商、经销商、区域伙伴", "招商包、渠道培训、跟进序列", "C6/D2-D3"],
    ["7. 复购/留存", "客户教育、售后、评价、案例、复购提醒", "教程、FAQ、客户案例、售后内容", "C2/E4"],
]

OPPORTUNITY_ROWS = [
    ["A1", "海外广告素材/销售表达急救包", "正在投 Meta/TikTok/Google 或 Amazon Ads 的卖家", "广告素材/投放优化", "3 个阻塞点+hook+脚本+1 版素材", "强：策划+视频+表达", "低/中高/最快", "IAB 2025 数字广告 2946 亿美元；Amazon 广告 686 亿美元"],
    ["A2", "展会前邀约与资料包", "30-45 天内参展的外贸工厂/品牌", "展会获客预算", "邀约信+短片脚本+展会页+产品页改写", "强：时间压力+项目交付", "低中/中高/最快", "中国 2026 Q1 出口 6.85 万亿元，外贸活动恢复强"],
    ["A3", "Listing/落地页表达优化", "Amazon/Shopify/独立站卖家", "页面转化/内容预算", "标题、卖点、场景图文、FAQ、CTA", "中高：需补平台规则", "中/中高/快", "Shopify 2025 GMV 3784 亿美元；Amazon 卖家服务 1722 亿美元"],
    ["A4", "LinkedIn/邮件开发内容包", "B2B 外贸销售团队/老板", "销售开发预算", "私信、邮件、跟进、产品故事、异议回复", "中高：表达强，需补英文销售", "中/中/快", "民营企业占中国外贸 57.3%，适合老板型成交"],
    ["A5", "报价前采购沟通包", "高客单设备、零部件、材料、工业品企业", "销售支持预算", "价值解释、对比表、采购 FAQ、决策材料", "中高：需要行业访谈", "中/中高/中", "B2B 成交常卡在信任和采购解释，不是内容发布"],
    ["A6", "竞品/评论/广告微诊断", "新品或转市场的跨境卖家", "市场研究/内容预算", "20 个竞品+20 条评论+10 个广告拆解", "强：研究+表达", "低/中/快", "可作为低价入口，但必须限制免费诊断范围"],
    ["B1", "UGC brief 与素材验收", "需要 Creator 素材但不会写 brief 的 DTC 品牌", "Creator/内容预算", "达人 brief、镜头清单、验收标准、授权说明", "中高：策划强，资源弱", "中/中高/快", "IAB creator spend 2025 预计 370 亿美元"],
    ["B2", "短视频素材批量测试包", "高频投放卖家/品牌", "广告测试预算", "5-10 个角度的脚本、分镜和素材变体", "强：视频交付直接", "中/高/快", "IAB 2025 视频广告同比增长 25.4%"],
    ["B3", "Creator/KOC 小战役撮合", "DTC 品牌、消费品、工具类卖家", "达人营销预算", "3-5 位达人名单+邀约+brief+授权素材", "中：需资源池", "中高/高/中", "品牌把 creator 当渠道，但痛点是匹配、标准和归因"],
    ["B4", "广告素材复盘与测试看板", "已有投放但不会复盘的卖家", "投放优化/运营预算", "素材标签、角度复盘、下轮测试计划", "中：需懂指标", "中/中高/中", "广告预算收紧时，客户更关心每一块钱的回报"],
    ["B5", "产品 Demo 本地化", "硬件、工具、家居、消费电子卖家", "产品视频/销售预算", "海外买家场景 demo、脚本、字幕、版本包", "强：拍摄剪辑优势", "中/中高/快", "社媒与视频 feed 每周占用 18h36m，视频仍是认知入口"],
    ["B6", "平台风格广告素材包", "同一产品要上 TikTok/Meta/YouTube/Amazon 的卖家", "多平台素材预算", "同一卖点拆成不同平台版本", "中高：需补平台差异", "中/高/中", "跨平台素材碎片化，客户需要结构化生产"],
    ["C1", "B2B 官网信任资产重构", "外贸工厂、设备、零部件、工业品牌", "官网/销售预算", "首页、产品页、案例、认证、FAQ、CTA", "强：品牌表达+项目交付", "中/中高/中", "B2B 信任资产支撑广告、邮件、展会和代理招商"],
    ["C2", "客户案例/证言系统", "已有海外客户但不会讲案例的企业", "销售支持/品牌预算", "采访、案例页、短视频证言、销售引用片段", "强：采访+故事化", "中/中高/中", "案例是官网、广告、开发信、PR 的共同底层资产"],
    ["C3", "认证/合规/FAQ 表达包", "有认证但买家看不懂的企业", "销售资料/合规预算", "认证解释、风险 FAQ、对比表、采购材料", "中高：需事实核查", "中/中/中", "工业品和消费品都需要把资质转成信任语言"],
    ["C4", "工厂/品牌故事资产", "有制造能力但缺海外信任的工厂", "品牌/销售预算", "工厂故事、流程、质控、团队、交付能力", "强：传媒叙事", "中/中/中", "适合支撑 B2B 官网、展会和代理招商"],
    ["C5", "可持续/低碳/供应链叙事", "新能源、材料、家居、消费品企业", "品牌/渠道预算", "ESG 证据、供应链故事、客户可用话术", "中：需证据严谨", "中高/中高/慢", "新三样和绿色产品出口强，但不能做空泛口号"],
    ["C6", "代理商/渠道商招商包", "想找海外代理的工厂/品牌", "渠道招商预算", "招商页、PPT、邮件、案例、条件说明", "中高：表达+销售", "中/中高/中", "渠道扩张依赖信任资产和销售材料"],
    ["D1", "展会前邀约战役", "已订展位但邀约弱的外贸企业", "展会获客预算", "目标客户名单+邀约邮件+展会短片+跟进序列", "强：时间压力明显", "低中/中高/最快", "展会是已有支出，可用小额增效切入"],
    ["D2", "代理商开发序列", "有成熟产品、缺海外渠道的企业", "渠道开发预算", "代理画像、开发信、跟进话术、招商材料", "中高：需销售访谈", "中/中高/中", "与 C6 组合后客单可提升"],
    ["D3", "渠道商 onboarding 内容", "已有代理但培训弱的企业", "渠道支持预算", "产品培训、FAQ、销售资料、短视频教程", "中高：内容组织强", "中/中/中", "复购和渠道效率方向，不适合作为第一单"],
    ["D4", "海外销售培训材料", "外贸团队、经销商、客服团队", "培训/销售预算", "话术、演示、异议处理、角色演练资料", "中：需方法沉淀", "中/中/中", "有服务案例后再产品化"],
    ["D5", "报价/提案模板系统", "客单价高、报价沟通复杂的 B2B 企业", "销售效率预算", "报价页、价值解释、竞品对比、采购 FAQ", "中高：表达精准", "中/中高/中", "适合从销售真实邮件和丢单原因里挖需求"],
    ["D6", "展后跟进与二次触达包", "展后有名片但转化弱的企业", "销售跟进预算", "分层跟进邮件、资料包、案例、电话问题", "强：交付边界清楚", "低中/中/快", "展后 7-14 天有明确窗口，适合快单"],
    ["E1", "海外销售表达体检工具", "服务方内部或半自动化获客", "工具化/诊断入口", "评分表、问题库、截图标注、报告模板", "强：沉淀方法", "中/中高/中", "先服务后工具，不要一开始做 SaaS"],
    ["E2", "出海卖点/Hook 模板库", "多 SKU 卖家、服务内部交付", "内容效率预算", "场景、痛点、利益、证据、CTA 模板", "强：表达沉淀", "低中/中/快", "可提高交付效率和复购"],
    ["E3", "AI 本地化表达工作流", "需要多语言但预算有限的卖家", "效率工具/内容预算", "翻译、润色、审校、禁用词、版本管理", "中高：需质量控制", "中/中/中", "数字服务贸易增长，但质量和审校是关键"],
    ["E4", "多 SKU 内容工厂", "品类多、上新快的卖家", "内容生产预算", "SKU 卖点库、图文模板、视频脚本批量化", "中高：流程强", "中高/高/慢", "适合第二阶段复购，不适合首单过重"],
    ["E5", "竞品广告/页面监测", "持续投放的卖家或品牌", "市场情报/投放预算", "每周竞品广告、页面、评论变化摘要", "中：需持续机制", "中/中/中", "可从一次诊断升级为月费"],
    ["E6", "Creator/UGC SOP 系统", "未来做撮合或素材生产时使用", "运营体系预算", "达人库字段、brief、授权、验收、复盘 SOP", "中：资源型业务底座", "中高/高/慢", "有 3-5 单 UGC 后再做"],
    ["F1", "海外 PR/媒体故事包", "有融资、出海节点或新品发布的品牌", "PR/品牌预算", "新闻角度、媒体包、创始人故事、采访材料", "中：叙事强，资源弱", "高/高/慢", "客单高但验证慢，暂缓"],
    ["F2", "出海品牌全案", "预算充足、长期建设的品牌", "品牌咨询预算", "定位、视觉、内容、渠道、全年计划", "中：能力可用但过重", "高/高/慢", "容易免费方案化，不做首单"],
    ["F3", "垂直内容频道/行业账号", "长期主义品牌或服务方自营", "品牌/内容预算", "栏目、账号、内容机制、增长复盘", "低中：周期长", "高/不确定/最慢", "容易追播放量，暂不作为商业入口"],
    ["F4", "出海表达培训课/社群", "想学习但未必有采购预算的人", "培训预算", "课程、案例、模板、作业点评", "中：可沉淀", "中/中/慢", "先有服务案例和方法论后再做"],
    ["F5", "广告代投/账号代运营", "想外包增长的卖家", "投放/代运营预算", "账户搭建、投放、素材、复盘", "低中：责任过重", "高/高/慢", "没有投放能力和预算控制前不要承诺"],
    ["F6", "海外本地创作者网络", "需要稳定海外内容生产的品牌", "Creator/渠道预算", "创作者招募、排期、合同、交付", "中：资源建设重", "高/高/慢", "未来可做，但先用手工小单验证"],
]

RELATION_ROWS = [
    ["竞品/评论/广告洞察", "A6/D5", "A1/A3/B2/C1", "提供买家语言、痛点、竞品证据，是后续所有表达资产的原料。", "先卖 3000 元诊断，再升级 6800-20000 元素材或页面包。"],
    ["卖点/Hook 库", "E2", "A1/B2/B6/E4", "把一次性表达沉淀为复用资产，提高后续交付速度。", "每单结束后归档 5-10 条可复用 hook。"],
    ["销售表达急救包", "A1", "B2/B4/E5", "广告素材测试会产生数据，反过来指导下一轮表达。", "用 7 天验证付款，用 30 天验证复购。"],
    ["Listing/落地页优化", "A3", "A1/B2/C1", "页面负责转化，广告负责流量；两者共用卖点和信任证据。", "若客户投广告，优先卖“页面+素材”组合。"],
    ["展会前邀约", "A2/D1", "D6/C1/C2", "展前要获客，展后要转化；资料和跟进序列可以复购。", "按展前、展中、展后拆 3 个产品包。"],
    ["B2B 官网信任资产", "C1", "A4/D2/C6", "官网不是展示柜，是开发信、渠道招商和报价沟通的信任底座。", "先修一个产品页，不做整站重构。"],
    ["客户案例/证言", "C2", "A1/C1/F1", "案例能同时提升广告、官网、邮件和 PR 的可信度。", "有海外客户的企业优先。"],
    ["代理商招商包", "C6/D2", "D3/D4", "招到代理后需要培训和销售内容，形成后续服务。", "先卖招商材料，再卖 onboarding。"],
    ["UGC brief", "B1", "B3/E6", "如果 brief 和验收标准跑通，再进入达人撮合和 SOP。", "先不承诺达人效果，只承诺 brief 和素材验收。"],
    ["短视频素材测试", "B2/B6", "B4/E5", "素材越多越需要复盘和监测，能形成月费。", "从一次性交付转成每月测试节奏。"],
    ["AI 本地化工作流", "E3", "A3/E4", "多语言和多 SKU 会放大人工成本，适合做内部效率工具。", "先服务交付，后工具化。"],
    ["海外 PR/品牌全案", "F1/F2", "C1/C2/C5", "PR 依赖案例、证据和品牌故事，不是第一步。", "等有 2-3 个付费案例后再卖。"],
]

FIT_ROWS = [
    ["表达重组", "把产品功能翻译成海外买家的痛点、场景、证据和行动", "强", "A1/A3/C1/D5/E2"],
    ["视频与素材", "脚本、分镜、拍摄、剪辑、版本化", "强", "A1/B2/B5/B6"],
    ["访谈与故事", "客户访谈、案例、工厂故事、品牌信任", "强", "C2/C4/F1"],
    ["项目交付", "短周期交付、客户沟通、边界管理", "强", "A2/D1/D6"],
    ["海外销售知识", "询盘、报价、采购流程、LinkedIn、英文销售", "中", "A4/A5/D2/D5"],
    ["平台规则", "Amazon/Shopify/TikTok/Meta 素材规范和数据解读", "中低", "A3/B4/B6/F5"],
    ["资源网络", "海外达人、媒体、代理商、创作者池", "低中", "B3/F1/F6"],
]

SCORE_ROWS = [
    ["能力适配", "20%", "现有能力是否能交付首单，不依赖新增大资源", "高：表达/视频/项目；低：代投/媒体资源/海外团队"],
    ["付款速度", "20%", "7-14 天内是否能拿定金、合同或采购流程", "高：展会、广告素材、诊断；低：品牌全案、长期账号"],
    ["预算确定性", "18%", "客户是否已有广告、展会、平台、销售或渠道预算", "优先找已有海外动作和现有支出的人"],
    ["交付风险", "15%", "是否能清楚限定交付物和责任边界", "首单不承诺销量、投放 ROI、媒体发布或达人效果"],
    ["复购潜力", "12%", "一次交付后能否升级为月费或系列包", "素材测试、监测、SKU 工厂、展会周期具备复购"],
    ["证据强度", "10%", "是否有公开数据、客户行为或支付痕迹支撑", "广告收入、平台服务收入、跨境交易数据是底座"],
    ["差异化", "5%", "是否容易被普通翻译、剪辑、代运营替代", "差异化来自“销售表达+证据+场景”，不是单纯内容制作"],
]

SHORTLIST_ROWS = [
    ["1", "A1 海外广告素材/销售表达急救包", "最贴近能力、最快逼近付款、能连接广告和页面", "3000 元体检 / 6800 元急救包；15 家客户微诊断，问定金。"],
    ["2", "A2/D1 展会前邀约与资料包", "时间压力强，客户已有展会支出，老板更容易判断价值", "找 30 天内参展企业，卖展前邀约+资料修复。"],
    ["3", "A3 Listing/落地页表达优化", "客户面广，能与广告素材组合，但需补平台规则", "只修 1 个 SKU 或 1 个落地页，避免整站免费方案。"],
    ["4", "A6 竞品/评论/广告微诊断", "低门槛获客入口，可生成后续素材包", "免费只给 3 个问题，完整诊断收费。"],
    ["5", "B2 短视频素材批量测试包", "收益高、复购好，但需要客户已有投放预算", "从 3-5 个脚本/分镜开始，不先接全量素材工厂。"],
    ["6", "C1 B2B 官网信任资产重构", "适合外贸工厂，客单可高，但首单周期略长", "只改一个产品页和 FAQ，不做整站重构。"],
    ["7", "C2 客户案例/证言系统", "能力匹配强，可支撑后续多方向", "只找已有海外客户的企业，先做 1 个案例。"],
    ["8", "B1/B3 UGC/Creator 小单", "市场大，但资源和授权复杂", "先卖 brief 和验收，不承诺达人效果。"],
]

VALIDATION_ROWS = [
    ["客户前提", "已有海外销售动作：广告、展会、独立站、Amazon/Shopify、外贸询盘、代理开发任一项", "只有想法、没有渠道和预算的人不进入首轮。"],
    ["证据动作", "先看 1 个页面、1 条广告、1 个展会资料、1 封开发信或 1 次报价沟通", "没有具体材料就无法诊断表达损耗。"],
    ["报价动作", "每个有效客户都给 3000/6800 两档，不继续免费讲方案", "必须问本周是否能付 3000-4000 元定金。"],
    ["成功标准", "收到定金、签试单、进入明确采购流程", "兴趣、点赞、说以后合作不算。"],
    ["复盘维度", "客户类型、触发场景、预算口、阻塞点、拒绝原因、是否复购", "用第一批真实反馈更新机会地图。"],
]

SOURCE_ROWS = [
    ["中国外贸 2026 前4个月", "GAC/China Daily：2026 前 4 个月货物贸易 16.23 万亿元，增长 14.9%；出口 9.33 万亿元；机电产品出口增长 17.6%。", "https://www.chinadaily.com.cn/a/202605/09/WS69fec37aa310d6866eb47b1b.html"],
    ["Shopify 2026 Q1", "Shopify：Q1 2026 GMV 1007.43 亿美元，收入 31.70 亿美元，同比增长 34%；Merchant solutions 24.20 亿美元。", "https://www.shopify.com/investors/press-releases/shopify-delivers-again-as-merchants-clear-100-billion-in-q1-gmv"],
    ["Amazon 2026 Q1", "Amazon：Q1 2026 第三方卖家服务 415.78 亿美元，增长 14%；广告服务 172.43 亿美元，增长 24%。", "https://s2.q4cdn.com/299287126/files/doc_earnings/2026/q1/earnings-result/AMZN-Q1-2026-Earnings-Release.pdf"],
    ["Gartner B2B 买家 2026", "Gartner：67% B2B 买家偏好无销售代表体验；45% 在近期采购中使用 AI。", "https://www.gartner.com/en/newsroom/press-releases/2026-03-09-gartner-sales-survey-finds-67-percent-of-b2b-buyers-prefer-a-rep-free-experience"],
    ["Forrester 商业采购 2026", "Forrester：GenAI 搜索成为 B2B 买家起点；典型购买涉及 13 名内部利益相关者和 9 名外部影响者。", "https://www.forrester.com/press-newsroom/forrester-2026-the-state-of-business-buying/"],
    ["中国外贸 2025", "ECNS/SCIO/GAC：2025 年中国货物贸易 45.47 万亿元，增长 3.8%；民营企业占 57.3%。", "https://www.ecns.cn/m/news/cns-wire/2026-01-14/detail-iheywhna5922248.shtml"],
    ["中国跨境电商 2025", "SCIO/GAC：2025 年跨境电商进出口 2.75 万亿元，比 2020 年增长 69.7%。", "https://english.scio.gov.cn/pressroom/node_9018308.html"],
    ["IAB/PwC 2025 数字广告", "IAB/PwC：2025 年美国互联网广告收入 2946 亿美元，增长 13.9%；视频增长 25.4%。", "https://www.iab.com/wp-content/uploads/2026/04/IAB_PwC_Internet_Ad_Revenue_Report_Full_Year_2025_April_2026.pdf"],
    ["IAB Creator 2025", "IAB：美国 Creator ad spend 2025 年预计 370 亿美元，增长 26%；48% 买家视为 must buy。", "https://www.iab.com/insights/2025-creator-economy-ad-spend-strategy-report/"],
    ["IAB Video 2025", "IAB：2025 年美国数字视频广告支出预计 720 亿美元；GenAI、精准定向和效果 KPI 推动变化。", "https://www.iab.com/insights/video-ad-spend-report-2025/"],
    ["UNCTAD 数字服务", "UNCTAD：2024 年可数字交付产品贸易增长 10%，占全球服务出口 56%。", "https://unctad.org/news/chips-and-other-electronic-components-power-digital-trade-asia-global-hub"],
    ["DataReportal 2026", "DataReportal/GWI：2026 报告显示全球社媒用户身份 56.6 亿；社媒和视频 feed 每周约 18 小时 36 分钟。", "https://datareportal.com/reports/digital-2026-two-in-three-people-use-social-media"],
    ["WTO 数字交付服务", "WTO：2023 年全球数字交付服务出口 4.25 万亿美元，占世界货物和服务出口 13.8%。", "https://www.wto.org/english/news_e/news24_e/tfore_10apr24_e.htm"],
    ["Gartner B2B 买家 2025", "Gartner：61% B2B 买家偏好无销售代表购买体验；73% 主动避开无关外联；69% 认为官网和销售信息不一致。", "https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-sales-survey-finds-61-percent-of-b2b-buyers-prefer-a-rep-free-buying-experience"],
    ["DHL 电商趋势 2025", "DHL：调研 24 个市场 24000 名购物者；81% 因缺少偏好配送弃购，79% 因退货流程不符预期离开。", "https://group.dhl.com/en/media-relations/press-releases/2025/dhl-e-commerce-trends-report-2025.html"],
    ["Baymard 结账体验 2025", "Baymard：18% 美国网购者因结账流程过长/复杂弃购；优化结账设计可带来约 35% 转化提升。", "https://baymard.com/blog/ecommerce-checkout-usability-report-and-benchmark"],
    ["BigCommerce 工业买家 2025", "BigCommerce：超过 60% 工业买家在线购买，数字渠道约占三分之一购买。", "https://www.bigcommerce.com/resources/2025-industrial-buyer-report/"],
    ["Stripe 支付本地化", "Stripe：动态展示相关本地支付方式可提升转化；不同国家支付方式偏好差异明显。", "https://stripe.com/gb/resources/more/payment-localization-best-practices-a-guide-for-scaling-payments-worldwide"],
]


def build():
    overview_img, matrix_img, pathway_img = build_visual_assets()
    doc = Document()
    setup(doc)

    title = doc.add_paragraph(style="Title")
    title.add_run("出海机会地图\n初始调研版")
    subtitle = doc.add_paragraph(style="Subtitle")
    subtitle.add_run("面向内容表达型个人/小团队：先从海外销售表达诊断、急救包、资料包切入，用 7-14 天付费信号验证。")

    callout(
        doc,
        "推荐结论",
        "第一阶段最应该卖“海外销售表达诊断 / 急救包 / 资料包”，不是账号代运营、泛内容、海外 PR、达人撮合或品牌全案。优先入口是 A6 广告微诊断、A1 广告急救包、A2 展会资料包、A3 页面表达优化：这些服务能绑定客户已有预算口，交付边界清楚，并能在 7-14 天内用定金、合同、报价推进或采购流程验证。",
    )
    h2(doc, "适合人群")
    table(doc, ["维度", "典型特征", "机会选择"], READER_FIT_ROWS, widths=[Cm(3.0), Cm(11.0), Cm(10.2)], font_size=7.8)
    action_strip(doc, COVER_ACTIONS, title="第一页判断")

    page(doc)
    h1(doc, "0. 第一阶段卖什么")
    para(doc, "首轮目标不是证明所有出海服务都能做，而是找到一个愿意快速付费的触发场景。推荐从表达诊断、广告急救、展会资料、页面优化四个入口开始。")
    table(
        doc,
        ["问题", "建议答案", "判断依据"],
        RECOMMENDATION_ROWS,
        widths=[Cm(3.0), Cm(7.0), Cm(14.8)],
        font_size=7.5,
    )
    h2(doc, "首轮服务包")
    table(
        doc,
        ["服务包", "试单价", "适用客户", "交付物", "边界"],
        SERVICE_PACKAGE_ROWS,
        widths=[Cm(3.0), Cm(2.5), Cm(5.6), Cm(7.3), Cm(6.1)],
        font_size=6.9,
    )

    page(doc)
    h1(doc, "0.1 第一批客户与筛选标准")
    para(doc, "第一批客户只找“正在做海外动作但表达造成损耗”的人。客户越接近现有预算、现有材料和明确时间点，越适合进入 7-14 天验证。")
    table(
        doc,
        ["客户类型", "已有动作", "付费触发", "优先服务包"],
        FIRST_CLIENT_ROWS,
        widths=[Cm(3.0), Cm(7.2), Cm(7.3), Cm(6.7)],
        font_size=7.2,
    )
    h2(doc, "进入首轮前的四个门槛")
    table(doc, ["筛选项", "通过信号", "排除信号"], SCREENING_ROWS, widths=[Cm(3.0), Cm(10.8), Cm(10.4)], font_size=7.5)
    action_strip(doc, UX_ACTIONS, title="首轮判断顺序")

    page(doc)
    h1(doc, "0.2 先不做什么")
    para(doc, "暂缓方向不是永远不做，而是不放进第一轮成交承诺。第一阶段要避开资源依赖高、结果责任重、验证周期长的机会。")
    table(
        doc,
        ["暂缓机会", "为什么不先做", "后续进入条件"],
        NOT_FIRST_ROWS,
        widths=[Cm(5.0), Cm(9.4), Cm(9.7)],
        font_size=7.3,
    )
    action_strip(doc, UX_CHECKPOINT_ACTIONS, title="首轮边界")

    page(doc)
    h1(doc, "0.3 7-14 天付款验证与升级路径")
    para(doc, "验证动作要把兴趣逼近付款。第一轮只需要证明一个入口成立：50 家名单、15 家高分、3 份报价、1 个定金/合同/采购流程信号。")
    table(
        doc,
        ["时间", "动作", "筛选标准", "产出"],
        VALIDATION_SPRINT_ROWS,
        widths=[Cm(2.5), Cm(4.0), Cm(11.0), Cm(6.7)],
        font_size=7.2,
    )
    h2(doc, "从第一单升级到复购")
    table(
        doc,
        ["入口", "第一单", "下一单", "升级依据"],
        UPGRADE_PATH_ROWS,
        widths=[Cm(3.2), Cm(4.8), Cm(6.7), Cm(9.4)],
        font_size=7.2,
    )
    callout(
        doc,
        "执行标准",
        "第一个付款来自广告，就向素材测试、页面和复盘加深；来自展会，就向展后跟进、案例和官网信任资产加深；来自页面，就向 FAQ、报价模板和卖点库加深。",
    )

    page(doc)
    h1(doc, "0.4 2026 最新信号")
    para(doc, "2025 年报能证明预算池存在，2026 年内数据用来判断当前窗口是否仍有动作、预算和表达损耗。结论是：外贸、独立站、平台卖家和 B2B 买家行为都在把机会推向“可自证、可转述、可快速修复”的销售表达资产。")
    table(
        doc,
        ["2026 信号", "最新数据", "对机会的判断", "服务动作"],
        CURRENT_2026_ROWS,
        widths=[Cm(3.0), Cm(8.4), Cm(7.6), Cm(5.0)],
        font_size=7.0,
    )

    page(doc)
    h1(doc, "0.5 一页总览图")
    para(doc, "先把预算证据、能力适配和第一轮入口放到同一张图里。核心切入点是“销售表达资产”，不是泛内容、泛账号或泛投放。")
    center_picture(doc, overview_img)

    page(doc)
    h1(doc, "0.6 优先级矩阵")
    para(doc, "矩阵用于防止“机会很多所以都想做”。右上角是先做区，左侧和下方不是删除，而是等首批付款证据出现后再升级。")
    center_picture(doc, matrix_img)

    page(doc)
    h1(doc, "0.7 路径图与验证漏斗")
    para(doc, "这张图把机会关系转成行动路径：从一个触发场景进入，拿到付款信号后沿相邻节点加深，而不是同时推进全部方向。")
    center_picture(doc, pathway_img)

    page(doc)
    h1(doc, "1. 数据底座：调研扩容")
    para(doc, "数据底座拆成三层：2026 当前窗口、市场与预算池、买家行为与转化阻力、适用性判据。每条数据都必须回答“谁正在花钱、哪里发生损耗、内容表达型服务者能不能用现有能力交付第一单”。")
    h2(doc, "1.1 市场与预算池信号")
    table(
        doc,
        ["信号", "调研数据", "能证明什么", "适用客户", "适用机会（编号+名称）"],
        MARKET_SIGNAL_ROWS,
        widths=[Cm(2.4), Cm(7.8), Cm(7.1), Cm(4.1), Cm(3.2)],
        font_size=6.5,
    )

    page(doc)
    h1(doc, "1.2 买家行为与转化阻力")
    para(doc, "市场规模只能说明“有人在花钱”，但不能说明“为什么需要内容表达型服务者”。买家行为数据用来识别表达、信任、自助研究、物流/支付说明和结账摩擦这些更具体的损耗。")
    table(
        doc,
        ["行为信号", "调研数据", "对机会的含义", "适用客户", "适用机会（编号+名称）"],
        BUYER_BEHAVIOR_ROWS,
        widths=[Cm(2.7), Cm(7.7), Cm(7.2), Cm(4.1), Cm(3.2)],
        font_size=6.7,
    )

    page(doc)
    h1(doc, "1.3 适用性判据")
    para(doc, "这一页用于把“机会看起来能做”变成“这个客户是否适用”。如果一个客户不满足这些判据，就算赛道大，也不应该进入首轮。")
    table(
        doc,
        ["适用信号", "判据", "适用 / 不适用", "适用机会（编号+名称）"],
        APPLICABILITY_SIGNAL_ROWS,
        widths=[Cm(3.0), Cm(7.5), Cm(10.8), Cm(3.5)],
        font_size=7.0,
    )

    page(doc)
    h1(doc, "1.4 从数据抽取核心")
    para(doc, "数据点增加后，核心不是变多，而是更清楚：第一轮要找“已有海外预算但销售表达造成损耗”的客户，用低资源依赖、可付款验证的交付物切入。")
    table(
        doc,
        ["抽取层", "核心结论", "数据依据", "落地方式"],
        CORE_EXTRACTION_ROWS,
        widths=[Cm(2.8), Cm(7.0), Cm(9.0), Cm(5.8)],
        font_size=7.5,
    )

    page(doc)
    h1(doc, "2. 出海机会系统架构")
    para(doc, "把“出海”拆成一条商业链路：选买家 -> 定卖点 -> 建信任 -> 获流量 -> 促转化 -> 扩渠道 -> 复购留存。机会不是孤立点，而是同一条收入链路里的不同预算节点。")
    table(
        doc,
        ["链路环节", "客户在做什么", "可服务机会", "关联机会（编号+名称）"],
        SYSTEM_ROWS,
        widths=[Cm(3.6), Cm(7.2), Cm(8.5), Cm(3.2)],
        font_size=8.0,
    )
    callout(
        doc,
        "地图读法",
        "优先看已有预算口：广告、展会、平台店铺、官网、销售开发、渠道招商。不要把“客户应该做内容”当机会，要找到“客户已经为哪件事花钱，但表达造成损耗”。",
    )
    action_strip(doc, SYSTEM_ACTIONS, title="系统页读法")

    page(doc)
    h1(doc, "3. 机会地图 A：最快付费切口")
    table(
        doc,
        ["编号", "机会", "买家/触发", "预算口", "首单交付", "能力关联", "难/益/验", "证据支撑"],
        OPPORTUNITY_ROWS[:6],
        widths=[Cm(0.8), Cm(3.6), Cm(4.2), Cm(2.7), Cm(4.1), Cm(2.8), Cm(2.2), Cm(6.4)],
        font_size=7.1,
    )
    action_strip(doc, OPPORTUNITY_ACTIONS["A"], title="A 类先做判断")

    page(doc)
    h1(doc, "3. 机会地图 B：广告、UGC 与素材测试")
    table(
        doc,
        ["编号", "机会", "买家/触发", "预算口", "首单交付", "能力关联", "难/益/验", "证据支撑"],
        OPPORTUNITY_ROWS[6:12],
        widths=[Cm(0.8), Cm(3.6), Cm(4.2), Cm(2.7), Cm(4.1), Cm(2.8), Cm(2.2), Cm(6.4)],
        font_size=7.1,
    )
    action_strip(doc, OPPORTUNITY_ACTIONS["B"], title="B 类先做判断")

    page(doc)
    h1(doc, "3. 机会地图 C：信任资产")
    table(
        doc,
        ["编号", "机会", "买家/触发", "预算口", "首单交付", "能力关联", "难/益/验", "证据支撑"],
        OPPORTUNITY_ROWS[12:18],
        widths=[Cm(0.8), Cm(3.6), Cm(4.2), Cm(2.7), Cm(4.1), Cm(2.8), Cm(2.2), Cm(6.4)],
        font_size=7.1,
    )
    action_strip(doc, OPPORTUNITY_ACTIONS["C"], title="C 类先做判断")

    page(doc)
    h1(doc, "3. 机会地图 D：展会、渠道与销售支持")
    table(
        doc,
        ["编号", "机会", "买家/触发", "预算口", "首单交付", "能力关联", "难/益/验", "证据支撑"],
        OPPORTUNITY_ROWS[18:24],
        widths=[Cm(0.8), Cm(3.6), Cm(4.2), Cm(2.7), Cm(4.1), Cm(2.8), Cm(2.2), Cm(6.4)],
        font_size=7.1,
    )
    action_strip(doc, OPPORTUNITY_ACTIONS["D"], title="D 类先做判断")

    page(doc)
    h1(doc, "3. 机会地图 E：工具化与流程沉淀")
    table(
        doc,
        ["编号", "机会", "买家/触发", "预算口", "首单交付", "能力关联", "难/益/验", "证据支撑"],
        OPPORTUNITY_ROWS[24:30],
        widths=[Cm(0.8), Cm(3.6), Cm(4.2), Cm(2.7), Cm(4.1), Cm(2.8), Cm(2.2), Cm(6.4)],
        font_size=7.1,
    )
    action_strip(doc, OPPORTUNITY_ACTIONS["E"], title="E 类先做判断")

    page(doc)
    h1(doc, "3. 机会地图 F：暂缓但保留观察")
    table(
        doc,
        ["编号", "机会", "买家/触发", "预算口", "首单交付", "能力关联", "难/益/验", "证据支撑"],
        OPPORTUNITY_ROWS[30:],
        widths=[Cm(0.8), Cm(3.6), Cm(4.2), Cm(2.7), Cm(4.1), Cm(2.8), Cm(2.2), Cm(6.4)],
        font_size=7.1,
    )
    action_strip(doc, OPPORTUNITY_ACTIONS["F"], title="F 类先做判断")

    page(doc)
    h1(doc, "4. 机会之间的关联")
    para(doc, "下面的关系边用于决定产品组合和升级路径。初始阶段不要一次卖完整链路，而是从一个强触发点进入，再把客户反馈沉淀到相邻机会。")
    table(
        doc,
        ["上游节点", "起点机会", "下游机会（编号+名称）", "为什么有关联", "产品化含义"],
        RELATION_ROWS,
        widths=[Cm(3.4), Cm(2.2), Cm(3.8), Cm(9.2), Cm(7.0)],
        font_size=7.1,
    )
    page(doc)
    h1(doc, "5. 与内容表达能力的关联")
    table(doc, ["能力层", "具体能力", "匹配度", "可承接机会"], FIT_ROWS, widths=[Cm(4.0), Cm(9.2), Cm(2.2), Cm(7.0)], font_size=8.0)
    h2(doc, "能力结论")
    bullets(
        doc,
        [
            "最强能力不是“会做内容”，而是“能把客户的产品、场景、卖点重组为销售表达”。",
            "拍摄和剪辑是交付手段，不是商业入口；入口必须是广告、展会、页面、销售开发这类预算口。",
            "账号运营、代投、海外 PR、达人网络是后置能力；首轮不要让它们成为交付承诺。",
        ],
    )
    action_strip(doc, ABILITY_ACTIONS, title="能力页落点")

    page(doc)
    h1(doc, "6. 多维评分框架")
    table(doc, ["维度", "权重", "看什么", "对内容表达型服务者的解释"], SCORE_ROWS, widths=[Cm(3.0), Cm(1.8), Cm(9.2), Cm(10.5)], font_size=7.8)
    h2(doc, "初始排序")
    table(doc, ["排序", "方向", "为什么优先", "建议验证方式"], SHORTLIST_ROWS, widths=[Cm(1.2), Cm(6.2), Cm(9.0), Cm(9.0)], font_size=7.3)

    page(doc)
    h1(doc, "7. 付费验证前的执行规则")
    table(doc, ["项目", "要求", "为什么"], VALIDATION_ROWS, widths=[Cm(3.8), Cm(11.0), Cm(9.8)], font_size=8.0)
    callout(
        doc,
        "推荐路径",
        "第一轮不要证明“出海服务能不能做”，而是证明哪一个触发场景愿意最快付钱。先用 A1 广告急救包、A2 展会资料包、A3 页面表达优化、A6 广告微诊断跑 15 个微诊断；第一个付费客户来自广告、展会、Listing 还是 B2B 官网，就把下一轮机会地图向那个节点加深。",
    )
    action_strip(doc, VALIDATION_ACTIONS, title="执行页落点")

    page(doc)
    h1(doc, "8. 数据来源")
    table(doc, ["主题", "来源与数据", "链接"], SOURCE_ROWS, widths=[Cm(3.8), Cm(12.3), Cm(10.5)], font_size=6.2)
    action_strip(doc, SOURCE_ACTIONS, title="数据来源怎么用")

    audit_delivery_text(doc)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
