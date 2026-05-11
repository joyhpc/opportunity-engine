"""Shared helpers for source adapters."""

from __future__ import annotations

import html
import re


STRONG = "强"
MEDIUM = "中"
WEAK = "弱"


def clean_feed_text(value: str) -> str:
    """Collapse Atom/HTML text into a short readable snippet."""

    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*Read more on Product Hunt.*$", "", text, flags=re.I)
    text = re.sub(r"\s*(Discussion\s*\|\s*Link|Discussion|Link)\s*$", "", text, flags=re.I)
    return text


def strength_from_score(score: float) -> str:
    if score > 200:
        return STRONG
    if score > 50:
        return MEDIUM
    return WEAK


def strength_from_position(position: int, *, strong_before: int, medium_before: int) -> str:
    if position < strong_before:
        return STRONG
    if position < medium_before:
        return MEDIUM
    return WEAK


def append_note(source_notes: list[dict] | None, **event) -> None:
    if source_notes is not None:
        source_notes.append(event)
