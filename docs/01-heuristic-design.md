# Heuristic Design

ODE's heuristics are deterministic helpers around the core opportunity engine. They are not hidden agents, and they should not silently change opportunity state unless a service explicitly saves a result.

## Why Heuristics Exist

The core engine can create, scan, score, gate, and report an opportunity. Real users often need help before and after that linear workflow:

- "I do not know what to build."
- "I found signals, but I do not know how to score them."
- "This looks like a bad score, but maybe the positioning is wrong."
- "This market is hot, but I need to know whether anyone is paying."
- "This fits the market, but does it fit me?"
- "My goal is vague; what exactly can I sell tomorrow?"

Heuristics answer those questions while keeping their assumptions visible.

## Design Rules

1. Prefer deterministic, testable rules over hidden model calls.
2. Return structured data plus formatted reports where useful.
3. Keep mutation in service functions, not in pure heuristic modules.
4. Separate evidence classes: trend, pain, revenue, compliance, inference.
5. Use founder fit as a soft lens, not an early hard filter.
6. Keep high-discovery wildcard opportunities visible as `Watch` or `Research` rather than deleting them too early.

## Module Map

| Module | Primary Commands | Mutates State | Purpose |
|---|---|---:|---|
| `explore.py` | `ode explore` | no | Fetch and cluster open-ended public signals into hypotheses. |
| `bridge.py` | `ode eval` without `--scores` | via eval worker | Infer initial score inputs from signals, market data, and financial data. |
| `pain_listener.py` | `ode pain`, `ode daily` | no | Grade community pain signals and produce validation queues. |
| `revenue_cases.py` | `ode cases`, `ode init-alerts`, `ode daily` | no | Grade revenue evidence and entry fit for reference cases. |
| `daily_warning.py` | `ode daily`, `ode init-alerts` | via warning service | Merge pain, cases, exploration, and portfolio into alerts and watchlist state. |
| `fit_lens.py` | `ode lens` | no | Soft-rank an opportunity by score, founder fit, and discovery value. |
| `synthesize.py` | `ode insights`, `ode report` | no | Detect contradictions and blind spots in stored opportunity data. |
| `reframe.py` | `ode insights` | no | Suggest pivots when an opportunity is below the `GO` range. |
| `dbs.py` | `ode dbs`, `clarify`, `diagnose`, `deconstruct` | only with `--save` | Diagnose commercial clarity, payment proof, language vagueness, and next action. |
| `ai_hardware_workflow.py` | `ode ai-hardware` | no | Provide a map-first workflow contract for AI hardware opportunity scans. |

## Explore

Entry path:

```text
ode explore
  -> services.discovery.explore_signals
  -> heuristics.explore.explore_with_fetch
  -> source_dispatch / trend scanner
  -> cluster_signals
  -> generate_hypotheses
```

Behavior:

- Uses declared runtime sources for the `explore` context: Hacker News, Reddit, optional Google Trends.
- Clusters by domain seed words.
- Classifies demand patterns.
- Produces hypotheses with confidence, themes, signals, and next steps.

This is useful when the user has no specific opportunity yet. It is not a replacement for revenue evidence.

## Bridge

Entry path:

```text
ode eval <opp_id>
  -> eval_worker
  -> if no --scores and signals exist: bridge.infer_scores
  -> OpportunityScorer
```

Bridge turns existing evidence into starting score inputs. It considers:

- signal count and source diversity;
- strength and momentum;
- market and financial data when available;
- pain keywords;
- competition and AI-native indicators.

Bridge output is a starting point. Manual `--scores` remains the way to supply deliberate judgment.

## Pain Listener

Entry path:

```text
ode pain
  -> services.discovery.listen_pains
  -> source_dispatch context "pain_listener"
  -> heuristics.pain_listener.listen
```

Runtime context:

- Hacker News top stories.
- Reddit hot RSS for selected subreddits or defaults.
- Product Hunt feed as solution-side launch evidence.

