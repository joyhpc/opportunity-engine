# ODE Architecture

> 三层扁平架构设计文档

---

## Design Principles

1. **扁平优于分层**：3 层足够，不引入 4-5 层的复杂性
2. **Gate 驱动推进**：每个阶段必须通过门禁，防止未验证的想法消耗资源
3. **启发优于评判**：KILL 不是终点，reframe 给出转型路径
4. **零依赖启动**：不需要 API Key、GPU 或外部服务即可运行核心功能
5. **数据可审计**：所有状态存储在 YAML 文件中，可 `git diff` 追踪变化

---

## Layer Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    ACCESS LAYER                          │
│                                                          │
│  ┌──────────┐  ┌──────────────┐  ┌─────┐  ┌──────────┐ │
│  │ CLI      │  │ Claude Skill │  │ MCP │  │ API/Web  │ │
│  │ cli.py   │  │ claude_skill │  │ WIP │  │ WIP      │ │
│  └────┬─────┘  └──────┬───────┘  └──┬──┘  └────┬─────┘ │
├───────┴──────────────┬─┴────────────┴──────────┴────────┤
│                 ENGINE CORE                              │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Pipeline DAG (engine/pipeline.py)              │    │
│  │  Kahn's algorithm topo sort → stage scheduling  │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  Workers (engine/workers.py)                    │    │
│  │  scan_worker · eval_worker · report_worker      │    │
│  │  async functions, run via asyncio.gather()      │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  Gate Evaluator (engine/gate.py)                │    │
│  │  SENSE gate · SCREEN gate · ANALYZE gate        │    │
│  │  GO / MAYBE / KILL verdict                      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Heuristics (heuristics/) — decoupled           │    │
│  │  explore · bridge · reframe · synthesize        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Tools (tools/)                                 │    │
│  │  trend_scanner · market_sizer · financial_model │    │
│  │  opportunity_scorer · competitor_matrix          │    │
│  │  report_generator · tech_feasibility            │    │
│  └─────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE                          │
│                                                          │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │ YAML Store   │  │ SQLite Cache  │  │ BM25 Index   │ │
│  │ core/store   │  │ data/cache    │  │ data/knowledge│ │
│  │ Git-tracked  │  │ TTL-based     │  │ pt-wrapper   │ │
│  └──────────────┘  └───────────────┘  └──────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## Module Map

### Access Layer

| Module | Path | Description |
|--------|------|-------------|
| CLI | `ode/cli.py` | Thin entry point over parser, handlers, and JSON mode |
| Claude Skill | `ode/integrations/claude_skill.py` | `/ode` skill handler for Claude Code |
| MCP Server | `ode/integrations/mcp_server.py` | MCP tool registration (Phase 3) |
| API/Web | `ode/api/`, `ode/web/` | FastAPI + dashboard (Phase 3) |

### Engine Core

| Module | Path | Description |
|--------|------|-------------|
| Pipeline DAG | `ode/engine/pipeline.py` | Kahn's algorithm topo sort, stage scheduling, optional pt-engine integration |
| Gate | `ode/engine/gate.py` | Stage gate evaluation: SENSE (signal count), SCREEN (weighted score + redlines), ANALYZE (NPV + regulatory) |
| Workers | `ode/engine/workers.py` | `scan_worker`, `eval_worker`, `report_worker` — async functions, not independent processes |
| Portfolio | `ode/engine/portfolio.py` | Multi-opportunity comparison and ranking |

### Heuristic Modules (Decoupled)

| Module | Path | Trigger | Description |
|--------|------|---------|-------------|
| explore | `ode/heuristics/explore.py` | `ode explore` | Signal clustering → hypothesis generation, no keywords needed |
| bridge | `ode/heuristics/bridge.py` | `ode eval` (auto) | Signal → 18-criterion score inference with confidence levels |
| reframe | `ode/heuristics/reframe.py` | `ode insights` | MAYBE/KILL → concrete pivot strategies per weak dimension |
| synthesize | `ode/heuristics/synthesize.py` | `ode insights` / report | Cross-data contradiction detection + blind spot analysis |
| fit_lens | `ode/heuristics/fit_lens.py` | `ode lens` | Soft founder-fit sorting that preserves high-discovery wildcards |

