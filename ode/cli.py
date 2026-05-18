"""ODE CLI entry point."""

from __future__ import annotations

import sys

from ode.cli_handlers import run_command
from ode.cli_parser import build_parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to the selected CLI handler."""

    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    run_command(args)


def configure_stdio() -> None:
    """Make CLI output tolerant of Unicode reports on legacy consoles."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
