# ODE — Opportunity Discovery Engine

> 机会发现引擎：从模糊直觉到数据驱动决策的系统化工具

---

## What is ODE?

ODE 是一个命令行工具，帮助独立开发者和小团队系统化地发现、评估和筛选商业机会。

**核心理念**：大多数人不是缺少想法，而是缺少一个结构化的评估框架。ODE 将 YC/a16z 的评估方法论工程化，让每个人都能用投资人的视角审视自己的想法。

### 解决什么问题

| 状态 | 传统方式 | ODE 方式 |
|------|---------|---------|
| "我不知道做什么" | 等灵感 | `ode explore` — 扫描趋势，聚类机会假设 |
| "这个想法行不行" | 拍脑袋 | `ode eval` — 6维18指标量化评分 |
| "数据矛盾怎么办" | 忽略不适感 | `ode insights` — 自动发现矛盾和盲区 |
| "被评为KILL怎么办" | 放弃 | reframe 启发模块 — 给出具体转型建议 |

---

## Quick Start

```bash
cd ~/opportunity-engine

# 1. 探索：不需要任何想法，扫描当前热点
python3 -m ode explore

# 2. 创建：从探索结果中锁定一个方向
python3 -m ode create --name "AI Tutor" --domain education --keywords "AI,tutoring,personalized"

# 3. 扫描：收集信号
python3 -m ode scan --keywords "AI tutoring,personalized learning" --hn-top 30 --reddit "edtech,learnprogramming"

# 4. 评估：自动推断评分 + 门禁判定
python3 -m ode eval <opp_id> --tam 5e9 --arpu 29.99

# 5. 报告：生成评估报告（含洞察）
python3 -m ode report <opp_id> --stage screen --print

# 6. 洞察：矛盾检测 + 盲区分析 + 转型建议
python3 -m ode insights <opp_id>

# 7. 画像镜头：开放发现后的软排序，不直接 kill 机会
python3 -m ode lens <opp_id> --profile examples/profiles/open_founder_profile.json

# 8. 组合视图
python3 -m ode portfolio
```

---

## CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `explore` | 开放式机会发现（无需想法） | `ode explore --hn-top 50` |
| `create` | 创建新机会 | `ode create --name "X" --domain "Y"` |
| `list` | 列出所有机会 | `ode list` |
| `show` | 查看机会详情 | `ode show <id>` |
| `scan` | 信号扫描 (HN/Reddit/Trends) | `ode scan --keywords "AI,SaaS"` |
| `eval` | 多维度评估 + 门禁 | `ode eval <id> --depth screen` |
| `report` | 生成 Markdown 报告 | `ode report <id> --print` |
| `insights` | 矛盾/盲区/转型建议 | `ode insights <id>` |
| `lens` | Founder Fit Lens 软排序 | `ode lens <id> --profile examples/profiles/open_founder_profile.json` |
| `portfolio` | 组合对比视图 | `ode portfolio` |
| `compare` | 并排对比机会 | `ode compare "id1,id2"` |
| `status` | ODE 系统状态 | `ode status` |

---

## Architecture

三层扁平架构 — 详见 [ARCHITECTURE.md](ARCHITECTURE.md)

```
┌─────────────────────────────────────────┐
│  Access Layer                           │
│  CLI · Claude Skill · MCP · API(WIP)   │
├─────────────────────────────────────────┤
│  Engine Core                            │
│  Pipeline DAG · Gate · Workers          │
│  ┌──────────────────────────────┐       │
│  │ Heuristics (decoupled)      │       │
│  │ explore·bridge·reframe·synth│       │
│  └──────────────────────────────┘       │
├─────────────────────────────────────────┤
│  Infrastructure                         │
│  YAML Store · SQLite Cache · BM25 Index │
└─────────────────────────────────────────┘
```

---

## Repository Layout

当前仓库按四类边界组织：

| Area | Purpose |
|------|---------|
| `ode/` | 正式产品包：CLI、service、engine、heuristics、tools、integrations |
| `flows/`, `schemas/`, `examples/` | 可验证流程、数据契约和 golden examples |
| `imports/` | 外部/历史项目审计素材，不作为第二个活跃产品维护 |
| `prototypes/` | 原型实验区，不被运行时代码直接依赖 |