### Tools

| Module | Path | Description |
|--------|------|-------------|
| Trend Scanner | `ode/tools/trend_scanner.py` | Google Trends + HackerNews API + Reddit scan |
| Source Registry | `ode/tools/source_registry.py` | Auditable source catalog from `sources/opportunity_sources.yaml` |
| Market Sizer | `ode/tools/market_sizer.py` | Top-down / bottom-up TAM/SAM/SOM estimation |
| Financial Model | `ode/tools/financial_model.py` | Unit economics (LTV/CAC), 36-month projections, NPV |
| Opportunity Scorer | `ode/tools/opportunity_scorer.py` | YC/a16z 6-dimension weighted scorecard, redline mechanism |
| Competitor Matrix | `ode/tools/competitor_matrix.py` | Competitor landscape analysis |
| Report Generator | `ode/tools/report_generator.py` | Markdown report generation with synthesis insights |
| Tech Feasibility | `ode/tools/tech_feasibility.py` | Technology feasibility assessment |

### Infrastructure

| Module | Path | Description |
|--------|------|-------------|
| YAML Store | `ode/core/store.py` | Generic entity CRUD, file-per-entity, Git-friendly |
| Models | `ode/core/models.py` | Opportunity, Signal, Competitor, Evidence, WorkerResult dataclasses |
| Constants | `ode/core/constants.py` | Stages, thresholds, scoring dimensions, paths |
| SQLite Cache | `ode/data/cache.py` | TTL-based key-value cache |
| BM25 Knowledge | `ode/data/knowledge.py` | Full-text search, wraps pt knowledge.py if available |

---

## Data Flow

### Complete Pipeline Flow

```
User
 │
 ├─ "I don't know what to build"
 │   └─► ode explore
 │        ├── scan HN/Reddit (trend_scanner)
 │        ├── cluster signals (explore.cluster_signals)
 │        ├── generate hypotheses (explore.generate_hypotheses)
 │        └── output: ranked opportunity hypotheses + next steps
 │
 ├─ "I have an idea"
 │   └─► ode create → ode scan → ode eval → ode report
 │        │             │          │          │
 │        │             │          │          └── report_worker
 │        │             │          │               ├── report_generator
 │        │             │          │               └── synthesize (auto-appended)
 │        │             │          │
 │        │             │          └── eval_worker
 │        │             │               ├── market_sizer
 │        │             │               ├── competitor_matrix
 │        │             │               ├── financial_model
 │        │             │               ├── bridge.infer_scores (auto, if no --scores)
 │        │             │               ├── opportunity_scorer
 │        │             │               └── gate.evaluate_gate
 │        │             │                    └── GO / MAYBE / KILL
 │        │             │
 │        │             └── scan_worker
 │        │                  ├── trend_scanner.scan_all
 │        │                  ├── dedup + save signals
 │        │                  └── gate.evaluate_sense_gate
 │        │
 │        └── store.save_opportunity
 │
 └─ "Score is MAYBE/KILL, now what?"
     └─► ode insights
          ├── synthesize (contradictions + blind spots)
          └── reframe (pivot strategies if score < 70)
```

### Gate Decision Logic

```
SENSE Gate (entry to SCREEN):
  strong_count = Σ(signal.strength ∈ {强, 中→weighted})
  strong >= 3 → GO
  strong >= 1 → MAYBE
  else       → KILL

SCREEN Gate (entry to ANALYZE):
  weighted_pct = Σ(dim_score × dim_weight) / total_weight × 10
  redline triggered → KILL (override)
  pct >= 70 → GO
  pct >= 50 → MAYBE
  pct <  50 → KILL

ANALYZE Gate (entry to VALIDATE):
  NPV > 0 AND no P0 regulatory risk → GO
  else → KILL
```

---

