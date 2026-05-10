"""ODE CLI entry point."""

from __future__ import annotations

from ode.cli_handlers import run_command
from ode.cli_parser import build_parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to the selected CLI handler."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    run_command(args)


if __name__ == "__main__":
    main()
