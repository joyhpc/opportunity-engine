"""Run the optional ODE web app with automatic port fallback."""

from __future__ import annotations

import argparse
import socket
from contextlib import closing


def is_port_available(host: str, port: int) -> bool:
    """Return whether a TCP port can be bound on the requested host."""

    if port < 0 or port > 65535:
        return False
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_available_port(host: str, start_port: int, max_tries: int = 50) -> int:
    """Find an available port, preferring start_port and then incrementing."""

    if start_port == 0:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])

    for port in range(start_port, min(65535, start_port + max_tries - 1) + 1):
        if is_port_available(host, port):
            return port
    raise RuntimeError(
        f"No available port found from {start_port} to "
        f"{min(65535, start_port + max_tries - 1)}."
    )


def display_host(host: str) -> str:
    """Return a browser-friendly host for the startup URL."""

    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the optional ODE local web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port; use 0 for any free port.")
    parser.add_argument("--max-tries", type=int, default=50, help="How many sequential ports to try.")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn reload for web development.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    port = find_available_port(args.host, args.port, args.max_tries)
    url = f"http://{display_host(args.host)}:{port}"
    if args.port != 0 and port != args.port:
        print(f"Port {args.port} is busy; using {port}.", flush=True)
    print(f"ODE web app: {url}", flush=True)

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "Missing web dependencies. Install them with: "
            "python -m pip install -r web/requirements.txt"
        ) from exc

    uvicorn.run("web.app:app", host=args.host, port=port, reload=args.reload)


if __name__ == "__main__":
    main()

