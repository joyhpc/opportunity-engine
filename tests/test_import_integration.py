from pathlib import Path

from ode.imports.detector_integration import (
    build_closed_loop_plan,
    load_imported_detector,
    load_seed,
    validate_plan,
    validate_plan_schema,
)


ROOT = Path(__file__).resolve().parents[1]


def test_imported_detector_assets_are_discoverable():
    assets = load_imported_detector(ROOT)

    assert assets.template_files
    assert assets.subtask_files
    assert {path.stem for path in assets.subtask_files} >= {"signal_capture", "market_screening"}
    assert {path.name for path in assets.tool_files} >= {"opportunity_scorer.py", "financial_model.py"}


def test_seed_builds_valid_closed_loop_plan():
    seed = load_seed(ROOT / "examples" / "import_integration" / "opportunity_seed.json")
    plan = build_closed_loop_plan(seed, ROOT)

    assert validate_plan(plan) == []
    assert [stage["id"] for stage in plan["stages"]] == [
        "SENSE",
        "SCREEN",
        "ANALYZE",
        "VALIDATE",
        "PLAN",
        "LAUNCH",
        "MONITOR",
    ]
    assert plan["stages"][0]["imported_subtasks"] == ["signal_capture"]
    assert "market_screening" in plan["stages"][1]["imported_subtasks"]
    assert "python tools/validate_import_integration.py" in plan["verification"]["commands"]


def test_plan_starts_with_repo_resource_planning_and_covers_tools():
    seed = load_seed(ROOT / "examples" / "import_integration" / "opportunity_seed.json")
    plan = build_closed_loop_plan(seed, ROOT)

    assert plan["solution_path"][0]["id"] == "PLAN_FIRST"
    assert "source.tool_files" in plan["solution_path"][0]["repo_resources"]

    source_tools = set(plan["source"]["tool_files"])
    planned_tools = {
        tool_use["tool_file"]
        for stage in plan["stages"]
        for tool_use in stage["tool_plan"]
    }
    assert source_tools <= planned_tools
    assert plan["tool_coverage"]["uncovered_tool_files"] == []

    validation_stage = next(stage for stage in plan["stages"] if stage["id"] == "VALIDATE")
    assert any(tool["tool_file"].endswith("idea_validator.py") for tool in validation_stage["tool_plan"])


def test_validate_plan_rejects_unassigned_imported_tools():
    seed = load_seed(ROOT / "examples" / "import_integration" / "opportunity_seed.json")
    plan = build_closed_loop_plan(seed, ROOT)

    for stage in plan["stages"]:
        stage["tool_plan"] = [
            tool
            for tool in stage["tool_plan"]
            if not tool["tool_file"].endswith("idea_validator.py")
        ]

    errors = validate_plan(plan)
    assert any("idea_validator.py" in error for error in errors)


def test_closed_loop_plan_matches_json_schema():
    seed = load_seed(ROOT / "examples" / "import_integration" / "opportunity_seed.json")
    plan = build_closed_loop_plan(seed, ROOT)

    assert validate_plan_schema(plan, ROOT) == []


def test_json_schema_rejects_missing_required_plan_field():
    seed = load_seed(ROOT / "examples" / "import_integration" / "opportunity_seed.json")
    plan = build_closed_loop_plan(seed, ROOT)
    del plan["source"]

    errors = validate_plan_schema(plan, ROOT)
    assert any("'source' is a required property" in error for error in errors)
