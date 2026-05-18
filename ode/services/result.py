"""Surface-neutral service result helpers."""

from __future__ import annotations


def ok(data: dict, message: str = "") -> dict:
    return {"ok": True, "data": data, "message": message}


def fail(message: str) -> dict:
    return {"ok": False, "data": {}, "message": message}
