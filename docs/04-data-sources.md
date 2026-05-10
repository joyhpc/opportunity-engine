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

## Commands

List all configured sources:

```bash
python -m ode sources
```

List only active runtime sources:

```bash
python -m ode sources --status active
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