详细层级和整理规则见 [docs/03-project-structure.md](docs/03-project-structure.md)。

机会筛选采用 “开放发现 + 延迟判断”：

```
Opportunity Score + Founder Fit + Discovery Value → Build Now / Validate Soon / Watch / Research / Ignore
```

Founder Fit Lens 是软排序，不是早期硬过滤；高 Discovery Value 的异类机会会进入 Watch，而不是被过早丢弃。

---

## Pipeline: 7-Stage Gate System

```
SENSE → SCREEN → ANALYZE → VALIDATE → PLAN → LAUNCH → MONITOR
  │        │         │          │
  ▼        ▼         ▼          ▼
 ≥3信号   ≥70分     NPV>0     ≥3付费用户
 GO/KILL  GO/MAYBE  GO/KILL   GO/KILL
          /KILL
```

每个阶段有门禁（Gate），只有通过门禁才能进入下一阶段。MAYBE 触发 reframe 启发模块。

---

## Scoring Framework

6 维度 18 指标，权重来源于 YC/a16z 评估方法论：

| Dimension | Weight | Criteria |
|-----------|--------|----------|
| Market Attractiveness | 25% | TAM, Growth, Timing |
| Competitive Landscape | 15% | Intensity, Barrier, Moat Potential |
| Capability Fit | 15% | Skill Match, Resource Need, Time to Market |
| Economic Viability | 25% | LTV/CAC, Margin, Payback |
| Validation Strength | 10% | Pain Evidence, WTP, MVT Result |
| AI-Native Potential | 10% | System Rethink, Data Loop, Compound Advantage |

Redline 机制：特定指标触发红线时，无论总分多高都判 KILL。

---

## Heuristic Modules (启发模块)

ODE 的核心差异化：不仅评估，还启发。

| Module | Purpose | Entry Point |
|--------|---------|-------------|
| **explore** | "我不知道做什么" → 扫描+聚类+假设生成 | `ode explore` |
| **bridge** | 信号 → 评分自动推断（18项免手动） | `ode eval`（无 --scores 时自动触发） |
| **reframe** | MAYBE/KILL → 具体转型策略 | `ode insights <id>` |
| **synthesize** | 交叉数据矛盾检测 + 盲区发现 | `ode insights <id>` / report 自动附加 |
| **fit_lens** | 机会质量 + 创始人适配 + 发现价值 → 软排序 | `ode lens <id>` |

详见 [docs/01-heuristic-design.md](docs/01-heuristic-design.md)

---

## Integration

| System | Integration | Status |
|--------|------------|--------|
| [project-tracker](https://github.com/joyhpc/project-tracker) | 机会毕业 → pt project | Done |
| Claude Code Skill | `/ode` 命令 | Done |
| MCP Server | 标准化工具注册 | Phase 3 |
| FastAPI | REST API | Phase 3 |

---

## Test Suite

```bash
python3 -m pytest tests/ -v    # 114 tests
```

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_cli_surface.py` | 4 | CLI 入口拆分、parser 命令集合、JSON/text 模式 |
| `tests/test_eldermind.py` | 33 | 核心模块：models, store, scorer, financials, gate, pipeline, cache, CLI |
| `tests/test_fit_lens.py` | 4 | Founder Fit Lens 分类、异类机会保护、service 接入 |
| `tests/test_heuristics.py` | 25 | 启发模块：explore, bridge, reframe, synthesize |
| `tests/test_import_integration.py` | 2 | 外部导入素材到 ODE 七阶段计划的契约 |
| `tests/test_project_structure.py` | 3 | 仓库层级边界、运行产物追踪检查 |
| `tests/test_service.py` | 43 | service layer、实验记录、实际财务数据、gate refresh |

---

## Dependencies

```
pyyaml>=6.0       # YAML 持久化
requests>=2.28    # HTTP 信号采集
pytest>=7.0       # 测试
pytest-asyncio    # 异步测试
```

零重度依赖，无需 GPU，无需 API Key（除非使用 Google Trends）。

---

## License

MIT

## GitHub

https://github.com/joyhpc/opportunity-engine
