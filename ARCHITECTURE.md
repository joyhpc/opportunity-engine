# ODE Architecture

This document describes the architecture that exists in the current repository. It is intentionally code-first: when it disagrees with old planning notes, this file wins.

## Design Principles

1. Keep access surfaces thin. CLI, JSON mode, Skill, MCP, and any future API should delegate to shared service commands instead of duplicating business logic.
2. Keep `ode/service.py` as a stable facade. Move implementation into `ode/services/*` so the historical import path remains usable.
3. Persist business state in plain YAML entities. The operator should be able to inspect and diff opportunities, signals, warnings, and reports.
4. Separate discovery from judgment. `explore`, `pain`, `cases`, and `daily` create or rank candidates; gates and diagnostics decide how much confidence to give them.
5. Treat revenue proof, trend proof, pain proof, and founder fit as different signals. Do not let launch attention or funding masquerade as payment evidence.
6. Treat generated artifacts as governed outputs. Do not overwrite ambiguous user-authored files without an explicit decision.

## Layer Diagram

```text
User / Agent / MCP client
        |
        v
Access surfaces
  ode/cli.py
  ode/cli_json.py
  ode/cli_handlers.py
  ode/integrations/claude_skill.py
  ode/integrations/mcp_server.py
  web/app.py, web/bridge.py (optional local UI)
        |
        v
Shared command registry
  ode/service_commands.py
        |
        v
Public service facade
  ode/service.py
        |
        v
Domain service implementations
  ode/services/opportunities.py
  ode/services/discovery.py
  ode/services/insights.py
  ode/services/warnings.py
  ode/services/dbs.py
        |
        v
Engine, heuristics, tools
  ode/engine/*
  ode/heuristics/*
  ode/tools/*
        |
        v
Core and infrastructure
  ode/core/models.py
  ode/core/repository.py
  ode/core/store.py
  ode/core/scoring.py
  ode/core/artifacts.py
  ode/data/cache.py
```

## Access Surfaces

| Surface | Code | Contract |
|---|---|---|
| CLI text mode | `ode/cli.py`, `ode/cli_parser.py`, `ode/cli_handlers.py` | Human-readable output. Should remain presentation-only. |
| CLI JSON mode | `ode/cli_json.py` | Prints the raw service result envelope: `{"ok": bool, "data": dict, "message": str}`. |
| Claude Skill | `ode/integrations/claude_skill.py` | `/ode` command handler; registered commands go through `service_commands`. |
| MCP | `ode/integrations/mcp_server.py` | Currently read-only service tools: status, list, show, sources, cases, portfolio, compare, insights, lens. |
| Local Web UI | `web/app.py`, `web/bridge.py` | Optional browser UI outside the runtime package. It calls `service_commands` only. |
| Package API/Web | `ode/api/`, `ode/web/` | Reserved package directories. There is no packaged server or dashboard inside `ode`. |

All access surfaces should converge on `ode/service_commands.py`. That registry knows the command name, read-only flag, default parameter conversion, and async executor.

## Service Layer

`ode/service.py` re-exports and wraps the implementation functions so existing code can continue importing `ode.service`.

Implementation modules:

| Module | Responsibilities |
|---|---|
| `ode/services/opportunities.py` | Create, list, show, scan, evaluate, report, status, portfolio, compare. |
| `ode/services/discovery.py` | Source catalog, revenue cases, open exploration, pain listening. |
| `ode/services/insights.py` | Synthesis, founder-fit lens, experiments, actuals, gate refresh. |
| `ode/services/warnings.py` | Daily warning review, initial warning bootstrap, watchlist persistence. |
| `ode/services/dbs.py` | Goal clarification, concept deconstruction, business diagnosis, DBS session, AI hardware workflow. |
| `ode/services/result.py` | Result envelope helpers `ok()` and `fail()`. |

Service functions are async and return the same envelope shape:

```json
{
  "ok": true,
  "data": {},
  "message": ""
}
```

Blocking fetches and CPU-ish sync work should be run through `ode/core/async_utils.py::run_blocking`, not raw `run_in_executor` calls spread through the codebase.

## Engine Layer

The engine is small and explicit.

| Module | Role |
|---|---|
| `ode/engine/workers.py` | Async worker functions: `scan_worker`, `eval_worker`, `report_worker`, plus convenience orchestration. Workers are not separate processes. |
| `ode/engine/gate.py` | Gate evaluators for `SENSE`, `SCREEN`, and `ANALYZE`. |
| `ode/engine/pipeline.py` | Seven-stage DAG declaration and Kahn topological scheduling helper. |
| `ode/engine/portfolio.py` | Multi-opportunity summaries and comparison tables. |

