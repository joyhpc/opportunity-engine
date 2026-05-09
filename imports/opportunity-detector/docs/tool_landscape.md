# 开源工具全景图

机会评估各阶段可用的开源工具、GitHub 项目和最佳实践汇总。

## 信号捕获与趋势监测

### 趋势数据
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| pytrends | GeneralMills/pytrends | 3K+ | Python API | Google Trends 非官方 API |
| Google Trends API | 官方 (2025 alpha) | — | REST API | Google Trends 官方接口 |

### 网页采集
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| Crawl4AI | unclecode/crawl4ai | 58K+ | Python/CLI | AI 友好的网页爬取，输出 Markdown |
| Firecrawl | mendableai/firecrawl | 20K+ | API | 自然语言提取网页数据 |

### 社交聆听
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| Social-Media-Trend-Tracker | AbhayAyare/ | — | Python | Twitter/Reddit NLP 分析 |
| cocoindex | cocoindex-io/cocoindex | — | Python | HN 实时监控 + LLM 主题提取 |
| HN API | 官方 Firebase API | — | REST | Hacker News 数据 |
| Reddit API | 官方 | — | REST | Reddit 帖子/评论数据 |

---

## 市场分析

### 市场规模估算
- **本项目 `market_sizer.py`** — 自顶向下 + 自底向上 TAM/SAM/SOM
- **Metabase** (metabase/metabase, 46K+) — 连接数据源做市场数据探索
- **Jupyter + pandas** — 自定义分析的最灵活方案

### 竞品分析
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| competitor-analyst | 0xmetaschool/ | — | Web | AI 驱动竞品数据采集 + SWOT |
| subsignal | wizenheimer/ | — | API | 竞品动态监控（定价、功能变化） |
| RivalSearchMCP | damionrashford/ | — | MCP | Claude/Cursor 的竞品分析工具 |
| **本项目 `competitor_matrix.py`** | — | — | CLI | 竞品对比矩阵 + 定位图生成 |

---

## 验证与 MVP

### A/B 测试与产品分析
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| GrowthBook | growthbook/growthbook | 7K+ | API/SDK | Feature flag + A/B 测试，Bayesian 统计 |
| PostHog | PostHog/posthog | 32K+ | API/SDK | 全栈产品分析 + A/B + Session Replay |
| Unleash | Unleash/unleash | 10K+ | API/SDK | Feature flag 管理 |

### 快速原型
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| screenshot-to-code | abi/ | 71K+ | Web/CLI | 截图→功能代码（AI驱动） |
| GrapesJS | GrapesJS/grapesjs | 25K+ | JS API | 拖拽式网页/落地页编辑器 |
| Destack | LiveDuo/destack | — | npm | Next.js 零配置页面构建器 |

### 创意验证
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| LaunchLens | kle-08/launchlens | — | CLI | 30秒 AI 创意验证 |
| VettIQ | — | — | Web | LangGraph 驱动的创业验证 |

---

## 财务建模

- **本项目 `financial_model.py`** — 单位经济、盈亏平衡、敏感性分析
- **Jupyter + numpy/pandas** — 自定义复杂模型
- **QuantLib** (quantlib.org) — 量化金融库（高级场景）

---

## 商业计划

### 商业模式画布
| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| businesstools | syron/ | — | Web | 交互式 BMC + VPC |
| Lean-Canvas | anshusaurav/ | — | Web | Markdown → Lean Canvas |

---

## 运营监控

| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| Metabase | metabase/metabase | 46K+ | API/Web | BI 看板，自然语言查询 |
| Grafana | grafana/grafana | 60K+ | API/Web | 时序数据可视化 |
| PostHog | PostHog/posthog | 32K+ | API/Web | 产品指标全栈追踪 |

---

## 机会评分

| 工具 | GitHub | Stars | 接口 | 用途 |
|------|--------|-------|------|------|
| OppScoreWeb | jpcarrascal/ | — | Web | JTBD 机会评分 + 机会地图 |
| **本项目 `opportunity_scorer.py`** | — | — | CLI | 多维加权评分，Go/Kill 建议 |

---

## 推荐工具栈（最小可行）

对于个人或小团队快速启动，推荐以下最小工具栈：

```
信号捕获:  pytrends + HN API + Reddit API
市场分析:  market_sizer.py + competitor_matrix.py
评分决策:  opportunity_scorer.py
验证:      GrapesJS(落地页) + PostHog(埋点)
财务:      financial_model.py
监控:      Metabase
```

总依赖: Python 3.10+, requests, pytrends, pyyaml
