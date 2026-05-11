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

## Entry Fit Rule

For a solo founder or small team, evidence grade is market proof, not build permission.

| Case Type | Use It For | Default Action |
|-----------|------------|----------------|
| A-grade incumbent | Proves a budget pool, buyer language, and timing | Treat as a market map; look for adjacent B/C wedges |
| B-grade order or formal disclosure | Shows money is moving before the category is fully locked | Prioritize if entry fit and founder fit are workable |
| C-grade company or founder claim | Good early signal with verification risk | Validate quickly before building |
| D/E trend or weak proof | Discovery value only | Keep on watchlist unless stronger proof appears |

The preferred early-stage pattern is:

```text
B/C revenue evidence + commodity or existing hardware + messy workflow + software wedge that can be validated within 30 days
```

Avoid treating this as attractive just because the evidence is strong:

```text
A-grade revenue evidence + incumbent scale + heavy capital, inventory, certification, or long procurement
```

## Quiet Money Rule

Many profitable opportunities are quiet because the seller is a small operator, channel partner, integrator, agency, dealer, or vertical workflow vendor. Do not rely only on press releases, funding news, launch rankings, or viral posts.

Use a second score, `quiet_money_score`, to catch low-publicity money:

| Signal Type | Examples | Interpretation |
|-------------|----------|----------------|
| Hard payment trace | invoice, receipt, signed contract, paid pilot, renewal | Strong quiet-money evidence |
| Operational trace | procurement listing, dealer quote, implementation job, maintenance demand, rental booking, repeat order | Useful when repeated across sources |
| Channel trace | reseller pages, marketplace order history, niche forum buyer posts, integrator case notes | Good discovery signal, verify before build |
| Vanity trace | funding, downloads, press, traffic, viral posts | Context only, not quiet money |

Default rule:

```text
One hard payment trace OR three independent operational/channel traces can enter Quiet Candidate.
Quiet Candidate still needs repeatability proof before build commitment.
```

For hardware-adjacent AI, quiet opportunities often appear around the hardware rather than inside the hardware:

```text
installation, rental, maintenance, data labeling, workflow automation, compliance reports, accessories, templates, operator training
```

## Workflow

1. Broad scan for cases that appear to have monetized.
2. Grade evidence before ideation.
3. Classify A-grade incumbents as market maps unless there is a clear lightweight wedge.
4. Prioritize B/C cases when they have workable entry fit and founder fit.
5. Promote low-publicity cases to Quiet Candidate only when payment or repeated operational traces exist.
6. Keep weak but interesting cases on a watchlist rather than deleting them too early.
7. Translate only verified or promising cases into ODE opportunities.
8. Apply Founder Fit Lens to decide whether to build, validate, watch, or research.

## China-Specific Rule

Government and state-media material can be useful for policy direction, procurement language, and regulatory timing. It should not be treated as market proof or revenue proof unless it contains contract amount, payer, supplier, delivery scope, and independent payment or fulfillment evidence.

## Commands

Analyze the seeded case file:

```bash
python -m ode cases
```

Bootstrap the initial warning system from the case library:

```bash
python -m ode init-alerts --min-grade C --profile examples/profiles/open_founder_profile.json --reset
```

This learns case priors, seeds `data/alerts/watchlist.yaml`, writes `data/alerts/case_priors.yaml`, and creates an initial report under `data/reports/initial/`.

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
