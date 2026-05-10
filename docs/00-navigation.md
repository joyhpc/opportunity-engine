# ODE Navigation

> Opportunity Discovery Engine — 项目导航页

---

## Quick Start

```bash
cd ~/opportunity-engine

# 探索模式（零输入启动）
python3 -m ode explore

# 完整流程
python3 -m ode create --name "X" --domain "Y" --keywords "a,b,c"
python3 -m ode scan --keywords "a,b"
python3 -m ode eval <opp_id> --tam 1e9 --arpu 29.99
python3 -m ode report <opp_id> --print
python3 -m ode insights <opp_id>
python3 -m ode lens <opp_id> --profile examples/profiles/open_founder_profile.json
python3 -m ode portfolio
```

---

## Project Documentation

| # | Document | Description | Key Topics |
|---|----------|-------------|------------|
| — | [README](../README.md) | 项目概览、Quick Start、CLI 参考 | 命令列表、评分维度、依赖 |
| — | [ARCHITECTURE](../ARCHITECTURE.md) | 三层架构设计、数据流、模块关系 | 层次图、Gate 逻辑、数据模型、集成点 |
| 01 | [Heuristic Design](01-heuristic-design.md) | 启发模块设计思路与应用笔记 | explore/bridge/reframe/synthesize |
| 02 | [AI Storybook Product Plan](02-ai-storybook-product-plan.md) | 原型产品计划 | storybook prototype |
| 03 | [Project Structure](03-project-structure.md) | 仓库层级、边界规则、清理路线 | ode/imports/prototypes/tests/tools |
| 04 | [Data Sources](04-data-sources.md) | 机会发现数据源注册表和扫描边界 | HN、Reddit、Google Trends、中国国内源 |
| — | [Import Integration](import-integration.md) | opportunity-detector 导入契约 | schema、golden example、validator |

---

## Source Code Map

### Access Layer

| Module | Path | Description |
|--------|------|-------------|
| CLI | [`ode/cli.py`](../ode/cli.py) | Thin entrypoint over parser, handlers, JSON mode |
| Claude Skill | [`ode/integrations/claude_skill.py`](../ode/integrations/claude_skill.py) | `/ode` Claude Code skill handler |
| MCP Server | [`ode/integrations/mcp_server.py`](../ode/integrations/mcp_server.py) | MCP tool registration (Phase 3 stub) |
| pt Bridge | [`ode/integrations/pt_bridge.py`](../ode/integrations/pt_bridge.py) | project-tracker sync on opportunity graduation |

### Engine Core

| Module | Path | Description |
|--------|------|-------------|
| Pipeline DAG | [`ode/engine/pipeline.py`](../ode/engine/pipeline.py) | Kahn's algorithm topo sort, 7-stage scheduling |
| Gate | [`ode/engine/gate.py`](../ode/engine/gate.py) | SENSE/SCREEN/ANALYZE gate evaluators |
| Workers | [`ode/engine/workers.py`](../ode/engine/workers.py) | scan/eval/report async workers + bridge auto-scoring |
| Portfolio | [`ode/engine/portfolio.py`](../ode/engine/portfolio.py) | Multi-opportunity comparison and ranking |

### Heuristic Modules

| Module | Path | Trigger | Description |
|--------|------|---------|-------------|
| Explore | [`ode/heuristics/explore.py`](../ode/heuristics/explore.py) | `ode explore` | Signal clustering → opportunity hypotheses |
| Bridge | [`ode/heuristics/bridge.py`](../ode/heuristics/bridge.py) | `ode eval` (auto) | 18-criterion score auto-inference |
| Reframe | [`ode/heuristics/reframe.py`](../ode/heuristics/reframe.py) | `ode insights` | MAYBE/KILL → pivot strategies |
| Synthesize | [`ode/heuristics/synthesize.py`](../ode/heuristics/synthesize.py) | `ode insights` / report | Contradiction + blind spot detection |
| Founder Fit Lens | [`ode/heuristics/fit_lens.py`](../ode/heuristics/fit_lens.py) | `ode lens` | Soft sorting: opportunity score + founder fit + discovery value |

### Tools

