# 机会探测器 (Opportunity Detector)

**用 DAG + 漏斗式评估流程，系统化发现和验证赚钱机会。**

基于 [project-tracker](https://github.com/joyhpc/project-tracker) 的 DAG/CPM 引擎。两种流程模板可选：

| 模板 | 阶段 | 节点 | 周期 | 适合 |
|------|------|------|------|------|
| `opportunity_detector` | 7 | 31 | ~59天 | 团队/大机会/需要深入分析 |
| `opportunity_detector_fast` | 4 | 15 | ~14天 | Solo founder / Micro SaaS / 快速验证 |

```
标准版: SENSE → SCREEN → ANALYZE → VALIDATE → PLAN → LAUNCH → MONITOR
加速版: SIGNAL → QUICK_ANALYZE → BUILD_VALIDATE → EXECUTE
```

## 核心理念

1. **漏斗式淘汰** — 每个阶段都有门禁，尽早 Kill 不值得的机会
2. **数据驱动决策** — 每个 Go/Kill 都基于结构化评估 + 红线检查，而非直觉
3. **Building IS Validation** — 用 AI 工具 7 天构建 MVP，构建本身就是最好的验证 (2025 最佳实践)
4. **痛点优先** — 不是你觉得痛，是用户自己在喊痛 (YC "痛点饮水坑" 方法)

## 快速开始

```bash
# 标准版 (深度评估)
cd ~/project-tracker
python3 pt init my-idea --name "我的想法" --flow opportunity_detector

# 加速版 (Solo Founder 14天验证)
python3 pt init my-idea --name "我的想法" --flow opportunity_detector_fast

# 查看进度
python3 pt status && python3 pt map
```

## 工具集 (9个)

### 信号发现
| 工具 | 用途 | 阶段 |
|------|------|------|
| `trend_scanner.py` | Google Trends + HN + Reddit 趋势扫描 | SENSE/SIGNAL |
| `pain_miner.py` | 从社区评论挖掘用户真实痛点，按严重度排序 | SENSE/SIGNAL |

### 分析评估
| 工具 | 用途 | 阶段 |
|------|------|------|
| `market_sizer.py` | TAM/SAM/SOM 估算（自顶向下+自底向上+交叉验证） | SCREEN |
| `competitor_matrix.py` | 竞品对比矩阵 + 2x2定位图 + 差异化分析 | SCREEN/ANALYZE |
| `opportunity_scorer.py` | **v2**: YC/a16z标准评分 + 红线检查 + 行动建议 | SCREEN |
| `financial_model.py` | 单位经济 + 盈亏平衡 + 36月预测 + 敏感性分析 | ANALYZE/PLAN |

### 验证执行
| 工具 | 用途 | 阶段 |
|------|------|------|
| `idea_validator.py` | 14天快速验证Playbook + Kill红线 + 进度追踪 | VALIDATE |
| `report_generator.py` | 汇总各阶段输出，生成 Markdown 报告 | 全阶段 |

每个工具都支持 `--help` 和 `--demo`。

## v2 评分框架 (来自 YC/a16z 2025-2026 最佳实践)

评分卡 v2 新增维度：
- **验证强度 (YC MVT)** — 痛点证据、付费意愿、最小可行测试结果
- **AI-Native 潜力 (a16z)** — 系统重构度、数据飞轮、复利优势
- **红线检查** — 任一红线触发即强制 Kill，不看总分

```bash
# 试试看
python3 tools/opportunity_scorer.py --demo          # v2 (默认)
python3 tools/opportunity_scorer.py --demo --framework v1  # v1
python3 tools/pain_miner.py --demo                  # 痛点挖掘
python3 tools/idea_validator.py --checklist          # 验证清单
```

## 推荐开源工具栈

| 功能 | 工具 | Stars |
|------|------|-------|
| 深度调研 | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 26K+ |
| 网页采集 | [Crawl4AI](https://github.com/unclecode/crawl4ai) / [Firecrawl](https://github.com/mendableai/firecrawl) | 60K+ / 90K+ |
| Reddit 调研 | [reddit-research-mcp](https://github.com/king-of-the-grackles/reddit-research-mcp) | MCP |
| 搜索 MCP | [tavily-mcp](https://github.com/tavily-ai/tavily-mcp) | 1.4K+ |
| A/B 测试 | [GrowthBook](https://github.com/growthbook/growthbook) | 7K+ |
| 产品分析 | [PostHog](https://github.com/PostHog/posthog) | 32K+ |
| 竞品情报 | [brightdata/competitive-intelligence](https://github.com/brightdata/competitive-intelligence) | Multi-agent |
| 公司调研 | [company-research-agent](https://github.com/guy-hartstein/company-research-agent) | 1.6K+ |

完整列表见 [工具全景图](docs/tool_landscape.md)。

## 与 project-tracker 的架构关系

```
┌─────────────────────────────────────────────────┐
│  project-tracker (通用引擎层)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ DAG/CPM  │ │ 决策登记簿 │ │ PoC 追踪  │         │
│  └──────────┘ └──────────┘ └──────────┘         │
│  flows/                                         │
│    ├── opportunity_detector.yaml  ← 接口层       │
│    ├── software_mvp.yaml                        │
│    └── ...                                      │
└───────────────────────┬─────────────────────────┘
                        │ 流程模板 = 插件接口
┌───────────────────────┴─────────────────────────┐
│  opportunity-detector (领域工具层)                 │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────┐ │
│  │ trend_scanner│ │ market_sizer │ │ scorer    │ │
│  │ pain_miner  │ │ competitor_  │ │ financial │ │
│  │             │ │   matrix     │ │   _model  │ │
│  └─────────────┘ └──────────────┘ └───────────┘ │
│  templates/  ← 模板的权威源头                      │
│  subtasks/   ← 子任务展开模板                      │
└─────────────────────────────────────────────────┘
```

**架构相似处 & 设计约定**：

| 维度 | project-tracker | opportunity-detector | 共享模式 |
|------|----------------|---------------------|---------|
| 核心抽象 | DAG 节点 + 阶段 + 门禁 | 同左（复用 pt 引擎） | phases → nodes → milestones(gate) |
| 推进模型 | start → done / skip | 同左 | 漏斗式淘汰，门禁处 Go/Kill |
| 决策追踪 | `pt decision` | 同左 | 结构化决策 + source + impact |
| 验证追踪 | `pt poc` | 同左 | 假设 → 红线指标 → 验证结果 |
| 子任务展开 | `pt sub-load` | 同左 | 按需加载，不预展开 |
| 工具脚本 | 无（引擎不含领域工具） | 9个 Python 分析工具 | 工具输出 → pt decision 记录 |

**边界原则**：
- **pt 不含领域逻辑** — 它是通用的 DAG 引擎，不知道"市场规模"或"竞品矩阵"是什么
- **opportunity-detector 不含调度逻辑** — 它不管节点依赖、关键路径、进度计算
- **流程模板是接口** — `templates/` 是模板的权威源头，安装时 copy 到 `pt/tracker/flows/`
- **工具可独立运行** — 所有 Python 工具支持 `--demo`，不依赖 pt 运行时

## 文档

- [7阶段漏斗方法论](docs/methodology.md) — 标准版流程详解
- [开源工具全景图](docs/tool_landscape.md) — 80+ 开源工具分类索引
- [pt 集成指南](docs/integration_guide.md) — project-tracker 集成用法
