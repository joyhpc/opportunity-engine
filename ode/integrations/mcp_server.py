"""MCP server for ODE using the shared service-command registry."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ode.service_commands import run_registered_params_async
from ode.services.result import fail

logger = logging.getLogger(__name__)

ToolFn = Callable[..., Any]


async def _run(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return await run_registered_params_async(command, params or {})
    except Exception as exc:
        logger.exception("MCP command failed: %s", command)
        return fail(str(exc))


def _register_tool(target, name: str, description: str, func: ToolFn) -> str:
    if target is None:
        return name
    decorator = target.tool(name=name, description=description)
    decorator(func)
    return name


def register_read_only_service_tools(target=None) -> list[str]:
    """Register read-only ODE service commands as MCP tools."""

    async def ode_status() -> dict[str, Any]:
        return await _run("status")

    async def ode_list() -> dict[str, Any]:
        return await _run("list")

    async def ode_show(opp_id: str) -> dict[str, Any]:
        return await _run("show", {"opp_id": opp_id})

    async def ode_sources(status: str | None = None, region: str | None = None) -> dict[str, Any]:
        return await _run("sources", {"status": status, "region": region})

    async def ode_cases(path: str | None = None,
                        region: str | None = None,
                        min_grade: str | None = None,
                        top: int | None = None,
                        profile: str | None = None,
                        profile_json: str | None = None) -> dict[str, Any]:
        return await _run("cases", {
            "path": path,
            "region": region,
            "min_grade": min_grade,
            "top": top,
            "profile": profile,
            "profile_json": profile_json,
        })

    async def ode_portfolio() -> dict[str, Any]:
        return await _run("portfolio")

    async def ode_compare(ids: str) -> dict[str, Any]:
        return await _run("compare", {"ids": ids})

    async def ode_insights(opp_id: str) -> dict[str, Any]:
        return await _run("insights", {"opp_id": opp_id})

    async def ode_lens(opp_id: str,
                       profile: str | None = None,
                       profile_json: str | None = None) -> dict[str, Any]:
        return await _run("lens", {
            "opp_id": opp_id,
            "profile": profile,
            "profile_json": profile_json,
        })

    specs: list[tuple[str, str, ToolFn]] = [
        ("ode_status", "Show ODE repository runtime status.", ode_status),
        ("ode_list", "List opportunities without mutating state.", ode_list),
        ("ode_show", "Show one opportunity by id or name.", ode_show),
        ("ode_sources", "List configured discovery sources.", ode_sources),
        ("ode_cases", "Analyze revenue-proven reference cases.", ode_cases),
        ("ode_portfolio", "Show portfolio ranking and summary.", ode_portfolio),
        ("ode_compare", "Compare opportunities by comma-separated ids.", ode_compare),
        ("ode_insights", "Generate synthesis and reframe insights for one opportunity.", ode_insights),
        ("ode_lens", "Apply the Founder Fit Lens without mutating the opportunity.", ode_lens),
    ]
    return [
        _register_tool(target, name, description, func)
        for name, description, func in specs
    ]


TOOL_REGISTRARS = (register_read_only_service_tools,)


def setup_tools(target=None) -> list[str]:
    """Register all ODE tools on an MCP-compatible target."""

    registered: list[str] = []
    for registrar in TOOL_REGISTRARS:
        registered.extend(registrar(target))
    return registered


def create_mcp_server():
    """Create and configure the MCP server when the optional MCP package exists."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.warning("MCP not installed: pip install mcp")
        return None

    mcp = FastMCP("opportunity-engine")
    setup_tools(mcp)
    return mcp
