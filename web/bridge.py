"""Thin bridge from the optional web app to ODE service commands."""

from __future__ import annotations

import logging
from typing import Any

from ode.service_commands import SERVICE_COMMANDS, run_registered_params_async


logger = logging.getLogger(__name__)


def _fail(message: str) -> dict[str, Any]:
    return {"ok": False, "data": {}, "message": message}


def command_catalog() -> list[dict[str, Any]]:
    """Return command metadata safe for a browser UI."""

    return [
        {
            "name": spec.name,
            "description": spec.description,
            "read_only": spec.read_only,
        }
        for spec in sorted(SERVICE_COMMANDS.values(), key=lambda item: item.name)
    ]


async def run_command(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a registered ODE command and return its service envelope."""

    if params is not None and not isinstance(params, dict):
        return _fail("Request field 'params' must be a JSON object.")

    try:
        return await run_registered_params_async(command, params or {})
    except Exception as exc:
        logger.exception("Web command failed: %s", command)
        return _fail(str(exc))
