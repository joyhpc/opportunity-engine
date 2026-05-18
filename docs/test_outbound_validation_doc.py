# -*- coding: utf-8 -*-
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "docs" / "出海销售表达服务_7天付费验证执行稿.docx"
PDF = ROOT / "docs" / "rendered_outbound_validation" / "outbound_validation.pdf"


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    return "".join(ET.fromstring(xml).itertext())


def main():
    assert DOCX.exists(), f"Missing DOCX: {DOCX}"
    assert PDF.exists(), f"Missing rendered PDF: {PDF}"

    text = docx_text(DOCX)
    required = [
        "今天先做这 5 件事",
        "7 天唯一成功标准",
        "只卖这一个东西",
        "只找这类客户",
        "7 天执行计划",
        "触达和电话话术",
        "客户回复后这样处理",
        "日终复盘表",
        "收到不少于 3000 元定金",
        "进入明确采购流程",
    ]
    forbidden = [
        "DBS 路由",
        "概念拆解",
        "商业机器诊断",
        "对标过滤",
        "Trend",
        "Twirl",
        "Benchmark",
        "Slow is Fast",
        "做生死判断",
    ]

    for item in required:
        assert item in text, f"Missing required text: {item}"
    for item in forbidden:
        assert item not in text, f"Old report text leaked back in: {item}"

    pages = len(PdfReader(str(PDF)).pages)
    assert pages <= 5, f"Document should stay concise; got {pages} pages"
    assert len(text) < 5200, f"Document text expanded too much: {len(text)} chars"

    print(f"PASS pages={pages} chars={len(text)}")


if __name__ == "__main__":
    main()
