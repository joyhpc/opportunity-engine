"""Claude Code skill integration — /ode command.

Registers ODE as a Claude Code skill for use in conversations.
"""

from __future__ import annotations


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
    ],
}


def handle_skill_command(command: str, args: str = "") -> str:
    """Handle a /ode skill command from Claude Code.

    This would be called by the Claude Code plugin system.
    Returns the command output as a string.
    """
    import sys
    import shlex
    from io import StringIO
    from ode.cli import main as cli_main

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        sys.argv = ["ode", command] + (shlex.split(args) if args else [])
        cli_main()
        output = sys.stdout.getvalue()
    except SystemExit:
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    return output
