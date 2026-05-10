from pathlib import Path

from ode.imports.detector_integration import build_closed_loop_plan, load_imported_detector, load_seed, validate_plan


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
