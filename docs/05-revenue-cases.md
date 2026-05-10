# Revenue Cases

Revenue cases answer a different question than trend signals.

- `sources` asks: where can ODE look for signals?
- `scan` asks: what is happening now?
- `cases` asks: who appears to have made money, how strong is the proof, and should this become a model for us?

## Evidence Grades

| Grade | Meaning | Examples |
|-------|---------|----------|
| A | Audited or exchange-grade primary proof | audited filing, exchange disclosure |
| B | Formal company disclosure plus strong corroboration | public-company business update, signed contract, payment proof |
| C | Company-originated or founder-originated claim | press release, founder interview, investor article |
| D | Estimate or weak institutional signal | analyst estimate, data-platform estimate, government promotion |
| E | Unverified social proof | screenshots, rumors, reposts |

Funding, valuation, downloads, users, and traffic are not revenue. GMV and gross sales are revenue-adjacent and must be converted into net revenue, take-rate, refunds, and margins before they can guide build decisions.

## Workflow

1. Broad scan for cases that appear to have monetized.
2. Grade evidence before ideation.
3. Keep weak but interesting cases on a watchlist rather than deleting them too early.
4. Translate only verified or promising cases into ODE opportunities.
5. Apply Founder Fit Lens to decide whether to build, validate, watch, or research.

## China-Specific Rule

Government and state-media material can be useful for policy direction, procurement language, and regulatory timing. It should not be treated as market proof or revenue proof unless it contains contract amount, payer, supplier, delivery scope, and independent payment or fulfillment evidence.

## Commands

Analyze the seeded case file:

```bash
python -m ode cases
```

Filter to China cases with evidence grade B or above:

```bash
python -m ode cases --region china --min-grade B
```

Use a founder profile:

```bash
python -m ode cases --profile examples/profiles/open_founder_profile.json --top 5
```

Get JSON:

```bash
python -m ode --json cases --region global --min-grade C
```

## Seed Cases

The default file lives at [`examples/revenue_cases/seed_cases.json`](../examples/revenue_cases/seed_cases.json). These are not final investment recommendations; they are auditable examples for practicing the scan -> filter -> verify -> fit workflow.
