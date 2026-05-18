# ODE Navigation

This is the documentation entry point. Use it to decide which document to trust for which question.

## Read Order

1. [README](../README.md): project purpose, commands, and current operational truth.
2. [ARCHITECTURE](../ARCHITECTURE.md): runtime layers, data flow, service boundaries, gates, and deferred work.
3. [Project Structure](03-project-structure.md): repository ownership rules and cleanup policy.
4. [Data Sources](04-data-sources.md): source registry truth and what is actually scanned.
5. Topic docs below only after the core architecture is clear.

## Documentation Reliability Map

| Document | Status | Use It For | Do Not Use It For |
|---|---|---|---|
| [README](../README.md) | authoritative | Quick start, command list, top-level truth. | Detailed internals. |
| [ARCHITECTURE](../ARCHITECTURE.md) | authoritative | Runtime architecture, service flow, gates, storage. | Product research conclusions. |
| [00-navigation](00-navigation.md) | authoritative | Finding the right document and source file. | Replacing code inspection. |
| [01-heuristic-design](01-heuristic-design.md) | maintained | Heuristic module intent and module boundaries. | Exact scoring constants. |
| [02-ai-storybook-product-plan](02-ai-storybook-product-plan.md) | research artifact | Historical product-plan material for the storybook prototype. | ODE runtime architecture or current business rules. |
| [03-project-structure](03-project-structure.md) | authoritative | Repo boundaries, generated data policy, import/prototype rules. | API behavior. |
| [04-data-sources](04-data-sources.md) | authoritative | Source registry, runtime contexts, source promotion rules. | Claiming full internet or platform coverage. |
| [05-revenue-cases](05-revenue-cases.md) | maintained | Revenue evidence grading and warning gates. | Treating cases as opportunities automatically. |
| [06-dbs-lens](06-dbs-lens.md) | maintained | DBS Lens behavior, license boundary, generated-artifact rule. | Original dbskill prompt or knowledge-base content. |
| [07-agent-runtime-optimization](07-agent-runtime-optimization.md) | roadmap | Future runtime improvements and completed registry work. | Current shipped guarantees. |
| [08-ai-hardware-dbs-workflow](08-ai-hardware-dbs-workflow.md) | maintained | AI hardware scan workflow contract. | General ODE architecture. |
| [09-opportunity-scan-quality-contract](09-opportunity-scan-quality-contract.md) | maintained | Quality bar for generated opportunity reports. | Runtime source-code boundaries. |
| [import-integration](import-integration.md) | maintained | `imports/opportunity-detector` integration contract. | Running the active ODE workflow directly. |
| [opportunity-scan-template](opportunity-scan-template.md) | template | New generated opportunity scan reports. | Runtime code behavior. |
| `*.docx`, rendered PDFs, assets | generated/research artifacts | Human review or presentation outputs. | Source of truth for code behavior. |

## Quick Commands

```bash
python tools/check_environment.py
python tools/validate_import_integration.py
python -m pytest
python -m ode status
```

Discovery:

```bash
python -m ode sources --region global
python -m ode sources --region china
python -m ode cases --region china --min-grade B
python -m ode pain --reddit "SaaS,SideProject,microsaas,webdev" --hn-top 50 --min-grade D
python -m ode explore --hn-top 50
```

Opportunity flow:

```bash
python -m ode create --name "X" --domain "Y" --keywords "a,b,c"
python -m ode scan --opp-id <opp_id> --hn-top 30 --reddit "startup,SaaS"
python -m ode eval <opp_id> --scores "{\"tam_size\": 8, \"growth\": 7, \"pain_evidence\": 6}"
python -m ode insights <opp_id>
python -m ode lens <opp_id> --profile examples/profiles/open_founder_profile.json
python -m ode report <opp_id> --stage screen --print
```

Agent and automation-friendly output:

```bash
python -m ode --json status
python -m ode --json sources --region global
python -m ode --json show <opp_id>
```

## Source Code Map

### Access Layer