Rules:

- Reachable pain grades are C, D, and E.
- Product Hunt launch attention is capped until corroborated by user/community pain.
- Launch posts and success stories are downranked.
- Validation queues keep signal tags so the operator knows why an item was retained.

## Revenue Cases

Entry path:

```text
ode cases
  -> services.discovery.analyze_revenue_cases
  -> heuristics.revenue_cases.analyze_revenue_cases
```

Revenue cases answer: who appears to have made money, how strong is the proof, and whether the pattern is entry-fit for a small team.

Evidence grades:

| Grade | Meaning |
|---|---|
| A | Audited or exchange-grade primary proof. |
| B | Formal disclosure, signed contract, payment proof, or strong corroboration. |
| C | Company/founder-originated claim or credible interview. |
| D | Estimate or weak institutional signal. |
| E | Unverified social proof. |

Funding, valuation, downloads, traffic, and PR are not revenue. GMV is revenue-adjacent and needs take-rate, refund, and margin context.

## Daily Warning

Entry path:

```text
ode daily
  -> services.warnings.run_daily_review
  -> pain + cases + optional explore + portfolio
  -> heuristics.daily_warning.update_watchlist
```

Alert levels:

- `New Spark`
- `Watch`
- `Validate Soon`
- `Act Now`

`init-alerts` bootstraps priors from revenue cases. `daily` then updates watchlist state and writes a report under `data/reports/daily/`.

## Founder Fit Lens

Entry path:

```text
ode lens <opp_id>
  -> services.insights.apply_lens
  -> heuristics.fit_lens.apply_fit_lens
```

The lens combines:

- stored opportunity score;
- founder fit from profile terms and constraints;
- discovery value from signal strength, diversity, and unusualness.

Recommendations include `Build Now`, `Validate Soon`, `Watch`, `Research`, and `Ignore`.

The lens does not mutate opportunities and does not replace gates.

## Synthesize And Reframe

Entry path:

```text
ode insights <opp_id>
  -> synthesize
  -> quick_assess when early signals exist
  -> reframe when weighted score is below 70
  -> latest saved DBS diagnostic
```

`synthesize.py` looks for contradictions and blind spots, such as:

- large market but weak pain evidence;
- high economics but missing willingness-to-pay proof;
- strong signals from only one source;
- regulated domain without regulatory assessment.

`reframe.py` suggests positioning changes, adjacent markets, inversions, and narrower wedges when a score is weak.

## DBS Lens

DBS Lens is a deterministic commercial diagnosis layer. It is implemented in `ode/heuristics/dbs.py` and exposed through:

- `ode dbs`
- `ode clarify`
- `ode diagnose`
- `ode deconstruct`

It checks:

- vague language;
- product, price, buyer, acquisition, delivery, and monthly revenue facts;
- non-revenue vanity terms;
- demand and scalability;
- next concrete action.

Saved diagnostics are advisory records on the opportunity. They appear in `show`, `insights`, and generated reports.

## AI Hardware Workflow

`ode ai-hardware` returns a workflow contract, not a market report. It requires map-first scanning across:

1. hardware body;
2. supply chain and components;
3. channel and distribution;
4. integration and deployment;
5. rental and operations;
6. repair and after-sales;
7. data, compliance, and workflow software.

Use this before narrowing to a single AI hardware opportunity.

## Testing Expectations

Important tests:

- `tests/test_heuristics.py`
- `tests/test_pain_listener.py`
- `tests/test_revenue_cases.py`
- `tests/test_daily_warning.py`
- `tests/test_fit_lens.py`
- `tests/test_dbs_lens.py`
- `tests/test_ai_hardware_workflow.py`

After changing heuristic rules, run:

```bash
python -m pytest tests/test_heuristics.py tests/test_pain_listener.py tests/test_revenue_cases.py tests/test_daily_warning.py tests/test_dbs_lens.py
```
