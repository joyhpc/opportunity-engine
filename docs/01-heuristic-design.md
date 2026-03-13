# Heuristic Design — 启发模块设计笔记

> Application Note: 为什么 ODE 需要启发功能，以及它如何工作

---

## Problem Statement

传统的机会评估工具有一个隐含假设：**用户已经知道自己要评估什么**。

但现实中，85-90% 的工作流需要用户预先具备：
- 明确的想法方向
- 对市场的初步认知
- 对 18 项评分标准的判断能力

这导致了一个悖论：**最需要工具帮助的人（处于模糊状态的人）反而无法使用工具**。

---

## Design Decision

将启发功能实现为 **4 个解耦模块**，而非内嵌到核心引擎中。

### Why Decoupled?

| 考虑因素 | 内嵌 | 解耦 |
|---------|------|------|
| 核心引擎稳定性 | 启发规则变化影响评估 | 互不影响 |
| 可选使用 | 无法跳过 | 用户可选择不用 |
| 测试性 | 需要完整 pipeline | 纯函数，独立测试 |
| 可替换性 | 修改引擎代码 | 接口不变，实现可换 |
| 未来 LLM 接入 | 改动面大 | 换一个实现即可 |

---

## Module 1: Explore (开放式发现)

**用户状态**："我不知道做什么"

**设计思路**：

不要求用户输入任何关键词。从公开趋势源（HN Top Stories, Reddit 热帖, Google Trends）抓取信号，然后用文本聚类将它们归入领域主题。

### Clustering Algorithm

选择了 **domain seed-word matching** 而非 ML 聚类（K-Means, DBSCAN），原因：

1. **零依赖**：不需要 scikit-learn, numpy
2. **可解释**：用户能理解"为什么这个信号属于 health 领域"
3. **足够好**：9 个预定义领域 + "emerging" 兜底，覆盖率足够
4. **可扩展**：添加新领域只需加一组 seed words

```python
DOMAIN_SEEDS = {
    "health": ["health", "medical", "therapy", "wellness", ...],
    "ai_ml": ["ai", "llm", "gpt", "agent", "copilot", ...],
    "fintech": ["finance", "payment", "crypto", ...],
    # ...9 domains + "emerging" fallback
}
```

匹配算法：tokenize 信号标题 → 与每个领域的 seed words 求交集 → 分配到最大交集的领域。

### Hypothesis Generation

对每个聚类，生成一个机会假设：
- 提取 top recurring themes (词频统计)
- 计算 confidence (信号数量 × 强度 × 来源多样性)
- 生成 next steps (基于 confidence 分级: ≥7 创建机会, ≥4 进一步调研, <4 持续观察)

### Usage

```bash
# 零输入
ode explore

# 指定源
ode explore --hn-top 50 --reddit "startup,SaaS,MachineLearning"

# 带种子关键词（缩小范围）
ode explore --keywords "education,learning"

# 保存结果
ode explore --output explore-report.md
```

---

## Module 2: Bridge (信号→评分桥接)

**用户状态**："我有信号了，但不知道怎么给 18 项评分打分"

**设计思路**：

传统评估要求用户手动为 18 个标准打 1-10 分。这对第一次用的人是巨大的认知负担。Bridge 从已有数据（信号、市场数据、财务数据）自动推断初始评分。

### Inference Rules

每个标准有独立的推断规则：

| Criterion | Data Source | Inference Logic |
|-----------|------------|-----------------|
| tam_size | 市场数据 or 信号量 | TAM≥$1B→10, ≥$100M→7, else 信号数/来源多样性 |
| growth | 信号 momentum | avg momentum >50%→9, >30%→7, >10%→5 |
| timing | 信号强度分布 | 强信号≥5→9, ≥2→7, 中信号≥5→5 |
| intensity | 竞争关键词 | 检测 "vs", "alternative", "switch from" |
| pain_evidence | 痛点关键词 | 检测 "frustrated", "broken", "need", "wish" |
| system_rethink | AI 关键词密度 | AI信号占比 >50%→8, >20%→6 |
| ltv_cac | 财务数据 | 直接从 LTV/CAC ratio 映射 |
| margin | 财务数据 | 毛利率映射 |
| payback | 财务数据 | 回收月数映射 |

### Confidence Levels

每个推断的分数带有置信度标签：

- `data`: 来自真实数据（市场数据、财务模型）
- `auto`: 来自启发式推断（信号分析、关键词检测）

```
| tam_size    | 7/10  | [ data ] | TAM=$500M |
| growth      | 5/10  | [ auto ] | avg momentum 15% |
| pain_evidence| 3/10 | [ auto ] | no pain signals |
```

用户可以只覆盖不信任的分数：`ode eval <id> --scores '{"pain_evidence": 8}'`

