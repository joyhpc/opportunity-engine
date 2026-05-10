"""Data source registry for opportunity discovery."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml


CATALOG_VERSION = "1.0.0"
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "sources" / "opportunity_sources.yaml"
REQUIRED_FIELDS = {
    "id",
    "label",
    "status",
    "layer",
    "adapter",
    "endpoint",
    "auth",
    "default_enabled",
    "freshness",
    "requires",
    "params",
    "strength_method",
    "best_for",
    "limitations",
}


@dataclass(frozen=True)
class DataSource:
    id: str
    label: str
    status: str
    layer: str
    adapter: str
    endpoint: str
    auth: str
    default_enabled: bool
    freshness: str
    requires: list[str]
    params: list[str]
    strength_method: str
    best_for: list[str]
    limitations: list[str]
    region: str = "global"
    language: list[str] = None
    access_method: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_source_catalog(path: str | Path | None = None) -> list[DataSource]:
    """Load and validate the configured opportunity source catalog."""

    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != CATALOG_VERSION:
        raise ValueError(f"Source catalog schema_version must be {CATALOG_VERSION}")

    sources = data.get("sources", [])
    if not isinstance(sources, list) or not sources:
        raise ValueError("Source catalog must include a non-empty sources list")

    seen: set[str] = set()
    loaded: list[DataSource] = []
    for raw in sources:
        if not isinstance(raw, dict):
            raise ValueError("Each source entry must be a mapping")
        missing = sorted(REQUIRED_FIELDS - set(raw))
        if missing:
            raise ValueError(f"Source {raw.get('id', '<unknown>')} missing: {', '.join(missing)}")
        if raw["id"] in seen:
            raise ValueError(f"Duplicate source id: {raw['id']}")
        seen.add(raw["id"])
        optional = {
            "region": raw.get("region", "global"),
            "language": raw.get("language", []),
            "access_method": raw.get("access_method", "unknown"),
        }
        loaded.append(DataSource(
            **{key: raw[key] for key in REQUIRED_FIELDS},
            **optional,
        ))

    return sorted(loaded, key=lambda source: (source.status, source.region, source.id))


def list_sources(status: str | None = None, region: str | None = None) -> list[DataSource]:
    """List sources, optionally filtering by status."""

    sources = load_source_catalog()
    if status:
        sources = [source for source in sources if source.status == status]
    if region:
        sources = [source for source in sources if source.region == region]
    return sources


def get_source(source_id: str) -> DataSource | None:
    """Return a source by id."""

    for source in load_source_catalog():
        if source.id == source_id:
            return source
    return None


def runtime_source_ids() -> set[str]:
    """Source ids currently called by scan workers."""

    return {
        source.id
        for source in load_source_catalog()
        if source.status in {"active", "optional"}
    }


def format_source_catalog(sources: list[DataSource]) -> str:
    """Format source catalog for terminal output."""

    lines = [
        "# Opportunity Data Sources",
        "",
        "| Status | Region | ID | Layer | Default | Adapter |",
        "|--------|--------|----|-------|---------|---------|",
    ]
    for source in sources:
        default = "yes" if source.default_enabled else "no"
        lines.append(
            f"| {source.status} | {source.region} | {source.id} | {source.layer} | {default} | {source.adapter} |"
        )
    lines.extend([
        "",
        "Statuses:",
        "- active: called by scan workers when required CLI params are provided",
        "- optional: called only when optional dependencies and seed inputs exist",
        "- utility: available helper, not part of scan workers today",
        "- manual: human-curated local signal path",
        "- planned: deliberately listed but not yet scanned",
    ])
    return "\n".join(lines)
