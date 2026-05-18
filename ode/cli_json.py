"""JSON output mode for the ODE CLI."""

from __future__ import annotations

import json

from ode.cli_io import CliInputError
from ode.service_commands import is_registered_command, run_registered_args


def run_json_mode(args) -> None:
    """Run a supported command and print the raw service-layer result."""

    if is_registered_command(args.command):
        try:
            result = run_registered_args(args)
        except CliInputError as exc:
            result = {"ok": False, "data": {}, "message": str(exc)}
    else:
        result = {
            "ok": False,
            "data": {},
            "message": f"--json not supported for '{args.command}' yet",
        }

    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