### Auto-Trigger

Bridge 在 `eval_worker` 中自动触发：当用户没有提供 `--scores` 时，从信号自动推断。用户完全无感知。

---

## Module 3: Reframe (转型建议)

**用户状态**："评分是 MAYBE/KILL，然后呢？"

**设计思路**：

传统评估工具的 KILL 是个终点。但实际上，很多好想法只是 **定位错误** 而非 **方向错误**。Reframe 针对每个弱势维度给出具体的转型策略。

### Strategy Database

按维度组织，每个策略有触发条件、描述和行动项：

```
Market Attractiveness:
  - TAM too small → "Niche Down": target micro-segment, price 3-5x
  - Growth too slow → "Ride Adjacent Wave": find AI/regulation/demographic shifts
  - Bad timing → "Create Urgency": launch alongside events, trending topics

Competitive Landscape:
  - Too competitive → "Asymmetric Entry": 10x cheaper or simpler
  - No moat → "Build Community Moat": community > code

Capability Fit:
  - Skill mismatch → "Partner or Reposition"
  - Too long to build → "Shrink the V1": one user, one problem

Economic Viability:
  - High CAC → "Flip Acquisition Model": content/SEO over paid ads
  - Low margin → "Move Up Value Chain": charge for outcomes, not access

Validation:
  - No pain evidence → "Pain Discovery Sprint": community posts + interviews
  - No WTP → "Pre-sell Before Building": landing page + deposit

AI-Native:
  - Low rethink → "Rethink the Workflow": design as if AI existed from day 1
```

### 与 Synthesize 的协作

`ode insights` 同时运行 synthesize 和 reframe：

1. synthesize 发现矛盾和盲区 → 告诉用户"你的数据不自洽"
2. reframe 基于弱势维度给出建议 → 告诉用户"如果想救活这个想法，试试这些"

---

## Module 4: Synthesize (交叉分析)

**用户状态**："数据都有了，但感觉哪里不对"

**设计思路**：

人类不擅长发现自己数据中的矛盾。Synthesize 做的是"第二双眼睛"——交叉比对不同维度的数据，找出不一致的地方。

### Contradiction Detection Rules

| # | Pattern | What It Means |
|---|---------|---------------|
| 1 | 大市场 + 弱痛点 | 可能是 nice-to-have in a big space |
| 2 | 高 LTV/CAC + 未验证 WTP | 财务模型可能是愿望，不是现实 |
| 3 | 强信号 + 无竞争 | 空市场警告：可能有隐藏壁垒 |
| 4 | 高 AI 潜力 + 低能力匹配 | 会变成 wrapper，不是 platform |
| 5 | 高分 + redline KILL | 致命缺陷可修复，不要直接放弃 |

### Blind Spot Detection

| Check | Severity | Trigger |
|-------|----------|---------|
| 无市场数据 | High | tam == 0 |
| 无财务模型 | High | ltv == 0 |
| 无 MVT 验证 | High | mvt_result ≤ 2 |
| 无信号 | Medium | signals empty |
| 单源信号 | Medium | only 1 source |
| 监管领域未评估 | High | domain ∈ regulated AND no regulatory risks |

### Auto-Append to Reports

`report_worker` 自动将 synthesize 结果附加到生成的报告末尾。用户不需要单独运行 `ode insights`，报告中就能看到矛盾和盲区。

---

## Design Trade-offs

### 为什么不用 LLM 做启发？

| Approach | Pros | Cons |
|----------|------|------|
| Rule-based (当前) | 可预测、可测试、零成本、离线可用 | 创意有限、需手动维护规则 |
| LLM-powered (未来) | 更有创意、更个性化 | 不可预测、有成本、需 API |

当前选择 rule-based 因为：
1. 工具面向朋友分享，不能假设他们有 API Key
2. 规则可测试，58 个测试全覆盖
3. 留好接口，未来加 LLM 只需换实现

### 为什么 Bridge 不直接替代手动评分？

Bridge 的推断只是起点，不是终点。原因：
1. 有些标准（如 `willingness_to_pay`）本质上无法从信号推断
2. 自动评分有系统性偏差（如总是对 SaaS 乐观）
3. 用户参与打分过程本身就有价值（迫使思考）

---

## Future Directions

1. **LLM Reframe**：用 Claude/GPT 生成更有创意的转型建议
2. **Cross-Opportunity Synthesis**：在 portfolio 层面发现模式（"你的 3 个机会都缺乏 WTP 验证"）
3. **Temporal Analysis**：信号趋势变化检测（一周前还是 emerging，现在变 strong）
4. **User Profile Adaptation**：基于用户技能/资源自动调整 Capability Fit 评分