| Module | Path | Description |
|---|---|---|
| CLI entry | [`ode/cli.py`](../ode/cli.py) | Thin entry point. Configures UTF-8 stdio and delegates to parser/handlers/JSON mode. |
| Parser | [`ode/cli_parser.py`](../ode/cli_parser.py) | Canonical argparse command definitions. |
| Text handlers | [`ode/cli_handlers.py`](../ode/cli_handlers.py) | Human-readable command output. |
| JSON mode | [`ode/cli_json.py`](../ode/cli_json.py) | Raw service envelopes for machine consumers. |
| Command registry | [`ode/service_commands.py`](../ode/service_commands.py) | Shared registry for JSON, Skill, MCP, and future API adapters. |
| Claude Skill | [`ode/integrations/claude_skill.py`](../ode/integrations/claude_skill.py) | `/ode` command integration. |
| MCP | [`ode/integrations/mcp_server.py`](../ode/integrations/mcp_server.py) | Read-only service tools. |
| project-tracker bridge | [`ode/integrations/pt_bridge.py`](../ode/integrations/pt_bridge.py) | Optional graduation bridge. |

### Service Layer

| Module | Description |
|---|---|
| [`ode/service.py`](../ode/service.py) | Public async facade; keep imports stable. |
| [`ode/services/opportunities.py`](../ode/services/opportunities.py) | CRUD, scan, eval, report, status, portfolio, compare. |
| [`ode/services/discovery.py`](../ode/services/discovery.py) | Sources, cases, explore, pain listener. |
| [`ode/services/insights.py`](../ode/services/insights.py) | Insights, lens, experiments, actuals, gate refresh. |
| [`ode/services/warnings.py`](../ode/services/warnings.py) | Daily warning review and initial alert bootstrap. |
| [`ode/services/dbs.py`](../ode/services/dbs.py) | DBS Lens and AI hardware workflow services. |

### Engine Core

| Module | Description |
|---|---|
| [`ode/engine/workers.py`](../ode/engine/workers.py) | `scan_worker`, `eval_worker`, `report_worker`; async functions, not separate processes. |
| [`ode/engine/gate.py`](../ode/engine/gate.py) | Gate logic for `SENSE`, `SCREEN`, `ANALYZE`. |
| [`ode/engine/pipeline.py`](../ode/engine/pipeline.py) | Seven-stage DAG declaration and topological helper. |
| [`ode/engine/portfolio.py`](../ode/engine/portfolio.py) | Portfolio summary and comparison formatting. |

### Core Infrastructure

| Module | Description |
|---|---|
| [`ode/core/models.py`](../ode/core/models.py) | `Opportunity`, `Signal`, `Competitor`, `Evidence`, `WorkerResult`. |
| [`ode/core/repository.py`](../ode/core/repository.py) | Service-facing repository boundary and duplicate detection. |
| [`ode/core/store.py`](../ode/core/store.py) | YAML entity persistence and data-root resolution. |
| [`ode/core/scoring.py`](../ode/core/scoring.py) | Adapter from scorer output to `Opportunity.scores`. |
| [`ode/core/artifacts.py`](../ode/core/artifacts.py) | Generated-artifact write planning. |
| [`ode/core/async_utils.py`](../ode/core/async_utils.py) | Shared adapter for blocking work. |
| [`ode/data/cache.py`](../ode/data/cache.py) | SQLite TTL cache. |
| [`ode/data/knowledge.py`](../ode/data/knowledge.py) | BM25-style knowledge adapter. |

### Heuristics

| Module | Trigger | Description |
|---|---|---|
| [`ode/heuristics/explore.py`](../ode/heuristics/explore.py) | `ode explore` | Signal clustering and hypothesis generation. |
| [`ode/heuristics/bridge.py`](../ode/heuristics/bridge.py) | `ode eval` without `--scores` | Auto-infers initial score inputs. |
| [`ode/heuristics/pain_listener.py`](../ode/heuristics/pain_listener.py) | `ode pain`, `ode daily` | C/D/E pain evidence grading and validation queues. |
| [`ode/heuristics/revenue_cases.py`](../ode/heuristics/revenue_cases.py) | `ode cases` | A-E revenue evidence grading and fit analysis. |
| [`ode/heuristics/daily_warning.py`](../ode/heuristics/daily_warning.py) | `ode daily`, `ode init-alerts` | Watchlist and alert classification. |
| [`ode/heuristics/fit_lens.py`](../ode/heuristics/fit_lens.py) | `ode lens` | Soft founder-fit recommendation. |
| [`ode/heuristics/synthesize.py`](../ode/heuristics/synthesize.py) | `ode insights`, `ode report` | Contradiction and blind-spot checks. |
| [`ode/heuristics/reframe.py`](../ode/heuristics/reframe.py) | `ode insights` | Pivot suggestions for low-scoring opportunities. |
| [`ode/heuristics/dbs.py`](../ode/heuristics/dbs.py) | `ode dbs`, `clarify`, `diagnose`, `deconstruct` | Deterministic commercial diagnosis. |
| [`ode/heuristics/ai_hardware_workflow.py`](../ode/heuristics/ai_hardware_workflow.py) | `ode ai-hardware` | Map-first AI hardware workflow contract. |

