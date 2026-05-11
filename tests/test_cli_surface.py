import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_cli(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ode", *args],
        cwd=ROOT,
        env={**os.environ, "ODE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_cli_status_text_mode(tmp_path):
    result = _run_cli(["status"], tmp_path)

    assert result.returncode == 0
    assert "ODE Status" in result.stdout
    assert "Total opportunities: 0" in result.stdout


def test_cli_status_json_mode(tmp_path):
    result = _run_cli(["--json", "status"], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["total"] == 0


def test_parser_exposes_expected_commands():
    from ode.cli_parser import build_parser

    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(subparsers) == 1

    expected = {
        "create",
        "list",
        "show",
        "scan",
        "eval",
        "report",
        "status",
        "sources",
        "cases",
        "portfolio",
        "compare",
        "explore",
        "pain",
        "daily",
        "init-alerts",
        "insights",
        "lens",
        "experiment",
        "record-actuals",
        "refresh-gate",
    }
    assert expected <= set(subparsers[0].choices)


def test_pain_parser_only_exposes_reachable_grades():
    from ode.cli_parser import build_parser

    parser = build_parser()
    pain = next(
        action.choices["pain"]
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    min_grade = next(action for action in pain._actions if "--min-grade" in action.option_strings)

    assert min_grade.choices == ["C", "D", "E"]


def test_cli_json_bad_profile_json_returns_structured_error(tmp_path):
    result = _run_cli([
        "--json",
        "pain",
        "--hn-top",
        "0",
        "--reddit",
        "",
        "--no-product-hunt",
        "--profile-json",
        "{bad",
    ], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "Invalid JSON for --profile-json" in payload["message"]
    assert "Traceback" not in result.stderr


def test_cli_daily_json_mode(tmp_path):
    result = _run_cli([
        "--json",
        "daily",
        "--hn-top",
        "0",
        "--reddit",
        "",
        "--no-product-hunt",
        "--no-explore",
        "--cases-top",
        "0",
        "--date",
        "2026-05-11",
    ], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["alerts"] == []
    assert payload["data"]["watchlist_updates"] == []
    assert payload["data"]["report_path"].endswith("2026-05-11.md")
    assert "Daily Opportunity Warning Report" in payload["data"]["report_text"]


def test_cli_init_alerts_json_mode(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps({
        "cases": [
            {
                "id": "receipt-case",
                "name": "Receipt Case",
                "category": "SaaS",
                "region": "global",
                "claim": "Invoice-backed $50K contract.",
                "metric_type": "contract_value",
                "amount": 50000,
                "currency": "USD",
                "period": "2026",
                "evidence": [
                    {
                        "type": "payment_receipt",
                        "source_name": "Customer invoice",
                        "url": "https://example.com/invoice",
                    }
                ],
                "fit_tags": ["developer tools", "software engineering"],
            }
        ]
    }), encoding="utf-8")

    result = _run_cli([
        "--json",
        "init-alerts",
        "--path",
        str(cases_path),
        "--date",
        "2026-05-11",
        "--reset",
    ], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["case_count"] == 1
    assert payload["data"]["priors"]
    assert payload["data"]["report_path"].endswith("2026-05-11.md")
    assert "Initial Opportunity Warning System" in payload["data"]["report_text"]


def test_cli_pain_rejects_unreachable_grade(tmp_path):
    result = _run_cli(["pain", "--min-grade", "A"], tmp_path)

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_cli_entrypoint_stays_thin():
    source = (ROOT / "ode" / "cli.py").read_text(encoding="utf-8")

    assert "from ode import service" not in source
    assert "add_parser(" not in source
    assert "COMMANDS =" not in source