| Module | Path | Description |
|--------|------|-------------|
| Trend Scanner | [`ode/tools/trend_scanner.py`](../ode/tools/trend_scanner.py) | HN + Reddit + Google Trends signals |
| Source Registry | [`ode/tools/source_registry.py`](../ode/tools/source_registry.py) | Auditable source catalog loaded from `sources/opportunity_sources.yaml` |
| Market Sizer | [`ode/tools/market_sizer.py`](../ode/tools/market_sizer.py) | Top-down/bottom-up TAM/SAM/SOM |
| Financial Model | [`ode/tools/financial_model.py`](../ode/tools/financial_model.py) | LTV/CAC, NPV, 36-month projections |
| Opportunity Scorer | [`ode/tools/opportunity_scorer.py`](../ode/tools/opportunity_scorer.py) | YC/a16z 6-dim weighted scorecard |
| Competitor Matrix | [`ode/tools/competitor_matrix.py`](../ode/tools/competitor_matrix.py) | Competitor landscape analysis |
| Report Generator | [`ode/tools/report_generator.py`](../ode/tools/report_generator.py) | Markdown report + synthesis auto-append |
| Tech Feasibility | [`ode/tools/tech_feasibility.py`](../ode/tools/tech_feasibility.py) | Technology feasibility check |

### Infrastructure

| Module | Path | Description |
|--------|------|-------------|
| Models | [`ode/core/models.py`](../ode/core/models.py) | Opportunity, Signal, Competitor, Evidence, WorkerResult |
| Store | [`ode/core/store.py`](../ode/core/store.py) | YAML-based entity CRUD |
| Constants | [`ode/core/constants.py`](../ode/core/constants.py) | Stages, thresholds, paths |
| Cache | [`ode/data/cache.py`](../ode/data/cache.py) | SQLite TTL cache |
| Knowledge | [`ode/data/knowledge.py`](../ode/data/knowledge.py) | BM25 full-text search |

---

## Configuration

| File | Purpose |
|------|---------|
| [`flows/opportunity_7stage.yaml`](../flows/opportunity_7stage.yaml) | Pipeline stage definitions, dependencies, gate rules |
| [`examples/profiles/open_founder_profile.json`](../examples/profiles/open_founder_profile.json) | Open default founder profile for soft fit sorting |
| [`sources/opportunity_sources.yaml`](../sources/opportunity_sources.yaml) | Registered active, optional, utility, manual, and planned discovery sources |
| [`requirements.txt`](../requirements.txt) | Python dependencies |

---

## Test Suite

```bash
python3 -m pytest tests/ -v    # 121 tests, < 1s
```

| Test File | Tests | Coverage |
|-----------|-------|----------|
| [`tests/test_cli_surface.py`](../tests/test_cli_surface.py) | 4 | CLI entrypoint split, parser command set, JSON/text modes |
| [`tests/test_eldermind.py`](../tests/test_eldermind.py) | 33 | models, store, scorer, financials, gate, pipeline, cache, CLI |
| [`tests/test_fit_lens.py`](../tests/test_fit_lens.py) | 4 | Founder Fit Lens classification, wildcard protection, service integration |
| [`tests/test_heuristics.py`](../tests/test_heuristics.py) | 25 | explore, bridge, reframe, synthesize |
| [`tests/test_import_integration.py`](../tests/test_import_integration.py) | 2 | imported detector assets and closed-loop plan contract |
| [`tests/test_project_structure.py`](../tests/test_project_structure.py) | 3 | repository hierarchy boundaries and artifact tracking |
| [`tests/test_service.py`](../tests/test_service.py) | 43 | service API, experiments, actuals, gate refresh |
| [`tests/test_source_registry.py`](../tests/test_source_registry.py) | 7 | source registry, region filter, runtime source ids, restricted platform sources, scanner source_id |

---

## Data Directory

```
data/
├── opportunities/     # opp-{uuid}.yaml
├── signals/           # sig-{uuid}.yaml
├── competitors/       # comp-{uuid}.yaml
├── evidence/          # ev-{uuid}.yaml
├── reports/           # {opp_id}_{stage}.md
└── cache.db           # SQLite TTL cache
```

---

## Related Projects

| Project | Repo | Integration |
|---------|------|-------------|
| project-tracker | [joyhpc/project-tracker](https://github.com/joyhpc/project-tracker) | 机会毕业 → pt project |
| sch-review | [joyhpc/sch-review](https://github.com/joyhpc/sch-review) | — |
| hardware-copilot | [joyhpc/hardware-copilot](https://github.com/joyhpc/hardware-copilot) | — |

---

## GitHub

https://github.com/joyhpc/opportunity-engine
