"""YAML-based data store for ODE entities."""

from __future__ import annotations

import dataclasses
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Type, TypeVar

import yaml

logger = logging.getLogger(__name__)

from .models import Opportunity, Signal, Competitor, Evidence
from .constants import (
    OPPORTUNITIES_DIR, SIGNALS_DIR, COMPETITORS_DIR, EVIDENCE_DIR,
    REPORTS_DIR, ALERTS_DIR, SCHEMA_VERSION,
)


T = TypeVar("T")


def _project_root() -> Path:
    """Return the ODE data root.

    Prefer an explicit ``ODE_ROOT``. Otherwise, when the CLI is launched from a
    checkout, use that checkout so generated data stays with the active repo.
    Fall back to the historical user-home location for installed-package usage.
    """

    explicit = os.environ.get("ODE_ROOT")
    if explicit:
        return Path(explicit)

    for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
        if (
            (candidate / "pyproject.toml").exists()
            and (candidate / "ode").is_dir()
        ):
            return candidate
        if (candidate / ".git").exists() and (candidate / "ode").is_dir():
            return candidate

    package_root = Path(__file__).resolve().parents[2]
    if (package_root / "pyproject.toml").exists() and (package_root / "ode").is_dir():
        return package_root

    return Path.home() / "opportunity-engine"


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
    """Save an entity (dataclass with to_dict()) to YAML. Uses atomic write."""
    d = entity.to_dict()
    d["_schema_version"] = SCHEMA_VERSION
    dirpath = _entity_dir(entity_type)
    filepath = dirpath / f"{entity.id}.yaml"
    # Atomic write: write to temp file then rename
    fd, tmp_path = tempfile.mkstemp(dir=dirpath, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(d, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
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
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    for filepath in sorted(dirpath.glob("*.yaml")):
        with open(filepath, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        d.pop("_schema_version", None)
        if not d:
            logger.warning("Skipped empty/corrupt %s", filepath)
            continue
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        try:
            results.append(cls(**filtered))
        except TypeError as e:
            logger.warning("Skipped malformed %s: %s", filepath, e)
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
    if opportunity_id:
        # Fast path: load only signals linked to this opportunity
        opp = load_opportunity(opportunity_id)
        if opp and opp.signals:
            results = []
            for sig_id in opp.signals:
                sig = load_entity(sig_id, "signal", Signal)
                if sig:
                    results.append(sig)
            return results
        return []
    return list_entities("signal", Signal)

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


def alerts_dir() -> Path:
    return _ensure_dir(_project_root() / ALERTS_DIR)


def find_opportunity_by_name(name: str) -> Optional[Opportunity]:
    """Find an opportunity by name (case-insensitive partial match)."""
    # Fast path: try direct ID load first
    direct = load_opportunity(name)
    if direct:
        return direct
    name_lower = name.lower()
    for opp in list_opportunities():
        if name_lower in opp.name.lower() or name_lower in opp.id.lower():
            return opp
    return None
