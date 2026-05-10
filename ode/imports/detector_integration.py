"""Build a verifiable ODE plan from imported opportunity-detector assets.

The adapter intentionally stays small: it reads imported templates and subtasks,
maps them to ODE's seven-stage pipeline, then emits a schema-shaped plan that
can be checked without any model call.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = "1.0.0"
DEFAULT_IMPORT_PATH = Path("imports") / "opportunity-detector"
STAGE_ORDER = ["SENSE", "SCREEN", "ANALYZE", "VALIDATE", "PLAN", "LAUNCH", "MONITOR"]


@dataclass(frozen=True)
class ImportedDetectorAssets:
    root: Path
    template_files: list[Path]
    subtask_files: list[Path]
    tool_files: list[Path]
    subtasks: dict[str, dict[str, Any]]


def load_imported_detector(repo_root: Path | None = None) -> ImportedDetectorAssets:
    """Load the imported opportunity-detector directory."""

    root = (repo_root or Path.cwd()).resolve()
    import_root = root / DEFAULT_IMPORT_PATH
    if not import_root.exists():
        raise FileNotFoundError(f"Missing imported detector directory: {import_root}")

    template_files = sorted((import_root / "templates").glob("*.yaml"))
    subtask_files = sorted((import_root / "subtasks").glob("*.yaml"))
    tool_files = sorted((import_root / "tools").glob("*.py"))

    subtasks: dict[str, dict[str, Any]] = {}
    for path in subtask_files:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Subtask file must contain a mapping: {path}")
        subtasks[path.stem] = data

    return ImportedDetectorAssets(
        root=import_root,
        template_files=template_files,
        subtask_files=subtask_files,
        tool_files=[p for p in tool_files if p.name != "__init__.py"],
        subtasks=subtasks,
    )


def load_seed(path: Path) -> dict[str, Any]:
    """Load and minimally validate an opportunity seed JSON file."""

    seed = json.loads(path.read_text(encoding="utf-8"))
    required = {"id", "title", "domain", "signals", "constraints"}
    missing = sorted(required - set(seed))
    if missing:
        raise ValueError(f"Seed is missing required fields: {', '.join(missing)}")
    if not isinstance(seed["signals"], list) or not seed["signals"]:
        raise ValueError("Seed must include at least one signal")
    return seed


def build_closed_loop_plan(seed: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    """Build the deterministic import integration plan."""

    assets = load_imported_detector(repo_root)
    subtask_by_stage = _subtask_by_stage(assets.subtasks)

    stages = [
        _stage(
            "SENSE",
            "Opportunity sensing",
            subtask_by_stage,
            ["Signal list", "Desk research memo", "One-page opportunity brief"],
            ["At least two independent signals are recorded", "Brief states confidence and unknowns"],
        ),
        _stage(
            "SCREEN",
            "Initial screening",
            subtask_by_stage,
            ["TAM/SAM/SOM estimate", "Competitor map", "Capability gap", "Rough unit economics"],
            ["Scorecard produces Go/Maybe/Kill", "Economics assumptions are explicit"],
        ),
        _stage(
            "ANALYZE",
            "Deep analysis",
            subtask_by_stage,
            ["Market deep dive", "Risk register", "Financial model"],
            ["NPV and sensitivity assumptions are inspectable", "P0 regulatory risks are called out"],
        ),
        _stage(
            "VALIDATE",
            "Validation",
            subtask_by_stage,
            ["Hypothesis list", "MVP design", "Validation report"],
            ["Paid or return-user evidence is linked", "Privacy and safety checks are complete"],
        ),
        _stage(
            "PLAN",
            "Business planning",
            subtask_by_stage,
            ["Business model", "Resource plan", "GTM plan", "Risk mitigation plan"],
            ["Launch decision has owner, budget, and rollback condition"],
        ),
        _stage(
            "LAUNCH",
            "Execution",
            subtask_by_stage,
            ["Phase-1 execution checklist", "First revenue record"],
            ["First measurable revenue or qualified customer commitment is recorded"],
        ),
        _stage(
            "MONITOR",
            "Monitoring",
            subtask_by_stage,
            ["Metrics dashboard", "Iteration review"],
            ["Metrics are reviewed and next action is decided"],
        ),
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "joyhpc/opportunity-detector",
            "import_path": DEFAULT_IMPORT_PATH.as_posix(),
            "template_files": [_rel(p, assets.root.parent.parent) for p in assets.template_files],
            "subtask_files": [_rel(p, assets.root.parent.parent) for p in assets.subtask_files],
            "tool_files": [_rel(p, assets.root.parent.parent) for p in assets.tool_files],
        },
        "seed": seed,
        "stages": stages,
        "gates": [
            {
                "stage": "SCREEN",
                "decision": "Go/Maybe/Kill",
                "minimum_evidence": ["scorecard >= 60 for Go/Maybe", "kill reason is recorded when below threshold"],
            },
            {
                "stage": "VALIDATE",
                "decision": "Go/Pivot/Kill",
                "minimum_evidence": ["at least one direct user signal", "MVP result recorded", "risk owner assigned"],
            },
            {
                "stage": "PLAN",
                "decision": "Launch approval",
                "minimum_evidence": ["budget", "owner", "first revenue path", "rollback condition"],
            },
        ],
        "acceptance": [
            "The imported detector assets are discoverable without depending on the deleted source repository.",
            "A seed opportunity can be converted into a seven-stage ODE plan deterministically.",
            "The plan states deliverables, gate decisions, verification commands, and generated artifacts.",
        ],
        "verification": {
            "commands": [
                "python tools/check_environment.py",
                "python tools/validate_import_integration.py",
                "python -m pytest",
            ],
            "mainstream_environments": ["windows-latest", "ubuntu-latest", "macos-latest"],
        },
        "artifacts": [
            {
                "path": "examples/import_integration/opportunity_seed.json",
                "purpose": "Golden input for the minimal opportunity task executor.",
            },
            {
                "path": "examples/import_integration/closed_loop_plan.golden.json",
                "purpose": "Deterministic closed-loop plan generated from the imported detector assets.",
            },
        ],
    }


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Return validation errors for the closed-loop plan."""

    errors: list[str] = []
    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1.0.0")

    stage_ids = [stage.get("id") for stage in plan.get("stages", [])]
    if stage_ids != STAGE_ORDER:
        errors.append(f"stages must be exactly {', '.join(STAGE_ORDER)}")

    for stage in plan.get("stages", []):
        for field in ("name", "imported_subtasks", "deliverables", "done_when"):
            if field not in stage:
                errors.append(f"stage {stage.get('id', '<unknown>')} missing {field}")
        if not stage.get("deliverables"):
            errors.append(f"stage {stage.get('id', '<unknown>')} has no deliverables")
        if not stage.get("done_when"):
            errors.append(f"stage {stage.get('id', '<unknown>')} has no done_when checks")

    commands = plan.get("verification", {}).get("commands", [])
    if "python tools/validate_import_integration.py" not in commands:
        errors.append("verification commands must include the import validator")

    return errors


def _stage(
    stage_id: str,
    name: str,
    subtask_by_stage: dict[str, list[str]],
    deliverables: list[str],
    done_when: list[str],
) -> dict[str, Any]:
    return {
        "id": stage_id,
        "name": name,
        "imported_subtasks": subtask_by_stage.get(stage_id, []),
        "deliverables": deliverables,
        "done_when": done_when,
    }


def _subtask_by_stage(subtasks: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    mapping = {stage: [] for stage in STAGE_ORDER}
    for name, data in subtasks.items():
        attach_to = data.get("attach_to", [])
        text = " ".join(str(item).lower() for item in attach_to)
        if any(token in text for token in ("signal", "background", "opportunity")):
            mapping["SENSE"].append(name)
        if any(token in text for token in ("market", "competition", "capability", "economics")):
            mapping["SCREEN"].append(name)
        if "deep" in name or "analysis" in name:
            mapping["ANALYZE"].append(name)
        if "validation" in name:
            mapping["VALIDATE"].append(name)
        if "planning" in name or "business" in name:
            mapping["PLAN"].append(name)

    for values in mapping.values():
        values.sort()
    return mapping


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
