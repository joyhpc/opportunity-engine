# AI Hardware DBS Workflow

AI hardware scans must be map-first, not shortlist-first. The goal is to avoid
missing capital-light opportunities in upstream hardware, supply-chain,
channel, integration, rental, repair, or workflow layers.

Run the workflow contract with:

```bash
python -m ode ai-hardware --region shenzhen
```

## DBS Placement

DBS is used at multiple points:

| Stage | DBS Tool | Purpose |
|-------|----------|---------|
| Boundary | `clarify` | Define region, founder constraints, validation window, and exclusions |
| Language | `deconstruct` | Break fuzzy words like hardware, platform, channel profit, export, integration, and damage estimate into observable jobs |
| Map | DBS protocol | Build all seven value-chain layers before narrowing |
| Evidence | `cases`, `pain`, `daily` | Separate revenue proof, quiet-money traces, and trend-only signals |
| Candidate | `diagnose` | Require product, price, buyer, acquisition, delivery, and revenue facts |
| Action | `dbs` | Turn the finalist into a 24-48 hour payment validation action |

Each DBS placement is multi-turn by default. If the operator is available, the
tool should ask follow-up questions. If the workflow is running unattended, it
must record the missing questions and keep the candidate in
`clarify_before_scoring`, `validate_payment`, or `Watch` instead of inventing
facts.

The dialogue is implemented as role separation, not as a fixed chat length:

| Role | Responsibility |
|------|----------------|
| Opportunity Builder | Make the strongest concrete case for the opportunity |
| DBS Challenger | Attack assumptions, payment evidence, delivery risk, legal risk, and artifact conflicts |
| Decision Judge | Decide continue, validate payment, watch, build, kill, or clarify |

The loop should normally run 2-6 internal rounds. The lower bound ensures the
first challenge is answered. The upper bound is only a safety cap. Stop only when
the challenger has no new critical objection, missing facts are recorded, the
next action has buyer/payment/pass-fail/owner, and artifact handling is decided.
If the cap is reached with unresolved objections, downgrade the candidate instead
of promoting it.

## Seven Layers

Every scan must cover:

1. Hardware body
2. Supply chain / components
3. Channel / trading / distribution
4. Integration / deployment
5. Rental / operations
6. Repair / after-sales
7. Data / compliance / workflow software

Do not assume the founder should only consider software layers. A hardware-body
or channel opportunity can stay alive if the entry mode is capital-light,
deposit-backed, and locally reachable.

## Gates

Candidates are ranked only after these gates:

- Evidence Grade
- Evidence Independence
- Quiet Money
- Entry Fit
- DBS Copyability
- Local Access
- Legal Risk
- Time to Payment

Public ARR, funding, downloads, traffic, or PR claims can prove a market, but
they do not become `Build Now` without local buyer access and payment proof.

## Required Output

An AI hardware opportunity report must include:

- opportunity map before shortlist;
- DBS builder/challenger dialogue and recorded missing facts at each stage;
- dialogue stop policy result: continue, validate payment, watch, build, kill, or clarify;
- ranked opportunities with DBS verdicts;
- excluded or capped opportunities with reasons;
- evidence type and independence per candidate;
- generated artifact governance and conflict decision before new files;
- 24-48 hour validation actions with pass/fail criteria.

If those sections are missing, the analysis is incomplete.

## Artifact Governance And Conflicts

Any new generated report, map, validation script, rendered file, or shareable
planning document needs a pre-write decision:

| Situation | Decision |
|-----------|----------|
| Target path is empty and no similar artifact exists | Create |
| Existing file is generated and overwrite is explicitly intended | Update |
| Existing file is generated but overwrite is not explicit | Create versioned sibling |
| Existing file looks user-authored or ownership is unclear | Block and report conflict |
| Similar artifact already exists | Version or rename before creation |

Use `ode.core.artifacts.plan_artifact_write` when a workflow is about to create
a file. The decision should be included in the generated output metadata or run
record.
