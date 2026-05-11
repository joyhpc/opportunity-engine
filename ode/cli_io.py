"""Shared CLI input helpers."""

from __future__ import annotations

import json
from pathlib import Path


class CliInputError(ValueError):
    """Raised when a CLI argument cannot be decoded into structured input."""


def load_profile_arg(args) -> dict | None:
    """Load a founder profile from inline JSON or a JSON file."""

    if getattr(args, "profile_json", None):
        try:
            return json.loads(args.profile_json)
        except json.JSONDecodeError as exc:
            raise CliInputError(f"Invalid JSON for --profile-json: {exc}") from exc

    if getattr(args, "profile", None):
        try:
            return json.loads(Path(args.profile).read_text(encoding="utf-8"))
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
