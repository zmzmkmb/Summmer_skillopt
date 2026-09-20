# ACL 2027 Phase 1Y/1Z New-Conversation Handoff

This document is the compact handoff for a new Codex desktop or CLI task. The
repository remains authoritative: if this document conflicts with
`experiment_state.json`, validated immutable artifacts, or phase reports, use
the repository evidence and repair this document.

## Recommended new-task prompt

```text
Continue the SummerSkillOpt ACL 2027 experiment from repository state, not chat
memory. Read AGENTS.md, paper/acl2027/experiment_state.json,
paper/acl2027/CROSS_CONVERSATION_PROTOCOL.md, and
paper/acl2027/PHASE1_YZ_NEW_CONVERSATION_HANDOFF.md. Because graphify-out/graph.json
exists, use graphify query first for project/architecture questions. Run:

python scripts/acl2027_experiment_handoff.py validate
python scripts/acl2027_experiment_handoff.py status

Resume Phase 1Y immediately. Phase 1 has a hard cap: complete only Phase 1Y and
Phase 1Z, then close Phase 1 with a positive, negative, or inconclusive
conclusion. Do not create Phase 1AA or further preflight micro-phases. Keep all
provider/model calls closed until an exact minimal request plan, immutable
payload hashes, cost estimate, zero-retry contract, and fresh explicit user
authorization exist. Do not rerun completed immutable artifacts or touch
unrelated dirty work. Before ending material work, update the checkpoint, run
cache-free tests, and validate state again.
```

## Authoritative status

- Workspace: the repository root containing this document
- Last completed phase: Phase 1Z
- Current phase: Phase 1Z, completed; Phase 1 is closed
- Paid/provider calls authorized: no
- Formal scaling authorized: no
- Repository validation at handoff: 31 completed phases and 1,068 immutable runs
- Phase 1X authorization is exhausted; it cannot be inherited by Phase 1Y/1Z.

Phase 1X completed exactly 24/24 `qwen3.7-plus` Token Plan attempts with zero
retries and no `max_tokens`. Exact usage was 27,981 input plus 884 output tokens
(28,865 total), locally accounted as CNY 0.063034. SearchQA scored 10/12.
2WikiMultiHopQA scored 7/12 answers, 9/12 support sets, and 6/12 joint successes,
passing the frozen Phase 1T eligibility gate. The analysis fingerprint is
`027b39fd5bf07d98d29590c7bdd35ab00393f61fc33ce37934a888f31b55fcee`.

This establishes substrate eligibility and verified-success availability. It
does not establish the paper's typed-prior, probe-representativeness, or
retention-aware deployment effects.

Phase 1Y executed its exact authorized 10-attempt history plan and then closed
provider permission. Local replay admitted 8 verified trajectories and 3 typed
candidates. Coverage is 3/5: `entity_bridge` and `relation_inference` each have
only one verified supporting trajectory and fail the frozen two-support
candidate contract. No evaluation leakage was found. Exact usage was 12,111
tokens and CNY 0.027228 with zero retries and no `max_tokens`.

Phase 1Z bound those immutable results and performed a zero-provider execution
gate adjudication. The held-out pilot was not scientifically executable, so it
closed as `inconclusive_without_phase1z_provider_execution` with 0 Phase 1Z
provider calls. Phase 1 is closed. The theoretical minimum repair is two
additional successful history calls, but the exact guaranteed request count is
undefined because success cannot be guaranteed; authorized additional calls
remain zero. Do not create another Phase 1 stage or inherit the old 1,152-call
upper bound.

## Hard convergence rule

Phase 1 has exactly two remaining phases:

1. Phase 1Y: verified-history and typed skill-candidate materialization.
2. Phase 1Z: the final real held-out method-effect pilot and Phase 1 conclusion.

Do not create Phase 1AA, 1AB, or separate phases for configuration, runner,
authorization, execution, or analysis. Those are internal steps of 1Y or 1Z.
After 1Z, close Phase 1 regardless of whether results support, refute, or leave
the claim inconclusive. A failed 1Z narrows or revises the paper claim; it does
not trigger another repair phase.

## Phase 1Y

Start with the declared zero-network write scope in `experiment_state.json`.
Bind the frozen SearchQA and 2Wiki history partitions, preserving exclusions for
calibration, probe, held-out, and all spent SearchQA IDs. Materialize only
automatically verified successful trajectories. Every accepted or rejected
candidate must retain deterministic identity, family/type/scope, supporting
task IDs, verifier replay, and provenance/rejection reasons.

Before requesting any model authorization, audit what can be reused from
existing successful histories. Do not assume that all 120 SearchQA plus 120
2Wiki history tasks require new calls. Determine the minimum new calls needed
to produce sufficiently diverse, causally usable typed candidates. Freeze the
exact request count, request hashes, cost estimate/ceiling, zero retries, no
`max_tokens`, resume semantics, and hard stops. Then ask the user for fresh,
explicit authorization. No current authorization permits those calls.

Phase 1Y must fail its route rather than quietly continue if verified candidates
are too few, lack reusable support, leak evaluation IDs, or are dominated by one
task or family. Its completion report must state whether 1Z is scientifically
executable and the exact minimal call plan if provider execution is needed.

## Phase 1Z

Phase 1Z is the final causal pilot, not another protocol-only preflight. Its
frozen design should use the existing disjoint 48 probe tasks and 240 held-out
tasks across SearchQA and 2Wiki, subject to a final power/identifiability audit.
Compare only conditions needed to identify the claims, provisionally:

- cold
- copied-global
- global-only
- contextual typed prior

Reuse paired responses whenever scientifically valid. Do not assume the earlier
rough upper bound of 1,152 Phase 1Z calls is necessary. Establish whether each
condition truly requires a separate provider response and minimize calls while
preserving paired causal identification. Freeze the exact count and cost before
requesting authorization.

Keep the Phase 1T thresholds unless a correction is preregistered before seeing
1Z outcomes:

- Accept: paired mean margin at least +0.125, at least three helpful pairs, and
  no harmful pair.
- Reject: paired mean margin at most -0.125 or at least two harmful pairs.
- Otherwise abstain.
- Recovery: two qualifying later windows for a retained candidate.

## Evidence needed for the paper

Current claim:

> Given verifiable reusable historical successes, typed/scoped skill priors and
> representativeness-aware non-destructive validation improve continual routing
> reliability per cumulative token.

Phase 1Z should report real paired held-out evidence for:

1. Contextual typed priors versus relevant cold/global controls.
2. Effect dispersion across task IDs, task types, and skill families.
3. Representative versus shifted probe sign prediction on held-out effects.
4. Frozen false-safe and false-harm outcomes.
5. Retaining triage versus destructive gating, including useful-candidate
   preservation/recovery and harmful deployments.
6. Exact/joint accuracy, paired margins, cumulative exact tokens, and reward per
   1,000 cumulative tokens by task family.

Do not promise a positive result. Promise a decisive Phase 1 conclusion. Even a
successful pilot is not full ACL evidence: later work would still need multiple
seeds, another model family, fuller statistical analysis, and broader coverage.

## Immutable references

- `configs/acl2027/phase1t_heldout_deployment_identifiability_v1.json`
- `paper/acl2027/results/phase1x_calibration_live_v1.md`
- `artifacts/acl2027_phase1x_calibration_live_v1/analysis_manifest.json`
- `paper/acl2027/CONTRIBUTION_EVIDENCE_LEDGER.md`
- `paper/acl2027/experiment_state.json`

At every material stopping point, run the relevant tests with
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`, update
`experiment_state.json`, and run the handoff validator again.
