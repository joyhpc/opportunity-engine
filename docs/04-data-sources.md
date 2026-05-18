# Data Sources

ODE source coverage has two layers:

1. The source registry: everything the project has named, classified, or planned.
2. Runtime contexts: the much smaller set that code actually calls today.

The registry lives in [`sources/opportunity_sources.yaml`](../sources/opportunity_sources.yaml). Do not infer runtime coverage from registry presence alone.

## Current Registry Snapshot

As of this audit pass, the catalog contains 66 entries.

| Status | Count | Meaning |
|---|---:|---|
| `active` | 3 | Has an adapter and at least one runtime context. |
| `optional` | 1 | Can run only when optional dependency and seed input exist. |
| `manual` | 11 | Human-curated local signal path. |
| `planned` | 50 | Coverage target only; not scanned. |
| `utility` | 1 | Helper source, not part of scan contexts today. |

Region labels currently include 41 China entries, 16 global entries, and 9 entries without a region label.

## Runtime Contexts

These contexts are the operational truth.

| Context | Called By | Sources |
|---|---|---|
| `scan_worker` | `ode scan` | `hackernews_topstories`, `reddit_hot_rss`, optional `google_trends` |
| `explore` | `ode explore` | `hackernews_topstories`, `reddit_hot_rss`, optional `google_trends` |
| `pain_listener` | `ode pain`, `ode daily` | `hackernews_topstories`, `reddit_hot_rss`, `producthunt_feed` |

`producthunt_feed` is active only for pain listening. It is not a `scan_worker` source.

`google_trends` is optional. It requires keywords and the optional Google Trends client path to work.

## Active And Optional Sources

| Source ID | Status | Adapter | Best For | Main Bias |
|---|---|---|---|---|
| `hackernews_topstories` | active | `ode.tools.sources.hackernews.scan` | Developer, infrastructure, AI engineering, technical early-adopter demand. | Strong technical bias; weak mainstream consumer coverage. |
| `reddit_hot_rss` | active | `ode.tools.sources.reddit.scan` | Community pain, user language, early validation topics. | Depends heavily on subreddit choice; noisy. |
| `producthunt_feed` | active | `ode.tools.sources.producthunt.scan` | Startup launches, indie AI tools, competitor language. | Launch attention is not revenue or primary pain proof. |
| `google_trends` | optional | `ode.tools.sources.google_trends.scan` | Search-interest timing and keyword expansion. | Seed-keyword dependent; optional dependency may be unavailable. |

## Manual Sources

Manual sources are valid evidence paths when the operator stores auditable notes, URLs, screenshots, or exports as local signals. They are not crawlers.

Examples:

- `manual_signal`
- `g2_manual`
- `capterra_manual`
- `indiehackers_manual`
- `cn_xiaohongshu_manual`
- `cn_wechat_public_manual`
- `cn_wechat_channels_assistant_manual`
- `cn_baidu_index`
- `cn_wechat_index`

Manual evidence should include source URL, timestamp or date range, extraction note, and why it matters.

## Planned Sources

Planned entries are visibility markers. They prevent the team from forgetting important platforms, but they do not affect scoring until an adapter and tests exist.

Examples:

- `github_trending`
- `arxiv_recent`
- `funding_news`
- `youtube_data_api_search`
- `tiktok_research_api`
- `x_recent_search_api`
- `meta_ads_library_api`
- `apple_itunes_search_api`
- `google_play_developer_reviews`
- `cn_36kr_newsflash`
- `cn_v2ex_hot`
- `cn_zhihu_hot`
- `cn_weibo_hot_search`
- `cn_government_procurement`
- `cn_taobao_open_platform`
- `cn_douyin_ecommerce_open_api`
- `cn_wechat_store_api`

Promotion rule:

1. Add or confirm registry metadata.
2. Implement an adapter under `ode/tools/sources/` or another explicit tools module.
3. Add context dispatch tests.
4. Add failure-mode tests for HTTP errors, malformed responses, and empty results.
5. Only then mark it `active` and add runtime context.

## Restricted Platforms

Xiaohongshu, Douyin, Kuaishou, WeChat Channels, and ecommerce order APIs can be valuable but should not be treated as ordinary public feeds.

Rules:

- Use official or explicitly authorized access paths.
- Prefer owned-account, merchant, order, or authorized backend data when possible.
- Store minimum auditable fields.
- Add tests for rate limits, redaction, malformed responses, and access failures.
- Do not scrape private or login-restricted data as a normal runtime source.

Best current use:

| Platform Type | Current ODE Treatment |
|---|---|
| Public social/content feeds | Mostly planned or manual. |
| Owned account analytics | Manual or planned authorized API. |
| Merchant/order proof | Planned authorized API. |
| Screenshots/exports | Manual signal with source notes. |

## Commands

List all configured sources:

```bash
python -m ode sources
```

List active runtime sources:

```bash
python -m ode sources --status active
```

List China-focused registry entries:

```bash
python -m ode sources --region china
```

Get JSON:

```bash
python -m ode --json sources --region global
```

Run a scan using runtime scan sources:

```bash
python -m ode scan --keywords "AI agents,developer tools" --hn-top 50 --reddit "startup,SaaS,MachineLearning"
```

Listen for pain signals:

```bash
python -m ode pain --reddit "SaaS,SideProject,microsaas,webdev" --hn-top 50 --min-grade D
```

## Signal Fields

Runtime signals should preserve:

| Field | Meaning |
|---|---|
| `source_id` | Stable registry id, such as `hackernews_topstories`. |
| `source` | Display/source detail, such as `reddit/r/SaaS`. |
| `title` | Primary text used for clustering and scoring. |
| `url` | Source URL when available. |
| `strength` | Adapter-normalized relative strength. |
| `momentum` | Source-specific momentum or engagement proxy. |
| `relevance_score` | Aggregate keyword relevance when applicable. |
| `raw_data` | Original adapter fields where preserved. |

When comparing strength values, use the code helpers instead of hand-typing literal strings; some legacy display literals are historical and should not become a new public contract.

## Design Rule

Discovery should stay broad, but every signal must be traceable. If a source is not in the registry and not tied to a runtime context or manual note, it should not influence scoring or alerts.