## Data Model

### Entity Relationships

```
Opportunity (opp-xxx)
 ├── signals: [sig-xxx, ...]        → Signal entities
 ├── scores: {criterion: value}     → from scorer/bridge
 ├── market: {tam, sam, som, ...}   → from market_sizer
 ├── financials: {ltv, cac, ...}    → from financial_model
 ├── gate_log: [{gate, verdict}]    → history of gate decisions
 └── stage: SENSE|SCREEN|ANALYZE|...

Signal (sig-xxx)
 ├── source: HN|Reddit|GoogleTrends
 ├── keyword, title, url
 ├── strength: 强|中|弱
 ├── momentum: 0-100
 └── opportunity_id: opp-xxx

WorkerResult
 ├── worker: scan|eval|report
 ├── status: ok|failed
 ├── scores, artifacts, data
 └── next_action: advance|hold|kill
```

### Storage Layout

```
~/opportunity-engine/data/
├── opportunities/
│   └── opp-{uuid}.yaml         # One file per opportunity
├── signals/
│   └── sig-{uuid}.yaml         # One file per signal
├── competitors/
│   └── comp-{uuid}.yaml
├── evidence/
│   └── ev-{uuid}.yaml
├── reports/
│   └── opp-{id}_{stage}.md     # Generated reports
└── cache.db                    # SQLite TTL cache
```

---

## Heuristic System Design

The heuristic modules are **decoupled** from the core engine — they can be removed without breaking any pipeline functionality.

### Why Decoupled?

1. **不同生命周期**：核心评估逻辑稳定，启发规则需要频繁迭代
2. **可选使用**：用户可以跳过启发直接手动评分
3. **可测试性**：纯函数，不依赖 IO，易于单元测试
4. **可替换**：未来可接入 LLM 作为启发源，不影响引擎

### Bridge Auto-Scoring Flow

```
eval_worker receives no --scores
  │
  ├── load signals for this opportunity
  ├── call bridge.infer_scores(signals, domain, market, financials)
  │    ├── Market criteria: signal volume + diversity → tam_size estimate
  │    ├── Competition: keyword detection → intensity inference
  │    ├── Economics: financial data → LTV/CAC score, or SaaS defaults
  │    ├── Validation: pain keywords → pain_evidence estimate
  │    └── AI-Native: AI keyword density → system_rethink score
  ├── scores_to_flat() → {criterion: score}
  └── proceed to scoring with inferred scores
```

Each inferred score includes a confidence tag (`auto` or `data`) and reasoning string, so the user knows which scores to trust and which to override.

---

## Integration Points

### project-tracker Bridge

```
ode eval <id>        → opportunity scored and gated
ode insights <id>    → insights generated
  │
  └── When opportunity reaches GRADUATED status:
      pt_bridge.promote_to_project(opp)
        └── subprocess: cd ~/project-tracker && python3 pt decision --add "..."
```

### Claude Code Skill

```
User types: /ode scan --keywords "AI,robotics"
  └── claude_skill.py
       ├── shlex.split(args)
       └── subprocess: python3 -m ode scan --keywords "AI,robotics"
```

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | Done | Core models + YAML store + constants |
| Phase 2 | Done | Pipeline DAG + gate + workers + tools |
| Phase 3 (WIP) | Stub | MCP server + FastAPI + Web dashboard |
| Phase 4 | Done | Configuration externalization (YAML configs) |
| Phase 5 | Done | Pipeline orchestration + JSON sidecar contracts |
| Phase 6 | Done | Heuristic modules: explore, bridge, reframe, synthesize |
| Phase 7 | Done | Founder Fit Lens: soft sorting without early hard filtering |

## Repository Structure

Operational repository boundaries are documented in
[`docs/03-project-structure.md`](docs/03-project-structure.md). In short:

- `ode/` is the only active runtime package.
- `imports/` is audited legacy/source material.
- `prototypes/` is experimental and must not be imported by runtime code.
- `flows/`, `schemas/`, and `examples/` define reproducible contracts.
