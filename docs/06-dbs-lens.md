# DBS Lens Integration

ODE includes a lightweight DBS Lens for business diagnosis:

- goal clarification before scoring;
- business-machine checks for product, price, buyer, acquisition, delivery, and revenue;
- concept deconstruction for fuzzy terms such as personal brand, private traffic, track, and moat;
- copyability scoring for revenue-proven cases.
- a Chinese-first `ode dbs` diagnostic chain that runs goal clarification, language deconstruction, business-model audit, evidence audit, and action judgment in one pass.

This implementation is method-compatible and deterministic. It does not vendor prompts, knowledge atoms, or skill files from `dontbesilent2025/dbskill`.

## Attribution And License Boundary

The design was informed by the public [`dontbesilent2025/dbskill`](https://github.com/dontbesilent2025/dbskill) repository. That repository is licensed under CC BY-NC 4.0, so ODE does not embed its knowledge base, prompt bodies, or `atoms.jsonl`.

Commercial users who want to import the original dbskill knowledge base should obtain separate authorization from the dbskill author and then use a future bring-your-own-licensed-knowledge import path.

## Operational Rule

DBS Lens findings are advisory in v1. They do not automatically change ODE gate verdicts. A saved diagnosis is shown in `ode show`, `ode insights`, and generated reports so the operator sees business-model blockers before trusting scores.

## Interaction Contract

For real applications, prefer the full `ode dbs` diagnostic chain before any isolated lens. The single-purpose commands (`clarify`, `diagnose`, `deconstruct`) are useful for debugging or focused follow-up, but they should not replace the interaction process.

DBS tools must behave as multi-turn dialogue loops. A CLI or automation run can
simulate the dialogue by recording explicit missing questions, but it should not
silently turn missing facts into polished assumptions.

The loop is not "ask N questions and stop." It is an internal two-role debate:

- **Opportunity Builder** proposes the strongest concrete buyer, offer, price,
  channel, delivery path, and validation action.
- **DBS Challenger** attacks vague words, missing payment proof, copied market
  claims, delivery risk, legal risk, and generated artifact conflicts.
- **Decision Judge** stops or continues the loop based on convergence.

Use a small maximum round count only as a safety cap. The real stop condition is
semantic:

- continue if the builder changes the core hypothesis after challenge;
- continue if the challenger finds a new critical missing fact;
- continue if buyer, payment ask, legal path, delivery path, or artifact decision is vague;
- stop when no new critical objection appears and the next market action has a
  buyer list, payment ask, pass/fail criterion, owner, and artifact decision;
- at the cap, downgrade to `clarify_before_scoring`, `validate_payment`, or
  `Watch` rather than forcing `Build Now`.

The application layer should preserve this order:

1. Route the user intent to the relevant diagnostic roles.
2. Dissolve vague or non-checkable language before giving advice.
3. Require product, price, buyer, acquisition, delivery, and revenue proof before scoring.
4. Treat traffic, followers, funding, trend heat, and praise as non-revenue until tied to payment.
5. Surface conflicts, assumptions, and unresolved questions before narrowing.
6. End with a market action that can be executed within 24-48 hours.

If key facts are missing, the correct behavior is to ask for or record the missing facts. Do not silently fill gaps with a polished plan.

## Generated Artifact Governance

DBS outputs often become reports, maps, validation scripts, or shareable plans.
Those files are governed artifacts. Before creating or updating one, the runtime
or operator should:

1. inspect the target directory and intended path;
2. search for existing or superseded artifacts with the same purpose;
3. classify conflicts as same artifact, material alternative, confusing name, or user-authored file;
4. update only generated artifacts with explicit overwrite intent;
5. create a versioned sibling for alternatives;
6. block overwrite when ownership is ambiguous;
7. record source inputs, status, owner, and verification commands.

The helper `ode.core.artifacts.plan_artifact_write` provides a deterministic
pre-write decision for new generated files.

For Chinese-language commercial work, prefer:

```bash
python -m ode dbs --text "传媒公司老板想做出海商业尝试" --opp-id <id> --product ... --price ... --buyer ... --acquisition ... --delivery ... --monthly-revenue ...
```