### Tools And Sources

| Module | Description |
|---|---|
| [`ode/tools/source_registry.py`](../ode/tools/source_registry.py) | Loads and validates `sources/opportunity_sources.yaml`. |
| [`ode/tools/source_dispatch.py`](../ode/tools/source_dispatch.py) | Calls source adapters by runtime context. |
| [`ode/tools/sources/`](../ode/tools/sources) | HN, Reddit, Product Hunt, Google Trends adapters. |
| [`ode/tools/trend_scanner.py`](../ode/tools/trend_scanner.py) | Compatibility aggregation over runtime scan sources. |
| [`ode/tools/opportunity_scorer.py`](../ode/tools/opportunity_scorer.py) | Weighted scorecard and redline checks. |
| [`ode/tools/market_sizer.py`](../ode/tools/market_sizer.py) | TAM/SAM/SOM estimates. |
| [`ode/tools/financial_model.py`](../ode/tools/financial_model.py) | Unit economics, projections, NPV. |
| [`ode/tools/report_generator.py`](../ode/tools/report_generator.py) | Markdown opportunity reports. |

## Runtime Data

`data/` is local runtime state and is ignored by Git.

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

Generated docs, maps, rendered PDFs, and validation artifacts outside `data/` need explicit artifact governance. Use `ode.core.artifacts.plan_artifact_write` before overwriting, versioning, or creating confusing siblings.

## Configuration And Contracts

| File | Purpose |
|---|---|
| [`pyproject.toml`](../pyproject.toml) | Package metadata, console script, pytest defaults. |
| [`requirements.txt`](../requirements.txt) | Runtime dependencies. |
| [`flows/opportunity_7stage.yaml`](../flows/opportunity_7stage.yaml) | External seven-stage flow declaration. |
| [`schemas/opportunity_import_flow.schema.json`](../schemas/opportunity_import_flow.schema.json) | Import plan contract. |
| [`examples/import_integration/`](../examples/import_integration) | Import integration golden input/output. |
| [`examples/revenue_cases/seed_cases.json`](../examples/revenue_cases/seed_cases.json) | Default revenue case library. |
| [`examples/profiles/open_founder_profile.json`](../examples/profiles/open_founder_profile.json) | Default founder profile example. |
| [`sources/opportunity_sources.yaml`](../sources/opportunity_sources.yaml) | Source registry. |

## Test Map

Collected tests on 2026-05-17: 225.

| Test File | Coverage |
|---|---|
| `tests/test_cli_surface.py` | CLI parser, JSON mode, service registry, Skill behavior. |
| `tests/test_service_boundaries.py` | Facade split, repository/scorer boundaries, MCP tools. |
| `tests/test_project_structure.py` | Runtime boundaries, ignored artifacts, artifact governance. |
| `tests/test_source_registry.py` | Source catalog and runtime dispatch. |
| `tests/test_service.py` | Service functions and opportunity workflow behavior. |
| `tests/test_heuristics.py` | Explore, bridge, reframe, synthesize. |
| `tests/test_pain_listener.py` | Pain evidence grading and validation queues. |
| `tests/test_revenue_cases.py` | Revenue evidence grading and fit rules. |
| `tests/test_daily_warning.py` | Alert levels, priors, stale logic, reports. |
| `tests/test_dbs_lens.py` | DBS commands, saved diagnostics, license boundary. |
| `tests/test_ai_hardware_workflow.py` | AI hardware workflow contract. |
| `tests/test_import_integration.py` | Imported detector adapter and schema/golden checks. |
| `tests/test_opportunity_scan_quality.py` | Generated opportunity scan quality contract. |
| `tests/test_storybook_pipeline_v2.py` | Storybook prototype contract. |

## Maintenance Rule

When code changes alter command behavior, source contexts, data model fields, or stage/gate semantics, update these documents in the same change:

- `README.md`
- `ARCHITECTURE.md`
- `docs/00-navigation.md`
- the relevant topic doc under `docs/`
