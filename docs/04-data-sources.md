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
| `producthunt_feed` | active | `ode pain` with Product Hunt enabled | recent Product Hunt launches from the public Atom feed | solution-side launch bias |
| `google_trends` | optional | `--keywords` plus optional `pytrends` dependency | search interest and rising queries | seed-keyword dependent |

`ode scan` and `ode explore` call HN, Reddit, and optional Trends. `ode pain` calls HN, Reddit, and Product Hunt, then grades signals before ranking founder fit and grouping candidates into validation queues.

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

## Mainstream Coverage Map

Mainstream platforms are covered first as a registry map, then promoted to active scanners only after access, compliance, and tests are clear.

| Area | Registered Sources | Runtime Status |
|------|--------------------|----------------|
| Global video/social | `youtube_data_api_search`, `tiktok_research_api`, `instagram_graph_hashtag_api`, `x_recent_search_api` | planned |
| Global paid demand | `meta_ads_library_api`, `amazon_product_advertising_api`, `linkedin_marketing_api` | planned |
| Global launches/apps | `producthunt_feed`, `producthunt_graphql`, `apple_itunes_search_api`, `google_play_developer_reviews` | active/planned |
| Global market intelligence | `crunchbase_paid`, `sensor_tower_paid`, `similarweb_paid`, `g2_manual`, `capterra_manual`, `indiehackers_manual` | planned/manual |
| China content/social | `cn_douyin_video_search_api`, `cn_kuaishou_open_platform`, `cn_bilibili_ranking`, `cn_weibo_hot_search`, `cn_zhihu_hot`, `cn_xiaohongshu_manual`, `cn_wechat_channels_assistant_manual` | planned/manual |
| China ecommerce/local | `cn_taobao_open_platform`, `cn_jd_open_platform`, `cn_pdd_open_platform`, `cn_1688_open_platform`, `cn_douyin_ecommerce_open_api`, `cn_kuaishou_ecommerce_open_api`, `cn_meituan_open_platform`, `cn_ele_me_open_platform`, `cn_wechat_store_api`, `cn_xiaohongshu_ark_order_api` | planned |

Coverage rule: a mainstream source can exist in the catalog even when it is not automated. The registry is the truth about coverage; `used_by_scan_workers` is the truth about what currently runs.

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
| `cn_xiaohongshu_ark_order_api` | planned | authorized merchant order/revenue proof |
| `cn_xiaohongshu_miniapp_platform` | planned | owned Xiaohongshu mini-app funnel signals |
| `cn_douyin_video_search_api` | planned | approved official Douyin video search signal |
| `cn_douyin_open_video_data` | planned | authorized owned-account Douyin video metrics |
| `cn_douyin_ecommerce_open_api` | planned | authorized Douyin shop order/revenue proof |
| `cn_kuaishou_open_platform` | planned | official Kuaishou short-video/account signals |
| `cn_kuaishou_ecommerce_open_api` | planned | authorized Kuaishou shop revenue proof |
| `cn_taobao_open_platform` | planned | authorized Taobao/Tmall product/order signals |
| `cn_jd_open_platform` | planned | authorized JD SKU/order signals |
| `cn_pdd_open_platform` | planned | authorized Pinduoduo goods/order signals |
| `cn_1688_open_platform` | planned | B2B supply-side signals |
| `cn_meituan_open_platform` | planned | local service merchant/order signals |
| `cn_ele_me_open_platform` | planned | food delivery merchant/order signals |
| `cn_dewu_manual` | manual | youth marketplace price and demand snapshots |
| `cn_wechat_channels_assistant_manual` | manual | owned WeChat Channels backend snapshots |
| `cn_wechat_channels_miniapp_api` | planned | owned WeChat Channels / mini-program connection signals |
| `cn_wechat_store_api` | planned | authorized WeChat Store order/revenue proof |
| `cn_wechat_public_manual` | manual | expert and B2B vertical narratives |
| `cn_baidu_index` | manual | China search interest |
| `cn_wechat_index` | manual | WeChat ecosystem interest |
| `cn_douban_group_manual` | manual | niche lifestyle/community pain |

## Restricted Social Commerce Platforms

Xiaohongshu, Douyin, and WeChat Channels are high-value opportunity sources, but they should not be treated as ordinary open feeds.

| Platform | Broad Public Discovery | Owned/Authorized Data | Best Current Use |
|----------|------------------------|-----------------------|------------------|
| Xiaohongshu | manual only in this project | Ark merchant order API and mini-app platform are planned | consumer language, ecommerce revenue proof, owned funnel tests |
| Douyin | planned only through approved official search capability | open video data requires user authorization | short-video demand discovery, owned content validation |
| WeChat Channels | manual only in this project | Channels Assistant, mini-program capabilities, and Store APIs are scoped to owned/authorized accounts | private-domain validation, livestream/content review, store revenue proof |

Implementation rule: do not promote a restricted platform source to `active` until the adapter uses an official or explicitly authorized access path, stores only the minimum auditable fields, and has tests for rate limits, redaction, and failure modes.

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

Listen for pain signals and solution-side Product Hunt proxies:

```bash
python -m ode pain --reddit "SaaS,SideProject,microsaas,webdev" --hn-top 50 --min-grade D
```

`ode pain` treats Product Hunt as a solution-side source: even explicit launch-copy pain is capped below primary community evidence until a Reddit/HN/user quote confirms the painful job. It also downranks launch and success-story posts so revenue claims stay in the separate `ode cases` workflow.

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
