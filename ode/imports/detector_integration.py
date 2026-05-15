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


SCHEMA_VERSION = "1.1.0"
DEFAULT_IMPORT_PATH = Path("imports") / "opportunity-detector"
DEFAULT_SCHEMA_PATH = Path("schemas") / "opportunity_import_flow.schema.json"
STAGE_ORDER = ["SENSE", "SCREEN", "ANALYZE", "VALIDATE", "PLAN", "LAUNCH", "MONITOR"]
TOOL_USAGE_RULES = {
    "SENSE": [
        (
            "trend_scanner.py",
            "Scan trends and community signals before any scoring work.",
            "It is the imported detector tool dedicated to trend and signal capture.",
        ),
        (
            "pain_miner.py",
            "Extract repeated user pains from community and interview inputs.",
            "It turns raw signals into pain evidence before screening starts.",
        ),
    ],
    "SCREEN": [
        (
            "market_sizer.py",
            "Estimate TAM/SAM/SOM during the first market screen.",
            "It is the purpose-built sizing tool referenced by the market screening template.",
        ),
        (
            "competitor_matrix.py",
            "Build the quick competitor map for initial positioning.",
            "It is the best available repo tool for competitor landscape structure.",
        ),
        (
            "financial_model.py",
            "Run rough unit economics before the first Go/Maybe/Kill decision.",
            "It is the imported model for CAC, LTV, margin, and payback assumptions.",
        ),
        (
            "opportunity_scorer.py",
            "Convert the screen into a scored Go/Maybe/Kill recommendation.",
            "It is the explicit scorecard tool for the screening gate.",
        ),
    ],
    "ANALYZE": [
        (
            "market_sizer.py",
            "Refine segment sizing for the deep market analysis.",
            "Deep analysis should reuse the sizing tool instead of inventing a new estimate path.",
        ),
        (
            "competitor_matrix.py",
            "Run the deeper competitor teardown and differentiation map.",
            "The same matrix tool is the best fit for both quick and deep competitive work.",
        ),
        (
            "financial_model.py",
            "Build full NPV, sensitivity, and scenario analysis.",
            "It is the best available financial tool for the ANALYZE gate.",
        ),
    ],
    "VALIDATE": [
        (
            "idea_validator.py",
            "Select validation experiments and pass/fail checks for critical assumptions.",
            "It is the imported detector tool focused on validation design.",
        ),
    ],
    "PLAN": [
        (
            "financial_model.py",
            "Translate validation results into budget and resource planning assumptions.",
            "Business planning should carry forward the same inspected economics model.",
        ),
        (
            "report_generator.py",
            "Assemble the business model, GTM, resource plan, and risk plan artifacts.",
            "It is the repo tool for turning analysis outputs into shareable planning artifacts.",
        ),
    ],
    "LAUNCH": [
        (
            "report_generator.py",
            "Generate the launch checklist and first revenue record artifact.",
            "The launch phase needs a durable execution artifact, not a new analysis tool.",
        ),
    ],
    "MONITOR": [
        (
            "trend_scanner.py",
            "Continue monitoring market and community signal changes.",
            "Monitoring should reuse the scanner rather than silently dropping signal capture.",
        ),
        (
            "pain_miner.py",
            "Track recurring user pain after launch.",
            "It is the best repo fit for turning qualitative monitoring into repeatable evidence.",
        ),
        (
            "report_generator.py",
            "Produce iteration reviews from monitoring data.",
            "It keeps the monitor loop inspectable through generated artifacts.",
        ),
    ],
}


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
    resource_root = assets.root.parent.parent
    subtask_by_stage = _subtask_by_stage(assets.subtasks)
    tool_plan_by_stage = _tool_plan_by_stage(assets.tool_files, resource_root)

    stages = [
        _stage(
            "SENSE",
            "Opportunity sensing",
            subtask_by_stage,
            tool_plan_by_stage,
            ["Signal list", "Desk research memo", "One-page opportunity brief"],
            ["At least two independent signals are recorded", "Brief states confidence and unknowns"],
        ),
        _stage(
            "SCREEN",
            "Initial screening",
            subtask_by_stage,
            tool_plan_by_stage,
            ["TAM/SAM/SOM estimate", "Competitor map", "Capability gap", "Rough unit economics"],
            ["Scorecard produces Go/Maybe/Kill", "Economics assumptions are explicit"],
        ),
        _stage(
            "ANALYZE",
            "Deep analysis",
            subtask_by_stage,
            tool_plan_by_stage,
            ["Market deep dive", "Risk register", "Financial model"],
            ["NPV and sensitivity assumptions are inspectable", "P0 regulatory risks are called out"],
        ),
        _stage(
            "VALIDATE",
            "Validation",
            subtask_by_stage,
            tool_plan_by_stage,
            ["Hypothesis list", "MVP design", "Validation report"],
            ["Paid or return-user evidence is linked", "Privacy and safety checks are complete"],
        ),
        _stage(
            "PLAN",
            "Business planning",
            subtask_by_stage,
            tool_plan_by_stage,
            ["Business model", "Resource plan", "GTM plan", "Risk mitigation plan"],
            ["Launch decision has owner, budget, and rollback condition"],
        ),
        _stage(
            "LAUNCH",
            "Execution",
            subtask_by_stage,
            tool_plan_by_stage,
            ["Phase-1 execution checklist", "First revenue record"],
            ["First measurable revenue or qualified customer commitment is recorded"],
        ),
        _stage(
            "MONITOR",
            "Monitoring",
            subtask_by_stage,
            tool_plan_by_stage,
            ["Metrics dashboard", "Iteration review"],
            ["Metrics are reviewed and next action is decided"],
        ),
    ]
    source_tool_files = [_rel(p, resource_root) for p in assets.tool_files]

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "joyhpc/opportunity-detector",
            "import_path": DEFAULT_IMPORT_PATH.as_posix(),
            "template_files": [_rel(p, resource_root) for p in assets.template_files],
            "subtask_files": [_rel(p, resource_root) for p in assets.subtask_files],
            "tool_files": source_tool_files,
        },
        "seed": seed,
        "solution_path": _solution_path(stages),
        "stages": stages,
        "tool_coverage": _tool_coverage(source_tool_files, stages),
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
        errors.append("schema_version must be 1.1.0")

    for field in ("source", "seed", "solution_path", "stages", "tool_coverage", "gates", "acceptance", "verification", "artifacts"):
        if field not in plan:
            errors.append(f"plan missing {field}")

    solution_path = plan.get("solution_path", [])
    if not solution_path:
        errors.append("solution_path must include the planning-first step")
    elif solution_path[0].get("id") != "PLAN_FIRST":
        errors.append("solution_path must start with PLAN_FIRST")

    source_tool_files = set(plan.get("source", {}).get("tool_files", []))
    planned_tool_files: set[str] = set()
    stage_ids = [stage.get("id") for stage in plan.get("stages", [])]
    if stage_ids != STAGE_ORDER:
        errors.append(f"stages must be exactly {', '.join(STAGE_ORDER)}")

    for stage in plan.get("stages", []):
        for field in ("name", "imported_subtasks", "tool_plan", "deliverables", "done_when"):
            if field not in stage:
                errors.append(f"stage {stage.get('id', '<unknown>')} missing {field}")
        if not stage.get("tool_plan"):
            errors.append(f"stage {stage.get('id', '<unknown>')} has no tool_plan")
        for tool_use in stage.get("tool_plan", []):
            for field in ("tool_file", "role", "why_best_fit"):
                if field not in tool_use:
                    errors.append(f"stage {stage.get('id', '<unknown>')} tool use missing {field}")
            tool_file = tool_use.get("tool_file")
            if tool_file:
                planned_tool_files.add(tool_file)
                if source_tool_files and tool_file not in source_tool_files:
                    errors.append(f"stage {stage.get('id', '<unknown>')} references unknown tool {tool_file}")
        if not stage.get("deliverables"):
            errors.append(f"stage {stage.get('id', '<unknown>')} has no deliverables")
        if not stage.get("done_when"):
            errors.append(f"stage {stage.get('id', '<unknown>')} has no done_when checks")

    uncovered_tools = sorted(source_tool_files - planned_tool_files)
    if uncovered_tools:
        errors.append("source tool files must be assigned to a stage: " + ", ".join(uncovered_tools))

    coverage = plan.get("tool_coverage", {})
    if sorted(coverage.get("used_tool_files", [])) != sorted(source_tool_files):
        errors.append("tool_coverage.used_tool_files must match all source tool files")
    if coverage.get("uncovered_tool_files") != []:
        errors.append("tool_coverage.uncovered_tool_files must be empty")

    commands = plan.get("verification", {}).get("commands", [])
    if "python tools/validate_import_integration.py" not in commands:
        errors.append("verification commands must include the import validator")

    return errors