The declared pipeline stages are:

```text
SENSE -> SCREEN -> ANALYZE -> VALIDATE -> PLAN -> LAUNCH -> MONITOR
```

Only the first three stages have concrete gate evaluators today.

## Gate Logic

| Gate | Inputs | Verdict Rule |
|---|---|---|
| `SENSE` | signals | Strong signals count as 1. Medium signals count as 0.5. Effective count `>= 3` is `GO`; `>= 1.8` is `MAYBE`; lower is `KILL`. |
| `SCREEN` | scoring result | Redlines force `KILL`. Otherwise weighted percentage `>= 70` is `GO`; `50-69` is `MAYBE`; `< 50` is `KILL`. |
| `ANALYZE` | financials, regulatory facts | `NPV > 0` and no P0 regulatory risk is `GO`; positive NPV with P0 risk is `MAYBE`; otherwise `KILL`. |
| Other stages | stage name only | Default pass-through returns `GO` with "No gate defined". |

`refresh-gate` can append a new gate log entry when the verdict changes. For `SCREEN`, passed experiments can upgrade a borderline `MAYBE` to `GO` when the score is high enough.

## Data Flow

### Create

```text
CLI/JSON/Skill
  -> service_commands._create
  -> service.create_opportunity
  -> services.opportunities.create_opportunity
  -> OpportunityRepository.find_duplicate
  -> core.store.save_opportunity
  -> data/opportunities/<id>.yaml
```

Duplicate checks compare exact opportunity name and keyword overlap.

### Scan

```text
scan command
  -> services.opportunities.scan
  -> engine.workers.scan_worker
  -> tools.trend_scanner.scan_all
  -> tools.source_dispatch / source adapters
  -> Signal YAML files
  -> opportunity.signals updated
  -> SENSE gate
```

`scan_worker` preserves historical signal ids by extending `opportunity.signals` instead of replacing them.

### Evaluate

```text
eval command
  -> services.opportunities.evaluate
  -> engine.workers.eval_worker
  -> optional market_sizer / financial_model
  -> bridge.infer_scores if no --scores and signals exist
  -> core.scoring.OpportunityScorer
  -> SCREEN or ANALYZE gate
  -> opportunity YAML updated
```

Manual `--scores` can override or bypass bridge inference.

### Report

```text
report command
  -> services.opportunities.generate_report
  -> engine.workers.report_worker
  -> tools.report_generator
  -> heuristics.synthesize appended when useful
  -> latest saved DBS diagnostic appended when present
  -> data/reports/<opp_id>_<stage>.md
```

### Discovery And Warning

```text
cases -> revenue_cases analyzer -> evidence grades and fit
pain -> source_dispatch -> pain_listener -> validation queues
explore -> source fetch -> cluster -> hypotheses
daily -> pain + cases + optional explore + portfolio -> watchlist + daily report
```

Daily state is stored under `data/alerts/`, and daily reports under `data/reports/daily/`.

### DBS Diagnostics

```text
dbs/clarify/diagnose/deconstruct
  -> services.dbs
  -> heuristics.dbs
  -> optional append_dbs_diagnostic
  -> opportunity.diagnostics[]
```

DBS outputs are advisory in v1. They are displayed in `show`, included in `insights`, and appended to generated reports when saved.

## Core Data Model

The primary dataclasses live in `ode/core/models.py`.

| Entity | Stored Under | Notes |
|---|---|---|
| `Opportunity` | `data/opportunities/` | Stage, status, scores, market, financials, regulatory notes, linked signal ids, gate log, experiments, diagnostics. |
| `Signal` | `data/signals/` | Source, keyword, title, momentum, strength, raw data, URL, opportunity id. |
| `Competitor` | `data/competitors/` | Landscape fields and opportunity id. |
| `Evidence` | `data/evidence/` | Source URL, structured data, confidence, opportunity id. |
| `WorkerResult` | returned, not persisted by default | Worker status, scores, artifacts, next action, message, data. |

YAML I/O is implemented by `ode/core/store.py`. `ode/core/repository.py` is a small boundary used by service code so duplicate detection and lookup behavior stay centralized.

## Source Registry

