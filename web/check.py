#!/usr/bin/env python3
"""Smoke-test the optional local web app when web dependencies are installed."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_DEPS = ("fastapi", "uvicorn", "httpx")


def main() -> int:
    sys.path.insert(0, str(ROOT))

    missing = [name for name in OPTIONAL_DEPS if importlib.util.find_spec(name) is None]
    if missing:
        print(f"[FAIL] Missing optional web dependencies: {', '.join(missing)}", file=sys.stderr)
        print("[INFO] Install them with: python -m pip install -r web/requirements.txt", file=sys.stderr)
        return 2

    from fastapi.testclient import TestClient
    from web.app import app

    previous_ode_root = os.environ.get("ODE_ROOT")
    with tempfile.TemporaryDirectory(prefix="ode-web-smoke-") as data_root:
        os.environ["ODE_ROOT"] = data_root
        try:
            with TestClient(app) as client:
                _assert_ok(client.get("/api/health").json(), "health")
                commands = _assert_ok(client.get("/api/commands").json(), "commands")
                _assert_has_status_command(commands)
                status = _assert_ok(
                    client.post("/api/commands/status", json={"params": {}}).json(),
                    "status command",
                )
                if status.get("total") != 0:
                    raise AssertionError("status command should use an empty temporary ODE_ROOT")
        finally:
            if previous_ode_root is None:
                os.environ.pop("ODE_ROOT", None)
            else:
                os.environ["ODE_ROOT"] = previous_ode_root

    print("[OK] optional web app smoke passed")
    return 0


def _assert_ok(payload: dict[str, Any], label: str) -> dict[str, Any]:
    if payload.get("ok") is not True:
        raise AssertionError(f"{label} did not return ok=true: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise AssertionError(f"{label} did not return object data: {payload}")
    print(f"[OK] {label}")
    return data


def _assert_has_status_command(data: dict[str, Any]) -> None:
    commands = data.get("commands")
    if not isinstance(commands, list):
        raise AssertionError(f"commands payload is not a list: {data}")
    status = next((item for item in commands if item.get("name") == "status"), None)
    if status is None:
        raise AssertionError("commands catalog does not include status")
    if status.get("read_only") is not True:
        raise AssertionError("status command should be marked read_only")


if __name__ == "__main__":
    raise SystemExit(main())
