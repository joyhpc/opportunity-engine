"""MCP server for ODE — expose tools via Model Context Protocol.

Phase 3 implementation. Follows hardware-copilot's TOOL_REGISTRARS pattern.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


TOOL_REGISTRARS = (
    # Will be populated in Phase 3
    # register_scan_tools,
    # register_eval_tools,
    # register_portfolio_tools,
)


def setup_tools(target=None):
    """Register all ODE tools on the MCP server."""
    for registrar in TOOL_REGISTRARS:
        registrar(target)


# Placeholder for Phase 3 implementation
def create_mcp_server():
    """Create and configure the MCP server."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.warning("MCP not installed: pip install mcp")
        return None

    mcp = FastMCP("opportunity-engine")
    setup_tools(mcp)
    return mcp
