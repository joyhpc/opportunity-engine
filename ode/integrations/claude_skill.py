"""Claude Code skill integration — /ode command.

Registers ODE as a Claude Code skill for use in conversations.
Calls the service layer directly instead of hijacking sys.argv.
"""

from __future__ import annotations

import asyncio
import shlex

from ode import service

SKILL_DEFINITION = {
    "name": "ode",
    "description": "Opportunity Discovery Engine — scan, evaluate, and report on business opportunities",
    "commands": [
        {
            "name": "scan",
            "description": "Scan for trend signals",
            "usage": "/ode scan --keywords 'AI,machine learning'",
        },
        {
            "name": "eval",
            "description": "Evaluate an opportunity",
            "usage": "/ode eval <opp_id> --depth screen",
        },
        {
            "name": "report",
            "description": "Generate an assessment report",
            "usage": "/ode report <opp_id>",
        },
        {
            "name": "portfolio",
            "description": "View opportunity portfolio",
            "usage": "/ode portfolio",
        },
        {
            "name": "status",
            "description": "Show ODE status",
            "usage": "/ode status",
        },
        {
            "name": "explore",
            "description": "Open-ended opportunity exploration",
            "usage": "/ode explore --hn-top 10",
        },
        {
            "name": "insights",
            "description": "Generate insights for an opportunity",
            "usage": "/ode insights <opp_id>",
        },
    ],
}


def _parse_skill_args(command: str, args_str: str) -> dict:
    """Parse a skill args string into kwargs for the service layer."""
    tokens = shlex.split(args_str) if args_str else []

    if command == "scan":
        kwargs: dict = {}
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
        return kwargs

    if command == "eval":
        kwargs = {}
        if tokens:
            kwargs["opp_id"] = tokens[0]
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
            else:
                i += 1
        return kwargs

    if command == "report":
        kwargs = {}
        if tokens:
            kwargs["opp_id"] = tokens[0]
        i = 1
        while i < len(tokens):
            if tokens[i] == "--stage" and i + 1 < len(tokens):
                kwargs["stage"] = tokens[i + 1]
                i += 2
            else:
                i += 1
        return kwargs

    if command == "insights":
        return {"opp_id": tokens[0]} if tokens else {}

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
        return kwargs

    # status, portfolio — no args
    return {}


_HANDLERS = {
    "scan": service.scan,
    "eval": lambda **kw: service.evaluate(kw.pop("opp_id", ""), **kw),
    "report": lambda **kw: service.generate_report(kw.pop("opp_id", ""), **kw),
    "status": service.get_status,
    "portfolio": service.get_portfolio,
    "insights": lambda **kw: service.get_insights(kw.pop("opp_id", "")),
    "explore": service.explore_signals,
}


def handle_skill_command(command: str, args: str = "") -> str:
    """Handle a /ode skill command from Claude Code.

    Returns the command output as a string (JSON).
    """
    handler = _HANDLERS.get(command)
    if not handler:
        return f'{{"ok": false, "message": "Unknown command: {command}"}}'

    parsed = _parse_skill_args(command, args)

    try:
        result = asyncio.run(handler(**parsed))
    except Exception as e:
        return f'{{"ok": false, "message": "Error: {e}"}}'

    import json
    return json.dumps(result, ensure_ascii=False, default=str)
