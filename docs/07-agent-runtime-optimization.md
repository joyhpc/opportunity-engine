# Agent Runtime Optimization

This is a roadmap document. It describes how ODE should become easier for agents and automations to consume. It is not a list of current shipped guarantees; use `README.md` and `ARCHITECTURE.md` for that.

## Current Baseline

ODE already has several agent-friendly foundations:

- `ode/service.py` is a surface-neutral async facade.
- `ode/services/*` keeps implementation behind that facade.
- `ode/service_commands.py` declares command metadata and routes parser-shaped params to services.
- CLI JSON mode uses service envelopes.
- Claude Skill routes registered commands through the shared registry.
- MCP registers read-only service tools.
- `flows/`, `schemas/`, and `examples/` provide machine-checkable contracts.
- `data/` keeps local state inspectable as YAML.
- Tests cover CLI, services, registry boundaries, source dispatch, DBS, warning state, import integration, and generated scan quality.

The main missing runtime pieces are:

- persistent run/session ledger;
- replay and failure recovery;
- full MCP write-tool contract;
- API/Web contracts and implementations;
- quality eval harness beyond pytest assertions.

## Optimization Priorities

### P0 - Shared Command Registry

Status: implemented.

Goal: avoid duplicating command parsing and service calls across CLI JSON, Skill, MCP, and future API adapters.

Current files:

- `ode/service_commands.py`
- `ode/cli_json.py`
- `ode/integrations/claude_skill.py`
- `ode/integrations/mcp_server.py`
- `tests/test_cli_surface.py`
- `tests/test_service_boundaries.py`

Current behavior:

- Registry command names are tested against parser command names.
- Each command has a read-only flag.
- JSON mode calls the registry first.
- Skill command handling calls the registry for registered commands.
- MCP exposes read-only registry commands.

Next work:

- Remove leftover duplicate fallback paths once they are proven unused.
- Add clearer parameter schemas for external tool consumers.
- Expand MCP carefully with write tools that return explicit run records.

### P1 - Persistent Run Ledger

Status: not implemented.

Goal: make every important agent-driven run auditable and recoverable.

Proposed model:

```text
data/runs/
  <run_id>.yaml
```

Suggested fields:

- `run_id`
- `command`
- `params`
- `started_at`
- `finished_at`
- `status`
- `service_result`
- `worker_results`
- `gate_results`
- `source_events`
- `artifacts`
- `next_action`
- `errors`

Why it matters:

- Agents can show what happened after a failed command.
- Daily scans can be replayed.
- Generated reports can cite source events and commands.
- MCP/API write tools can return a durable reference instead of only a transient response.

### P1 - Task Request Layer

Status: not implemented.

Goal: turn vague user intent into a structured request before creating opportunities or running scans.

DBS Lens already helps clarify vague language, but it is still command-centric. A future layer could create:

```text
TaskRequest
  goal
  constraints
  missing_facts
  recommended_commands
  minimum_evidence_required
  artifact_policy
```

Possible flow:

```text
user goal
  -> DBS clarify/deconstruct
  -> TaskRequest
  -> create/scan/cases/pain/daily
  -> RunRecord
  -> report
```

This would make agent usage less dependent on memorizing CLI commands.

### P2 - MCP And API Contracts

Status: partial for MCP read-only tools; API deferred.

Current MCP tools are read-only:

- `ode_status`
- `ode_list`
- `ode_show`
- `ode_sources`
- `ode_cases`
- `ode_portfolio`
- `ode_compare`
- `ode_insights`
- `ode_lens`

Recommended expansion order:

1. Keep read-only tools stable.
2. Add run ledger.
3. Add write tools for `create`, `scan`, `eval`, `report`, `experiment`, `record-actuals`, `refresh-gate`.
4. Require every write tool to return `run_id`, `artifacts`, and `next_action`.
5. Only then add a REST/API thin adapter.

API/Web should not duplicate service logic. Add contract tests before adding dependencies or server modules.

### P2 - Quality Eval Harness

Status: partially represented by tests and generated-report contract.

Existing quality assets:

- `docs/09-opportunity-scan-quality-contract.md`
- `docs/opportunity-scan-template.md`
- `tests/test_opportunity_scan_quality.py`
- `tests/test_ai_hardware_workflow.py`

Future harness:

```text
examples/evals/
  input opportunities
  fixed signals
  expected classifications
  expected evidence grades
  expected DBS blockers
```

Potential command:

```bash
python tools/run_quality_eval.py
```

The goal is to test judgment quality, not just code execution.

## Agent Consumption Rules

Agents using ODE should:

1. Start with `sources`, `cases`, `pain`, or `explore` before creating a strong recommendation.
2. Treat `planned` registry sources as coverage notes, not runtime evidence.
3. Use `--json` for machine parsing.
4. Save DBS diagnostics only when the user wants advisory records attached to an opportunity.
5. Use `lens` as soft sorting, not as a hard kill decision.
6. Use artifact governance before writing generated docs or maps outside normal data reports.

## Completed Improvements

- CLI entry point is thin.
- Parser is separate from handlers.
- Service implementation is split into `ode/services/*`.
- Shared command registry exists and is tested.
- JSON mode and Claude Skill use the registry.
- MCP read-only tools are registered from service commands.
- API/Web empty server stubs were removed.
- Artifact write planning exists.

## Next Small Slice

The next high-leverage slice is the run ledger:

1. Add `RunRecord` dataclass or schema.
2. Add `data/runs/` helpers under `ode/core/` or `ode/services/`.
3. Wrap write commands in run-record creation.
4. Return `run_id` from write command envelopes.
5. Add tests for `scan`, `eval`, `daily`, and `report` run records.

Do this before expanding MCP write tools or adding REST/API.
