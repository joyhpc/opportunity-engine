"""Claude Code skill integration — /ode command.

Registers ODE as a Claude Code skill for use in conversations.
Uses the CLI argparse parser to avoid duplicating argument parsing logic.
"""

from __future__ import annotations

import asyncio
import json

from ode import service
from ode.cli_io import CliInputError
from ode.service_commands import (
    is_registered_command,
    run_registered_command_from_string,
    split_command_args,
)

SKILL_DEFINITION = {
    "name": "ode",
    "description": "Opportunity Discovery Engine — scan, evaluate, and report on business opportunities",
    "commands": [
        {"name": "scan", "description": "Scan for trend signals",
         "usage": "/ode scan --keywords 'AI,machine learning'"},
        {"name": "list", "description": "List opportunities",
         "usage": "/ode list"},
        {"name": "sources", "description": "List configured opportunity sources",
         "usage": "/ode sources --region global"},
        {"name": "cases", "description": "Analyze revenue-proven cases",
         "usage": "/ode cases --region china --min-grade B"},
        {"name": "show", "description": "Show an opportunity",
         "usage": "/ode show <opp_id>"},
        {"name": "eval", "description": "Evaluate an opportunity",
         "usage": "/ode eval <opp_id> --depth screen"},
        {"name": "report", "description": "Generate an assessment report",
         "usage": "/ode report <opp_id>"},
        {"name": "portfolio", "description": "View opportunity portfolio",
         "usage": "/ode portfolio"},
        {"name": "compare", "description": "Compare opportunities",
         "usage": "/ode compare opp-1,opp-2"},
        {"name": "status", "description": "Show ODE status",
         "usage": "/ode status"},
        {"name": "explore", "description": "Open-ended opportunity exploration",
         "usage": "/ode explore --hn-top 10"},
        {"name": "insights", "description": "Generate insights for an opportunity",
         "usage": "/ode insights <opp_id>"},
        {"name": "lens", "description": "Apply Founder Fit Lens",
         "usage": "/ode lens <opp_id> --profile examples/profiles/open_founder_profile.json"},
        {"name": "experiment", "description": "Record a prototype iteration",
         "usage": "/ode experiment <opp_id> --version v1 --outcome pass"},
        {"name": "record-actuals", "description": "Record actual financial data",
         "usage": "/ode record-actuals <opp_id> --cogs 0.25"},
        {"name": "refresh-gate", "description": "Re-evaluate gate with current state",
         "usage": "/ode refresh-gate <opp_id>"},
    ],
}


def _parse_and_dispatch(command: str, args_str: str) -> dict:
    """Parse args using CLI argparse and dispatch to service layer."""

    if is_registered_command(command):
        return run_registered_command_from_string(command, args_str)

    tokens = split_command_args(args_str)

    # Map command + args to service calls directly
    if command == "scan":
        kwargs = {}
        i = 0
        while i < len(tokens):
            if tokens[i] == "--keywords" and i + 1 < len(tokens):
                kwargs["keywords"] = [k.strip() for k in tokens[i + 1].split(",")]
                i += 2
            elif tokens[i] == "--domain" and i + 1 < len(tokens):
                kwargs["domain"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--opp-id" and i + 1 < len(tokens):
                kwargs["opp_id"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--hn-top" and i + 1 < len(tokens):
                kwargs["hn_top"] = int(tokens[i + 1])
                i += 2
            elif tokens[i] == "--reddit" and i + 1 < len(tokens):
                kwargs["subreddits"] = [s.strip() for s in tokens[i + 1].split(",")]
                i += 2
            else:
                i += 1
        return asyncio.run(service.scan(**kwargs))

    if command == "eval":
        opp_id = tokens[0] if tokens else ""
        kwargs = {}
        i = 1
        while i < len(tokens):
            if tokens[i] == "--depth" and i + 1 < len(tokens):
                kwargs["depth"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--tam" and i + 1 < len(tokens):
                kwargs["tam"] = float(tokens[i + 1])
                i += 2
            elif tokens[i] == "--arpu" and i + 1 < len(tokens):
                kwargs["arpu"] = float(tokens[i + 1])
                i += 2
            elif tokens[i] == "--scores" and i + 1 < len(tokens):
                kwargs["scores"] = json.loads(tokens[i + 1])
                i += 2
            else:
                i += 1
        return asyncio.run(service.evaluate(opp_id, **kwargs))

    if command == "report":
        opp_id = tokens[0] if tokens else ""
        kwargs = {}
        i = 1
        while i < len(tokens):
            if tokens[i] == "--stage" and i + 1 < len(tokens):
                kwargs["stage"] = tokens[i + 1]
                i += 2
            else:
                i += 1
        return asyncio.run(service.generate_report(opp_id, **kwargs))

    if command == "explore":
        kwargs = {}
        i = 0
        while i < len(tokens):
            if tokens[i] == "--hn-top" and i + 1 < len(tokens):
                kwargs["hn_top"] = int(tokens[i + 1])
                i += 2
            elif tokens[i] == "--keywords" and i + 1 < len(tokens):
                kwargs["keywords"] = [k.strip() for k in tokens[i + 1].split(",")]
                i += 2
            elif tokens[i] == "--reddit" and i + 1 < len(tokens):
                kwargs["subreddits"] = [s.strip() for s in tokens[i + 1].split(",")]
                i += 2
            else:
                i += 1
        return asyncio.run(service.explore_signals(**kwargs))

    if command == "experiment":
        opp_id = tokens[0] if tokens else ""
        kwargs = {}
        i = 1
        while i < len(tokens):
            if tokens[i] == "--version" and i + 1 < len(tokens):
                kwargs["version"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--cogs" and i + 1 < len(tokens):
                kwargs["cogs"] = float(tokens[i + 1])
                i += 2
            elif tokens[i] == "--outcome" and i + 1 < len(tokens):
                kwargs["outcome"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--result" and i + 1 < len(tokens):
                kwargs["result"] = tokens[i + 1]
                i += 2
            elif tokens[i] == "--description" and i + 1 < len(tokens):
                kwargs["description"] = tokens[i + 1]
                i += 2
            else:
                i += 1
        return asyncio.run(service.add_experiment(opp_id, **kwargs))

    if command == "record-actuals":
        opp_id = tokens[0] if tokens else ""
        kwargs = {}
        i = 1
        while i < len(tokens):
            if tokens[i] == "--cogs" and i + 1 < len(tokens):
                kwargs["cogs"] = float(tokens[i + 1])
                i += 2
            elif tokens[i] == "--arpu" and i + 1 < len(tokens):
                kwargs["arpu"] = float(tokens[i + 1])
                i += 2
            else:
                i += 1
        return asyncio.run(service.record_actuals(opp_id, **kwargs))

    if command == "refresh-gate":
        opp_id = tokens[0] if tokens else ""
        return asyncio.run(service.refresh_gate(opp_id))

    return {"ok": False, "data": {}, "message": f"Unknown command: {command}"}


def handle_skill_command(command: str, args: str = "") -> str:
    """Handle a /ode skill command from Claude Code.

    Returns the command output as a string (JSON).
    """
    try:
        result = _parse_and_dispatch(command, args)
    except CliInputError as e:
        result = {"ok": False, "data": {}, "message": str(e)}
    except Exception as e:
        result = {"ok": False, "data": {}, "message": f"Error: {e}"}

    return json.dumps(result, ensure_ascii=False, default=str)