The catalog is `sources/opportunity_sources.yaml`. Runtime dispatch is implemented by:

- `ode/tools/source_registry.py`
- `ode/tools/source_dispatch.py`
- adapters under `ode/tools/sources/`

Important distinction:

- `status: active` means a source has a runtime adapter and declared context.
- `status: optional` means it needs extra dependency or input before it can run.
- `status: manual` means the operator may store curated local signals.
- `status: planned` means it is only a coverage target.
- `used_by_scan_workers` specifically means the source belongs to the `scan_worker` context.

Current contexts:

| Context | Sources |
|---|---|
| `scan_worker` | `hackernews_topstories`, `reddit_hot_rss`, optional `google_trends` |
| `explore` | `hackernews_topstories`, `reddit_hot_rss`, optional `google_trends` |
| `pain_listener` | `hackernews_topstories`, `reddit_hot_rss`, `producthunt_feed` |

## Scoring

`ode/tools/opportunity_scorer.py` owns the scorecard. `ode/core/scoring.py` adapts scorer output into `Opportunity.scores`.

Stored scores include:

- dimension averages by human-readable dimension name;
- `_weighted_pct`;
- `_scoring_details`.

The top-level dimensions are:

1. Market Attractiveness
2. Competitive Landscape
3. Capability Fit
4. Economic Viability
5. Validation Strength
6. AI-Native Potential

`ode/heuristics/bridge.py` can infer flat score inputs from signals, market data, and financial data when `eval` receives no explicit `--scores`.

## Heuristics

Heuristics are deliberately decoupled from the engine. They can be used through services or reports without becoming hidden stage transitions.

| Module | Main Entry | Behavior |
|---|---|---|
| `explore.py` | `services.discovery.explore_signals` | Open-ended signal clustering and hypothesis generation. |
| `pain_listener.py` | `services.discovery.listen_pains` | C/D/E pain evidence grading, downranking launch/success stories, validation queues. |
| `revenue_cases.py` | `services.discovery.analyze_revenue_cases` | A-E revenue evidence grading, fit, quiet-money and verification steps. |
| `daily_warning.py` | `services.warnings.run_daily_review` | Merges pain, cases, explore, and portfolio into watchlist updates. |
| `fit_lens.py` | `services.insights.apply_lens` | Soft founder-fit recommendation. It does not mutate opportunities. |
| `synthesize.py` | `services.insights.get_insights`, report worker | Contradiction and blind-spot detection. |
| `reframe.py` | `services.insights.get_insights` | Pivot suggestions when stored weighted score is below 70. |
| `dbs.py` | `services.dbs.*` | Deterministic commercial diagnosis, saved advisory records, copyability checks. |
| `ai_hardware_workflow.py` | `services.dbs.build_ai_hardware_workflow` | Map-first hardware opportunity workflow contract. |

## Imports And Prototypes

Top-level `imports/` contains audited external or historical material. It is not an active second app.

`ode/imports/detector_integration.py` is the adapter that maps imported `opportunity-detector` assets into ODE's seven-stage import contract.

Top-level `prototypes/` contains experiments. Runtime code must not import from it.

Boundary tests enforce both rules.

## Artifact Governance

`ode/core/artifacts.py` provides `plan_artifact_write`. It classifies generated-file writes as:

- `create`
- `update_generated`
- `version`
- `conflict`
- `blocked`

Use it before creating reports, maps, rendered documents, validation scripts, or other generated artifacts outside the normal `data/reports/` worker path.

## Testing Contract

Recommended verification:

```bash
python tools/check_environment.py
python tools/validate_import_integration.py
python -m pytest
```

High-value boundary tests:

- `tests/test_cli_surface.py`: parser commands, JSON mode, service registry coverage, Skill behavior.
- `tests/test_service_boundaries.py`: service facade split, repository/scorer boundaries, MCP read-only tools.
- `tests/test_project_structure.py`: runtime package boundaries and artifact governance.
- `tests/test_source_registry.py`: source catalog, context dispatch, failure notes.
- `tests/test_opportunity_scan_quality.py`: generated opportunity scan quality contract.

## Known Deferred Work

- No REST/API server.
- No web dashboard.
- No persistent run ledger yet.
- MCP exposes only read-only tools.
- `VALIDATE`, `PLAN`, `LAUNCH`, and `MONITOR` are declared stages without dedicated gate evaluators.
- Planned source registry entries are not scanned until adapters and tests are added.
