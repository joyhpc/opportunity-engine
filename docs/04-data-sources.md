# Data Sources

ODE 的机会发现分两层：

1. **已接入扫描源**：运行时 worker 真的会调用。
2. **来源注册表**：把 active、optional、utility、manual、planned 都列出来，避免误以为系统已经在扫全网。

注册表在 [`sources/opportunity_sources.yaml`](../sources/opportunity_sources.yaml)。

## Current Runtime Sources

| Source ID | Status | Trigger | What It Captures | Main Bias |
|-----------|--------|---------|------------------|-----------|
| `hackernews_topstories` | active | `--hn-top > 0` | HN top stories through Firebase API | technical early adopters |
| `reddit_hot_rss` | active | `--reddit "sub1,sub2"` | subreddit hot RSS posts | noisy community language |
| `google_trends` | optional | `--keywords` plus optional `pytrends` dependency | search interest and rising queries | seed-keyword dependent |

`ode scan` and `ode explore` currently call only those runtime sources.

## Utility And Manual Sources

| Source ID | Status | Purpose |
|-----------|--------|---------|
| `duckduckgo_instant_answer` | utility | future lightweight evidence lookup; not used by scan workers today |
| `manual_signal` | manual | curated funding, interview, user, or news signals stored as local `Signal` entities |

## Planned Sources

| Source ID | Why It Matters |
|-----------|----------------|
| `arxiv_recent` | catches research inflection points before commercial products appear |
| `github_trending` | catches developer adoption and open-source momentum |
| `funding_news` | catches capital flow, category formation, and new competitors |

Planned sources are intentionally visible but not counted as scanned until an adapter exists and tests pass.

## China-Focused Sources

这些源先进入注册表，不代表都已经自动扫描。国内平台公开 API 不稳定、登录限制多、平台条款差异大，所以先按可审计目录管理，后续逐个挑选成 adapter。

| Source ID | Status | Signal Type |
|-----------|--------|-------------|
| `cn_36kr_newsflash` | planned | startup launches, funding, tech news |
| `cn_huxiu_articles` | planned | China tech narratives |
| `cn_tmtpost_news` | planned | platform and enterprise tech news |
| `cn_cyzone_news` | planned | startup and financing news |
| `cn_iyiou_industry` | planned | industry digitization |
| `cn_itjuzi_funding` | planned | funding database, likely paid/manual |
| `cn_qimingpian_funding` | planned | funding database, likely paid/manual |
| `cn_qichacha_company` | planned | company and competitor verification |
| `cn_tianyancha_company` | planned | company and competitor verification |
| `cn_juejin_hot` | planned | developer/building signals |
| `cn_oschina_news` | planned | open-source and enterprise software |
| `cn_v2ex_hot` | planned | indie/developer community pain |
| `cn_zhihu_hot` | planned | public attention and consumer questions |
| `cn_weibo_hot_search` | planned | public attention spikes |
| `cn_bilibili_ranking` | planned | content and youth consumer interest |
| `cn_gov_policy` | planned | policy tailwinds and regulation |
| `cn_miit_policy` | planned | industrial internet, AI, software policy |
| `cn_stats_data` | planned | macro/TAM sanity checks |
| `cn_government_procurement` | planned | B2G budget-backed demand |
| `cn_xiaohongshu_manual` | manual | consumer desire and purchase language |
| `cn_wechat_public_manual` | manual | expert and B2B vertical narratives |
| `cn_baidu_index` | manual | China search interest |
| `cn_wechat_index` | manual | WeChat ecosystem interest |
| `cn_douban_group_manual` | manual | niche lifestyle/community pain |

Selection rule: promote sources to `active` only after adapter behavior, access stability, and tests are clear.

## Commands

List all configured sources:

```bash
python -m ode sources
```

List only active runtime sources:

```bash
python -m ode sources --status active
```

List China-focused sources:

```bash
python -m ode sources --region china
```

Get JSON:

```bash
python -m ode --json sources
```

Run a scan using current runtime sources:

```bash
python -m ode scan --keywords "AI agents,developer tools" --hn-top 50 --reddit "startup,SaaS,MachineLearning"
```

## Signal Audit Fields

Signals produced by runtime scanners should include:

| Field | Meaning |
|-------|---------|
| `source_id` | stable registry id, for example `hackernews_topstories` |
| `source` | display/source detail, for example `reddit/r/SaaS` |
| `title` | signal text |
| `url` | source URL when available |
| `strength` | `强`, `中`, or `弱` |
| `momentum` | source-specific momentum metric |
| `relevance_score` | keyword match score added during aggregate scan |

## Design Rule

Discovery should stay open, but every signal must be traceable. If a source is not in the registry, it should not silently influence scoring.
