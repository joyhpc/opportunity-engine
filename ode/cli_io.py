"""Shared CLI input helpers."""

from __future__ import annotations

import json
from pathlib import Path


class CliInputError(ValueError):
    """Raised when a CLI argument cannot be decoded into structured input."""


def load_profile_arg(args) -> dict | None:
    """Load a founder profile from inline JSON or a JSON file."""

    return load_profile_values(
        profile_json=getattr(args, "profile_json", None),
        profile=getattr(args, "profile", None),
    )


def load_profile_values(*, profile_json: str | None = None,
                        profile: str | None = None) -> dict | None:
    """Load a founder profile from raw argument values."""

    if profile_json:
        try:
            return json.loads(profile_json)
        except json.JSONDecodeError as exc:
            raise CliInputError(f"Invalid JSON for --profile-json: {exc}") from exc

    if profile:
        try:
            return json.loads(Path(profile).read_text(encoding="utf-8"))
        except OSError as exc:
            raise CliInputError(f"Cannot read --profile: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CliInputError(f"Invalid profile JSON: {exc}") from exc

    return None


def split_csv_arg(value: str | None) -> list[str] | None:
    """Split a comma-separated CLI value, preserving explicit empty lists."""

    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def load_diagnosis_facts_arg(args) -> dict:
    """Load DBS diagnosis facts from JSON plus individual CLI flags."""

    facts = {}
    if getattr(args, "facts_json", None):
        try:
            decoded = json.loads(args.facts_json)
        except json.JSONDecodeError as exc:
            raise CliInputError(f"Invalid JSON for --facts-json: {exc}") from exc
        if not isinstance(decoded, dict):
            raise CliInputError("--facts-json must decode to an object")
        facts.update(decoded)

    for key in (
        "product",
        "price",
        "buyer",
        "acquisition",
        "delivery",
        "monthly_revenue",
        "demand",
        "scalability",
    ):
        value = getattr(args, key, None)
        if value is not None:
            facts[key] = value

    return facts
