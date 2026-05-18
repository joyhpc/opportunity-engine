# ODE Local Web

This is an optional, pluggable local web app for Opportunity Discovery Engine.
It lives entirely under `web/` and only calls existing ODE service commands.

## Install

```powershell
python -m pip install -r web/requirements.txt
```

## Run

```powershell
python -m web.run
```

The runner prefers `127.0.0.1:8000`. If that port is busy, it automatically
tries the next ports and prints the actual URL.

Options:

```powershell
python -m web.run --port 8010
python -m web.run --port 0
python -m web.run --host 0.0.0.0
```

The default `127.0.0.1` bind is recommended. `/api/commands/{command}` exposes
every registered command — including write commands like `create`, `scan`, and
`daily` — with no authentication, so `--host 0.0.0.0` makes those reachable
from anyone on the local network.

## Verify

After installing `web/requirements.txt`, run:

```powershell
python -m web.check
```

The smoke check imports the optional dependencies, exercises `/api/health`,
loads the command catalog, and runs the `status` command against a temporary
`ODE_ROOT`.

## Test

The extension ships its own tests under `web/tests/`. They are not part of the
repository's default `pytest` run — run them explicitly:

```powershell
python -m pytest web/tests
```

## API

Run a registered ODE command:

```http
POST /api/commands/status
Content-Type: application/json

{"params": {}}
```

All command responses preserve the service envelope:

```json
{"ok": true, "data": {}, "message": ""}
```

## Reused Core Interfaces

- `ode.service_commands.SERVICE_COMMANDS`
- `ode.service_commands.run_registered_params_async`

The web layer does not import stores, workers, heuristics, or tools directly.

## Remove

```powershell
Remove-Item -Recurse -Force .\web
```

Because no existing project files are modified, deleting `web/` restores the
project to its previous behavior.