def validate_plan_schema(plan: dict[str, Any],
                         repo_root: Path | None = None,
                         schema_path: Path | None = None) -> list[str]:
    """Return JSON Schema validation errors for the closed-loop plan."""

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema is required to validate the import flow schema"]

    root = (repo_root or Path.cwd()).resolve()
    path = schema_path or root / DEFAULT_SCHEMA_PATH
    schema = json.loads(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(plan), key=lambda error: list(error.path))

    messages: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"schema {location}: {error.message}")
    return messages


def _stage(
    stage_id: str,
    name: str,
    subtask_by_stage: dict[str, list[str]],
    tool_plan_by_stage: dict[str, list[dict[str, str]]],
    deliverables: list[str],
    done_when: list[str],
) -> dict[str, Any]:
    return {
        "id": stage_id,
        "name": name,
        "imported_subtasks": subtask_by_stage.get(stage_id, []),
        "tool_plan": tool_plan_by_stage.get(stage_id, []),
        "deliverables": deliverables,
        "done_when": done_when,
    }


def _tool_plan_by_stage(tool_files: list[Path], root: Path) -> dict[str, list[dict[str, str]]]:
    by_name = {path.name: _rel(path, root) for path in tool_files}
    plan = {stage: [] for stage in STAGE_ORDER}
    for stage_id, usages in TOOL_USAGE_RULES.items():
        for file_name, role, why_best_fit in usages:
            tool_file = by_name.get(file_name)
            if tool_file:
                plan[stage_id].append({
                    "tool_file": tool_file,
                    "role": role,
                    "why_best_fit": why_best_fit,
                })
    return plan


def _solution_path(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = [
        {
            "id": "PLAN_FIRST",
            "name": "Plan from repository resources",
            "repo_resources": ["source.template_files", "source.subtask_files", "source.tool_files"],
            "output": "Overall staged solution path with every best-fit repo tool bound before execution.",
        }
    ]
    for stage in stages:
        path.append({
            "id": stage["id"],
            "name": stage["name"],
            "repo_resources": [
                *[f"subtask:{name}" for name in stage.get("imported_subtasks", [])],
                *[tool["tool_file"] for tool in stage.get("tool_plan", [])],
            ],
            "output": "; ".join(stage.get("deliverables", [])),
        })
    return path


def _tool_coverage(source_tool_files: list[str], stages: list[dict[str, Any]]) -> dict[str, Any]:
    used = sorted({
        tool["tool_file"]
        for stage in stages
        for tool in stage.get("tool_plan", [])
    })
    return {
        "policy": "Every imported detector tool must be assigned to at least one stage before execution.",
        "used_tool_files": used,
        "uncovered_tool_files": sorted(set(source_tool_files) - set(used)),
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
