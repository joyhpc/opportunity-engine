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
        "portfolio",
        "compare",
        "explore",
        "insights",
        "experiment",
        "record-actuals",
        "refresh-gate",
    }
    assert expected <= set(subparsers[0].choices)


def test_cli_entrypoint_stays_thin():
    source = (ROOT / "ode" / "cli.py").read_text(encoding="utf-8")

    assert "from ode import service" not in source
    assert "add_parser(" not in source
    assert "COMMANDS =" not in source
