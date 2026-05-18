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


def test_cli_json_create_preserves_id_and_description(tmp_path):
    result = _run_cli([
        "--json",
        "create",
        "--name",
        "JSON Probe",
        "--id",
        "opp-jsonprobe",
        "--description",
        "desc-BBB",
        "--keywords",
        "foo,bar",
    ], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["id"] == "opp-jsonprobe"
    assert payload["data"]["keywords"] == ["foo", "bar"]

    saved = Path(payload["data"]["path"])
    assert saved.exists()
    assert "description: desc-BBB" in saved.read_text(encoding="utf-8")


def test_cli_json_supports_scan_eval_report_flow(tmp_path):
    create = _run_cli([
        "--json",
        "create",
        "--name",
        "Flow Probe",
        "--id",
        "opp-flow",
        "--keywords",
        "workflow",
    ], tmp_path)
    assert create.returncode == 0
    assert json.loads(create.stdout)["ok"] is True

    scan = _run_cli([
        "--json",
        "scan",
        "--opp-id",
        "opp-flow",
        "--hn-top",
        "0",
    ], tmp_path)
    assert scan.returncode == 0
    scan_payload = json.loads(scan.stdout)
    assert scan_payload["ok"] is True
    assert scan_payload["data"]["opp_id"] == "opp-flow"
    assert "signal_count" in scan_payload["data"]

    eval_result = _run_cli([
        "--json",
        "eval",
        "opp-flow",
        "--scores",
        json.dumps({"tam_size": 8, "growth": 7, "pain_evidence": 6}),
    ], tmp_path)
    assert eval_result.returncode == 0
    eval_payload = json.loads(eval_result.stdout)
    assert eval_payload["ok"] is True
    assert eval_payload["data"]["depth"] == "screen"
    assert eval_payload["data"]["gate"]

    report = _run_cli(["--json", "report", "opp-flow"], tmp_path)
    assert report.returncode == 0
    report_payload = json.loads(report.stdout)
    assert report_payload["ok"] is True
    assert report_payload["data"]["report_path"].endswith(".md")
    assert "report_text" in report_payload["data"]


def test_cli_json_unsupported_envelope_includes_data(capsys):
    from argparse import Namespace
    from ode.cli_json import run_json_mode

    run_json_mode(Namespace(command="not-registered"))

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": False,
        "data": {},
        "message": "--json not supported for 'not-registered' yet",
    }


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
        "dbs",
        "clarify",
        "diagnose",
        "deconstruct",
        "ai-hardware",
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


def test_cli_ai_hardware_json_mode(tmp_path):
    result = _run_cli([
        "--json",
        "ai-hardware",
        "--region",
        "shenzhen",
    ], tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    workflow = payload["data"]["workflow"]
    assert len(workflow["value_chain_layers"]) == 7
    assert "DBS Stage Plan" in payload["data"]["formatted"]


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


def test_service_command_registry_runs_read_only_status(tmp_path, monkeypatch):
    from ode.service_commands import (
        parse_registered_command,
        registered_command_names,
        run_registered_params,
        run_registered_command_from_string,
    )

    monkeypatch.setenv("ODE_ROOT", str(tmp_path))

    assert {"list", "show", "status", "sources", "cases", "portfolio"} <= (
        registered_command_names(read_only=True)
    )

    args = parse_registered_command("sources", "--region global")
    assert args.command == "sources"
    assert args.region == "global"

    result = run_registered_command_from_string("status")
    assert result["ok"] is True
    assert result["data"]["total"] == 0

    result = run_registered_params("status", {})
    assert result["ok"] is True
    assert result["data"]["total"] == 0


def test_service_command_registry_is_parser_subset():
    from ode.cli_parser import build_parser
    from ode.service_commands import SERVICE_COMMANDS

    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert set(SERVICE_COMMANDS) <= set(subparsers.choices)


def test_service_command_registry_covers_parser_commands():
    from ode.cli_parser import build_parser
    from ode.service_commands import SERVICE_COMMANDS

    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert set(subparsers.choices) <= set(SERVICE_COMMANDS)


def test_registered_command_parser_preserves_unquoted_windows_paths():
    from ode.service_commands import parse_registered_command

    args = parse_registered_command(
        "lens",
        r"opp-1 --profile C:\foo\profile.json",
    )

    assert args.profile == r"C:\foo\profile.json"


def test_claude_skill_uses_registered_read_only_command(tmp_path, monkeypatch):
    from ode.integrations.claude_skill import handle_skill_command

    monkeypatch.setenv("ODE_ROOT", str(tmp_path))

    payload = json.loads(handle_skill_command("status", ""))
    assert payload["ok"] is True
    assert payload["data"]["total"] == 0


def test_claude_skill_registered_command_reports_argument_errors():
    from ode.integrations.claude_skill import handle_skill_command

    payload = json.loads(handle_skill_command("show", ""))
    assert payload["ok"] is False
    assert "opp_id" in payload["message"]


def test_claude_skill_registered_command_reports_profile_json_errors(tmp_path, monkeypatch):
    from ode.integrations.claude_skill import handle_skill_command

    monkeypatch.setenv("ODE_ROOT", str(tmp_path))

    payload = json.loads(handle_skill_command("lens", "opp-x --profile-json '{bad'"))
    assert payload["ok"] is False
    assert "Invalid JSON for --profile-json" in payload["message"]


def test_cli_pain_rejects_unreachable_grade(tmp_path):
    result = _run_cli(["pain", "--min-grade", "A"], tmp_path)

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_cli_entrypoint_stays_thin():
    source = (ROOT / "ode" / "cli.py").read_text(encoding="utf-8")

    assert "from ode import service" not in source
    assert "add_parser(" not in source
    assert "COMMANDS =" not in source


def test_cli_json_mode_stays_registry_only():
    source = (ROOT / "ode" / "cli_json.py").read_text(encoding="utf-8")

    assert "from ode import service" not in source
    assert "asyncio.run(service." not in source
    assert "dispatch =" not in source


def test_cli_configures_stdio_for_unicode_reports(monkeypatch):
    import ode.cli as cli

    calls = []

    class Stream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(cli.sys, "stdout", Stream())
    monkeypatch.setattr(cli.sys, "stderr", Stream())

    cli.configure_stdio()

    assert calls == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]


def test_store_project_root_prefers_current_checkout(monkeypatch):
    from ode.core import store

    monkeypatch.delenv("ODE_ROOT", raising=False)
    monkeypatch.chdir(ROOT)

    assert store._project_root() == ROOT
