"""YAML-based data store for ODE entities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Type, TypeVar

import yaml

from .models import Opportunity, Signal, Competitor, Evidence
from .constants import (
    OPPORTUNITIES_DIR, SIGNALS_DIR, COMPETITORS_DIR, EVIDENCE_DIR,
    REPORTS_DIR, SCHEMA_VERSION,
)


T = TypeVar("T")


def _project_root() -> Path:
    """Return the ODE project root (~/opportunity-engine)."""
    return Path(os.environ.get("ODE_ROOT", Path.home() / "opportunity-engine"))


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Generic YAML I/O
# ---------------------------------------------------------------------------

def _entity_dir(entity_type: str) -> Path:
    mapping = {
        "opportunity": OPPORTUNITIES_DIR,
        "signal": SIGNALS_DIR,
        "competitor": COMPETITORS_DIR,
        "evidence": EVIDENCE_DIR,
    }
    rel = mapping.get(entity_type)
    if not rel:
        raise ValueError(f"Unknown entity type: {entity_type}")
    return _ensure_dir(_project_root() / rel)


def save_entity(entity, entity_type: str) -> Path:
    """Save an entity (dataclass with to_dict()) to YAML."""
    d = entity.to_dict()
    d["_schema_version"] = SCHEMA_VERSION
    dirpath = _entity_dir(entity_type)
    filepath = dirpath / f"{entity.id}.yaml"
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(d, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return filepath


def load_entity(entity_id: str, entity_type: str, cls: Type[T]) -> Optional[T]:
    """Load an entity from YAML by ID."""
    dirpath = _entity_dir(entity_type)
    filepath = dirpath / f"{entity_id}.yaml"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    d.pop("_schema_version", None)
    if not d:
        return None
    # Filter to only fields the dataclass accepts
    import dataclasses
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in d.items() if k in valid_fields}
    if not filtered:
        return None
    return cls(**filtered)


def list_entities(entity_type: str, cls: Type[T]) -> list[T]:
    """List all entities of a given type."""
    dirpath = _entity_dir(entity_type)
    if not dirpath.exists():
        return []
    results = []
    import dataclasses
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    for filepath in sorted(dirpath.glob("*.yaml")):
        with open(filepath, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        d.pop("_schema_version", None)
        if not d:
            print(f"Warning: skipped empty/corrupt {filepath}", file=__import__('sys').stderr)
            continue
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        try:
            results.append(cls(**filtered))
        except TypeError as e:
            print(f"Warning: skipped malformed {filepath}: {e}", file=__import__('sys').stderr)
            continue
    return results


def delete_entity(entity_id: str, entity_type: str) -> bool:
    """Delete an entity file. Returns True if deleted."""
    dirpath = _entity_dir(entity_type)
    filepath = dirpath / f"{entity_id}.yaml"
    if filepath.exists():
        filepath.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def save_opportunity(opp: Opportunity) -> Path:
    return save_entity(opp, "opportunity")

def load_opportunity(opp_id: str) -> Optional[Opportunity]:
    return load_entity(opp_id, "opportunity", Opportunity)

def list_opportunities() -> list[Opportunity]:
    return list_entities("opportunity", Opportunity)

def save_signal(sig: Signal) -> Path:
    return save_entity(sig, "signal")

def load_signal(sig_id: str) -> Optional[Signal]:
    return load_entity(sig_id, "signal", Signal)

def list_signals(opportunity_id: str = "") -> list[Signal]:
    all_sigs = list_entities("signal", Signal)
    if opportunity_id:
        return [s for s in all_sigs if s.opportunity_id == opportunity_id]
    return all_sigs

def save_competitor(comp: Competitor) -> Path:
    return save_entity(comp, "competitor")

def load_competitor(comp_id: str) -> Optional[Competitor]:
    return load_entity(comp_id, "competitor", Competitor)

def list_competitors(opportunity_id: str = "") -> list[Competitor]:
    all_comps = list_entities("competitor", Competitor)
    if opportunity_id:
        return [c for c in all_comps if c.opportunity_id == opportunity_id]
    return all_comps

def save_evidence(ev: Evidence) -> Path:
    return save_entity(ev, "evidence")

def reports_dir() -> Path:
    return _ensure_dir(_project_root() / REPORTS_DIR)


def find_opportunity_by_name(name: str) -> Optional[Opportunity]:
    """Find an opportunity by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for opp in list_opportunities():
        if name_lower in opp.name.lower() or name_lower in opp.id.lower():
            return opp
    return None
