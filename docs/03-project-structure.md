# Project Structure

> 这个仓库的整理目标：产品代码、导入素材、原型实验、运行产物各归其位。

## Top-Level Ownership

```text
opportunity-engine/
├── ode/                 # 正式产品包, CLI/service/engine/runtime code
├── flows/               # 可声明的业务流程和阶段定义
├── schemas/             # JSON schema and machine-checkable contracts
├── sources/             # auditable opportunity discovery source catalog
├── examples/            # 可复现输入和 golden outputs
├── imports/             # 外部项目审计素材, not a second active app
├── prototypes/          # 原型和实验代码, not imported by runtime
├── docs/                # 人读文档和设计说明
├── tests/               # pytest suite
├── tools/               # repo maintenance and validation scripts
├── requirements.txt     # runtime/test dependency list used by CI
└── pyproject.toml       # package metadata, CLI entrypoint, pytest defaults
```

## Runtime Package Layers

```text
ode/
├── cli.py               # 命令行入口: parse args and dispatch
├── cli_parser.py        # argparse command definitions
├── cli_handlers.py      # terminal text handlers over service.py
├── cli_json.py          # raw JSON service output mode
├── service.py           # surface-neutral async facade over ode/services/
├── services/            # domain service implementations behind the facade
├── core/                # dataclasses, constants, YAML store
├── engine/              # pipeline DAG, gates, async workers, portfolio logic
├── heuristics/          # explore/bridge/reframe/synthesize, optional reasoning
├── tools/               # domain calculators, scanners, report generation
├── data/                # cache and knowledge infrastructure adapters
├── imports/             # adapters from imported assets into ODE contracts
├── integrations/        # Claude Skill, MCP, project-tracker bridges
├── api/                 # reserved REST surface package; no empty stub module
└── web/                 # reserved dashboard package; no empty stub module
```

The intended dependency direction is:

```text
CLI/API/Skill/Web
    -> parser/handler adapters
        -> service
        -> engine + heuristics
            -> core + tools + data
                -> external libraries
```

`ode/heuristics/fit_lens.py` is the soft personalization layer. It ranks an
opportunity with `Opportunity Score`, `Founder Fit`, and `Discovery Value`, then
classifies it as `Build Now`, `Validate Soon`, `Watch`, `Research`, or `Ignore`.
It should not mutate or kill opportunities.

`ode/heuristics/revenue_cases.py` is the revenue-case verification layer. It
grades proof from A to E, separates revenue from funding/traffic/GMV, and
returns fit-aware next actions without mutating opportunities.

`ode/imports/` is an adapter boundary. It may read from top-level `imports/`,
but normal engine modules should not directly depend on imported repository
material.

## Boundary Rules

1. Active product behavior lives under `ode/`.
2. `imports/` stores audited third-party or legacy source material. Treat it as input data unless code is explicitly promoted into `ode/`.
3. `prototypes/` is allowed to be messy while exploring, but runtime code and tests must not import from it.
4. `examples/` and `schemas/` define reproducible contracts. Golden files should change only with intentional contract updates.
5. Generated user data belongs under `data/` and remains ignored by Git.
6. Python caches, pytest caches, local IDE folders, and prototype outputs stay out of version control.
7. New user-facing behavior should enter through `service.py` first, then be exposed by CLI/API/MCP as thin surfaces.
8. Personal fit is a lens, not an early hard filter. High-discovery wildcard opportunities should remain visible.
9. Revenue cases are reference material, not opportunities. They should become opportunities only after evidence grading and fit analysis.
10. Generated reports, renders, plans, and validation artifacts need a pre-write governance decision. Use `ode.core.artifacts.plan_artifact_write` to avoid overwriting user-authored files or duplicating confusing artifacts.

## Current Cleanup Inventory

| Area | Current State | Decision |
|------|---------------|----------|
| `ode/` | Main product package with clear subpackages | Keep as active runtime root |
| `imports/opportunity-detector/` | Audited source material from legacy repo | Keep isolated; access through `ode/imports/detector_integration.py` |
| `prototypes/storybook/` | Large prototype scripts and product notes | Keep out of runtime; prefer `pipeline_v2.py` for structured tool_use experiments; keep `pipeline.py` as deprecated history only |
| `ode/integrations/mcp_server.py` | MCP access surface | Keep; registers read-only service commands as MCP tools |
| `ode/api/`, `ode/web/` | Reserved access-surface packages | Keep directories only; do not ship empty placeholder modules |
| `.pytest_cache/`, `__pycache__/` | Local runtime artifacts | Ignore and remove locally when cleaning |
| Docs test count | README/navigation drifted from test reality | Keep synced to `python -m pytest` result |

## Refactor Roadmap

### Phase 0 - Repository Hygiene

- Add project metadata and pytest defaults in `pyproject.toml`.
- Add editor rules for UTF-8/LF consistency.
- Clean ignored runtime artifacts locally.
- Keep README, navigation, and structure docs synchronized.

### Phase 1 - Surface Separation

- Split CLI parser construction from command handlers when command count grows again.
- Keep `service.py` as the single API used by CLI, MCP, API, and Claude Skill.
- Add tests for JSON mode and error formatting before touching CLI internals.
- Status: first pass complete. `ode/cli.py` is now a thin entrypoint and
  behavior is covered by `tests/test_cli_surface.py`.
- Status: service implementation is split into `ode/services/*`; `ode/service.py`
  remains the compatibility facade for existing surfaces.

### Phase 2 - Import Promotion

- Convert any useful `imports/opportunity-detector` tool into a tested `ode/tools/` module.
- Preserve the original imported file until parity tests pass.
- Update `examples/import_integration/*.golden.json` only through `tools/validate_import_integration.py --write`.

### Phase 3 - Access Surfaces

- MCP is implemented as a thin adapter over the shared service-command registry.
- API/Web are reserved packages only until contract tests and dependency choices exist.
- Do not duplicate scoring, gate, or persistence logic in access layers.
- Add contract tests before exposing new surfaces.

## Verification Commands

```bash
python tools/check_environment.py
python tools/validate_import_integration.py
python -m pytest
python -m ode status
```
