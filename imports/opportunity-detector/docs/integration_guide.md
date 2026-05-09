# project-tracker 集成指南

机会探测器作为 pt 的流程模板运行，完全复用 pt 的 DAG 引擎、决策登记簿和验证追踪能力。

## 安装流程模板

```bash
# 将模板复制到 pt 的 flows 目录
cp templates/opportunity_detector.yaml ~/project-tracker/tracker/flows/

# 将子任务模板复制到 subtasks 目录
cp subtasks/*.yaml ~/project-tracker/tracker/flows/subtasks/
```

## 创建项目

```bash
cd ~/project-tracker

# 创建新的机会评估项目
python3 pt init my-idea --name "我的创业想法" --flow opportunity_detector

# 查看状态
python3 pt status

# 可视化 DAG
python3 pt map
python3 pt map --html  # HTML 版本
```

## 日常使用

### 推进任务
```bash
# 开始一个任务
python3 pt start signal_capture

# 完成任务
python3 pt done signal_capture

# 跳过任务（Kill 时批量跳过）
python3 pt skip mvp_design mvp_execution data_analysis
```

### 记录决策
```bash
# 在门禁处记录 Go/Kill 决策
python3 pt decision --add "Go: 市场规模 > $500M, LTV/CAC = 4.2x" \
    --source "初筛评分卡" \
    --impact "进入深度分析阶段"

# Kill 决策
python3 pt decision --add "Kill: TAM < $10M, 不值得投入" \
    --source "market_sizer.py 输出" \
    --impact "项目终止, 学习记录归档"
```

### 追踪假设验证
```bash
# 添加需要验证的假设
python3 pt poc --add "用户愿意为AI编程教育付费$20/月" \
    --metric "落地页转化率 > 5%"

python3 pt poc --add "获客成本 < $50" \
    --metric "前100个用户的平均CAC"
```

### 多机会并行

```bash
# 创建多个机会项目
python3 pt init idea-a --name "想法A: SaaS工具" --flow opportunity_detector
python3 pt init idea-b --name "想法B: 咨询服务" --flow opportunity_detector
python3 pt init idea-c --name "想法C: 教育平台" --flow opportunity_detector

# 切换项目
python3 pt switch idea-a
python3 pt status  # 查看想法A的进度

python3 pt switch idea-b
python3 pt status  # 查看想法B的进度
```

### Kill 一个机会

```bash
# 在门禁处决定 Kill
python3 pt decision --add "Kill: 竞争过于激烈, 无差异化空间" \
    --source "competitor_matrix 分析" \
    --impact "停止投入"

# 跳过所有剩余任务
python3 pt skip $(python3 pt list --status pending --ids-only)
```

## 与 Python 工具集成

工具脚本输出 Markdown，可直接用于 pt 决策记录：

```bash
# 生成评分卡并记录决策
python3 ~/AGENT_COMMU_HighValue/tools/opportunity_scorer.py --demo -o scorecard.md

# 将结果关联到 pt 决策
python3 pt decision --add "初筛评分 72/100, Go" \
    --source "scorecard.md" \
    --impact "进入 ANALYZE 阶段"

# 财务模型输出
python3 ~/AGENT_COMMU_HighValue/tools/financial_model.py --demo -o financial.md
```

## 自定义流程

pt 的 DAG 支持动态修改：

```bash
# 添加自定义节点
python3 pt add --id regulatory_check --name "法规合规检查" \
    --phase ANALYZE --depends ms_screen

# 重新连接依赖
python3 pt rewire financial_model --depends regulatory_check value_chain risk_assessment

# 删除不需要的节点
python3 pt rm patent_tech_scan  # 如果不涉及技术机会
```

## 文件结构

```
~/project-tracker/
├── tracker/flows/
│   ├── opportunity_detector.yaml    ← 流程模板
│   └── subtasks/
│       ├── signal_capture.yaml      ← SENSE 子任务
│       ├── market_screening.yaml    ← SCREEN 子任务
│       ├── deep_analysis.yaml       ← ANALYZE 子任务
│       ├── validation.yaml          ← VALIDATE 子任务
│       └── business_planning.yaml   ← PLAN 子任务
└── projects/
    └── my-idea.yaml                 ← 项目状态文件
```
