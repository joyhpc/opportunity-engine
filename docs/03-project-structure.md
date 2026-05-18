# Project Structure

This document defines repository ownership. Its goal is to make it obvious which files are production runtime, which files are contracts, which files are imported material, and which files are generated or experimental.

## Top-Level Ownership

```text
opportunity-engine/
  ode/                 active runtime package
  flows/               declarative business-flow definitions
  schemas/             machine-checkable JSON contracts
  sources/             auditable opportunity source catalog
  examples/            reproducible inputs and golden outputs
  imports/             audited external or historical source material
  prototypes/          experiments; not imported by runtime
  docs/                human-readable docs, templates, generated research artifacts
  tests/               pytest suite
  tools/               repository maintenance and validation scripts
  web/                 optional local browser UI; separate dependencies
  requirements.txt     runtime dependency list
  pyproject.toml       package metadata, script entry, pytest defaults
```

## Runtime Package

```text
ode/
  cli.py               thin CLI entry point
  cli_parser.py        argparse command definitions
  cli_handlers.py      human-readable CLI handlers
  cli_json.py          raw JSON output mode
  cli_io.py            CLI input parsing helpers
  service.py           public async facade over ode/services/
  service_commands.py  shared command registry for CLI JSON, Skill, MCP, future API
  services/            domain service implementations
  core/                dataclasses, repository, scoring adapter, YAML store, artifacts
  engine/              DAG, gates, workers, portfolio logic
  heuristics/          discovery, scoring bridge, DBS, warnings, fit lens, synthesis
  tools/               source adapters, scanners, scoring, sizing, financials, reports
  data/                cache and knowledge infrastructure adapters
  imports/             adapters from top-level imported material into ODE contracts
  integrations/        Claude Skill, MCP, project-tracker bridge
  api/                 reserved package only; no server module
  web/                 reserved package only; no dashboard module
```

## Dependency Direction

Allowed direction:

```text
access surfaces
  -> service_commands
  -> service facade
  -> services
  -> engine / heuristics / tools
  -> core / data
  -> external libraries
```

Rules:

1. `ode/service.py` is the compatibility facade. Do not put large new business logic there.
2. Access surfaces should not call store functions, workers, or heuristics directly when a service function exists.
3. CLI text handlers may format output, but should not own business behavior.
4. JSON mode, Skill, MCP, and any future API should consume `ode/service_commands.py`.
5. Runtime code must not import top-level `imports/` or `prototypes/`.
6. `ode/imports/` may read top-level imported material and convert it into ODE contracts.
7. `ode/api/` and `ode/web/` should remain reserved packages. Optional browser UI code belongs in top-level `web/` and must call ODE through `ode/service_commands.py`.

## Active Boundaries

| Area | Current State | Decision |
|---|---|---|
| `ode/` | Main product package. | Active runtime root. |
| `ode/services/` | Split service implementations behind `ode/service.py`. | Put service behavior here. |
| `ode/service_commands.py` | Registry covers parser commands and labels read-only commands. | Use for machine/agent-facing surfaces. |
| `ode/api/`, `ode/web/` | Packages exist, server stubs were removed. | Keep reserved; do not add empty placeholder modules. |
| `web/` | Optional local browser UI with separate dependencies and default-collected bridge tests. | Keep thin; do not import stores, workers, heuristics, tools, or service implementation modules directly. |
| `imports/opportunity-detector/` | Audited legacy/source material. | Keep isolated; use `ode/imports/detector_integration.py`. |
| `prototypes/storybook/` | Experiment and product-plan area. | Keep out of runtime. |
| `data/` | Runtime state. | Ignored by Git. |
| `docs/rendered_*`, `docs/assets/*` | Generated/research artifacts. | Treat as governed outputs, not architecture truth. |

## Data And Generated Files

Runtime state belongs under:

```text
data/
  opportunities/
  signals/
  competitors/
  evidence/
  alerts/
  reports/
  cache.db
```

These paths are ignored by Git. Generated reports or rendered files outside `data/` need a write plan before creation or overwrite:

```python
from ode.core.artifacts import plan_artifact_write
```

`plan_artifact_write` can return:

- `create`
- `update_generated`
- `version`
- `conflict`
- `blocked`

Use it when producing shareable docs, maps, PDFs, validation plans, or rendered artifacts that could collide with user-authored files.

## Import Promotion Rule

Top-level imported material is not automatically production code.

Promotion path:

1. Identify the useful source file under `imports/`.
2. Build or adapt a tested equivalent under `ode/`.
3. Add tests for the ODE module.
4. Keep the original import material for audit history.
5. If the import contract changes, update the golden output via:

```bash
python tools/validate_import_integration.py --write
```

Normal runtime modules should never reach directly into `imports/opportunity-detector`.

## Prototype Rule

`prototypes/` can be messy. It is a place for experiments, not a dependency root.

Before prototype code becomes runtime:

1. Move the minimal behavior into `ode/`.
2. Add tests under `tests/`.
3. Update docs only after the runtime boundary exists.

## Documentation Rule

Authoritative docs:

- `README.md`
- `ARCHITECTURE.md`
- `docs/00-navigation.md`
- this file
- `docs/04-data-sources.md` for source registry behavior

Research artifacts and generated reports are not architecture truth. If they contain old wording, preserve them as artifacts unless the user asks for a content revision.

## Cleanup Inventory

| Item | Policy |
|---|---|
| `__pycache__/`, `.pytest_cache/`, `*.pyc` | Never track. |
| `data/` entity and report files | Local runtime state; ignored. |
| `.codex_tmp/` | Local working scratch; should not become product state. |
| Office temp files such as `~$*.docx` | Local editor artifacts; should not be tracked. |
| Rendered PDFs/images | Keep only when they are intentional review artifacts. |
| Source diagrams under `docs/assets/` | Keep only with clear document ownership. |

## Verification Commands

```bash
python tools/check_environment.py
python tools/validate_import_integration.py
python -m pytest
python -m ode --json status
```

Optional local Web verification after installing `web/requirements.txt`:

```bash
python tools/check_web_app.py
```

Boundary tests to check after structure changes:

```bash
python -m pytest tests/test_project_structure.py tests/test_service_boundaries.py tests/test_cli_surface.py
```

## Current Deferred Work

- Persistent run ledger is not implemented.
- Packaged API/Web surfaces under `ode/` are not implemented.
- MCP write tools are not implemented.
- Later pipeline stages exist in declarations but do not have dedicated gate evaluators.
