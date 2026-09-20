# Phase 4 Strong-Conclusion Plan

Updated: 2026-08-18

## Phase 4B result (2026-08-18)

The explicitly authorized development calibration completed 100/100
`qwen3.7-plus` calls with zero retries and automatic authorization closure.
All 100 responses were JSON-parseable, but 0/100 satisfied the frozen six-field
evidence-grounded response contract. The required contract-valid rate was
0.95, so the Phase 4B stop rule fired. Phase 4C, replication, cross-domain
testing, and formal scaling remain unauthorized. The strict analysis
fingerprint is
`75f54900bc79b1a9a49f715219b7bfb20571c91a261e71b2e850f9e92713e885`.

## Phase 4B-R1 contract repair preflight (2026-08-18)

The zero-network diagnostic found that the original six-field schema was stored
outside `messages` and therefore was not included in the adapter's provider
payload. The original context also exposed sentences without explicit evidence
IDs. The repaired preflight embeds the exact schema in both transmitted
messages, annotates every evidence sentence, audits the final transport
projection, and freezes 20 new development tasks with 100 balanced proposal
rows. It creates no authorization. Fingerprint:
`a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c`.

## Phase 4B-R2 repaired live-execution preflight (2026-08-18)

R2 binds the exact R1 100-row repaired schedule to a closed Token Plan Beijing
`qwen3.7-plus` execution contract and rechecks request/transport hashes,
five-condition balance, visible schema, evidence IDs, and historical identity
disjointness. It finds only 80 unique transmitted payloads: the `global_only`
and `contextual_typed` rows are identical after transport projection for each
of the 20 tasks. That contrast is not identifiable in this immutable schedule.
R2 is execution readiness only, creates no receipt or open authorization, and
has fingerprint `94a2e284a4049db12f5e1f1294fa92d4433547ee9be0dd151e6ba848bbc7da28`.

## Phase 4B-R3 terminal repaired calibration (2026-08-18)

The explicitly authorized R3 run ended at 73 request starts and 72 complete
responses after an external timeout left one orphan request and 27 unattempted
rows. All recorded responses satisfy the strict six-field contract and resolve
their evidence IDs, providing partial non-gating evidence that the repair
worked. The 100-row gate was not reached, so Phase 4C remains unauthorized.
Terminal audit fingerprint:
`f32e141b1ba15637cdb9b99fa360a59996adf613b90d610b7ef206bce14773e1`.

## Purpose

Phase 3H established that typed skill priors can change intermediate operations,
but it did not establish a reliable final-answer benefit. Phase 4 tests the
stronger claim under a single evidence-grounded response contract and wholly
new held-out tasks.

Strong claim to preregister:

> Under a uniform evidence-verification protocol, a task-matched typed skill
> prior causally improves final-answer accuracy over cold, global-only, and
> shuffled controls, with the improvement mediated by a verifiable intermediate
> operation and evidence trace.

This document is a design plan only. It creates no authorization and permits no
provider, paid, cross-domain, or formal-scaling call.

## Phase Sequence

### Phase 4A: Zero-Network Diagnosis and Design

- Audit the immutable Phase 3H v5 ledger without changing its gate.
- Classify answer failures into operation-correct/answer-wrong,
  operation-unchanged, evidence miss, entity confusion, and control leakage.
- Freeze a uniform response contract for every condition:
  `skill_assessments`, `selected_skill_id`, `evidence_sentence_ids`,
  `extracted_operands`, `intermediate_result`, and `final_answer`.
- Select wholly new tasks and prove zero overlap with all prior task IDs,
  logical-call IDs, request hashes, provider response IDs, and evaluation rows.

### Phase 4B: Development Calibration

- Use a separate development split of new tasks, approximately 20 tasks and
  five conditions (about 100 calls).
- This stage is contract and capability calibration only; it cannot supply the
  held-out effect estimate.
- Stop before held-out execution if contract validity is below 0.95,
  contextual procedure selection is below 0.90, or evidence extraction is not
  reliably verifiable.

### Phase 4C: Held-Out Causal Test

- Use approximately 80 entirely new held-out tasks, each assigned all five
  conditions:
  `cold`, `global_only`, `contextual_typed`, `shuffled_typed`, and
  `incompatible_control`.
- Keep the evidence-grounded response contract identical across conditions.
- Freeze task order, payloads, route, model, temperature, retry policy,
  pacing, response format, and cost ceilings before authorization.
- Analyze only rows passing the preregistered contract and coverage gates.

### Phase 4D: Independent Replication

Run only if Phase 4C passes every positive gate. Use a new held-out task split
and a separately versioned preflight. Cross-domain and formal scaling remain
closed until replication also passes.

## Frozen Decision Gates

Positive requires all of the following:

- contract-valid rate at least 0.95;
- contextual procedure-selection rate at least 0.90;
- contextual final-answer accuracy at least 0.10 above cold;
- contextual final-answer accuracy at least 0.08 above global-only;
- contextual final-answer accuracy at least 0.08 above shuffled typed;
- paired bootstrap 95% confidence interval for the primary improvement has a
  lower bound above zero;
- operation-change answer-grounding rate at least 0.65;
- both task families move in the same direction;
- shuffled typed does not obtain a comparable benefit.

Negative requires a complete primary population and no contextual advantage
over cold or global-only. All other complete outcomes are inconclusive.

Only a positive Phase 4C result may authorize Phase 4D. Selector uptake alone
cannot pass the gate.

## Required Provenance

Every future preflight must bind the Phase 3H v5 audit, preserve all spent
requests, freeze a new versioned config and artifact directory, record the
development/held-out split, and keep paid API permission explicit. Before any
material experiment turn ends, update `experiment_state.json`, append a
checkpoint, update the roadmap and handoff, run cache-free regressions, and run
the handoff validator.

## Phase 4B-R4 recovery preflight (2026-08-18)

The closed zero-network R4 preflight freezes 28 new canonical identities while
excluding all 73 spent R3 identities. Its combined plan preserves 72 complete
R3 responses as provenance and restores all 100 calibration rows. The orphan
replacement has a new logical ID and request hash but repeats one spent
provider-visible payload; this deliberate transport repeat is disclosed.

The grid still contains only 80 unique payloads because all 20
`global_only`/`contextual_typed` pairs are identical, so those labels cannot be
used for a causal comparison. No execution is authorized, and unknown orphan
usage leaves future cost ceilings unresolved. Fingerprint:
`fc668155d0e1d787fe45bf381f5958d8f9d5d78759be3c0bab3951580254f066`.

## Phase 4B-R5 live-execution preflight (2026-08-18)

The closed zero-network R5 preflight binds the 28-row R4 recovery schedule to
the exact qwen3.7-plus route and accounting contract. It reserves CNY 0.011136
for unknown orphan usage, freezes a CNY 0.30 recovery-stage ceiling and CNY
15.00 cumulative ceiling, and projects a known upper bound of CNY 12.640056.

No receipt or provider call exists. Any future authorization must preserve the
one disclosed orphan transport repeat and the 20 identical
`global_only`/`contextual_typed` transport pairs. Fingerprint:
`4b220ba56d8cf0990ecf86df791f79b8218db427c81a117b6c78a775d58f5a0d`.

## Phase 4B-R6 completed calibration (2026-08-18)

The authorized 28-row recovery completed and closed automatically. Combined
with R3, the full 100-row development calibration has 100/100 strict contract-
valid and evidence-resolving responses, with contextual selection 1.0. The
Phase 4B development contract gate therefore passes.

This does not establish the strong causal claim because all 20
`global_only`/`contextual_typed` pairs remain transport-identical. Phase 4C,
replication, cross-domain testing, and formal scaling remain unauthorized.
Analysis fingerprint:
`80cc655e1dc70795b783ae671f55e9df064c552467db3a42295e795f46016048`.

## Phase 4C-D1 admissibility diagnostic (2026-08-18)

Before any held-out authorization, the inherited Phase 4A schedule was audited
for provider-visible contract and causal condition distinctness. All 400 rows
fail the visibility audit for the six-field contract and evidence IDs, and all
80 `global_only`/`contextual_typed` pairs are transport-identical.

Phase 4C is therefore blocked pending a separately versioned repair design,
fresh live preflight, and exact authorization. Diagnostic fingerprint:
`57e2588f8183e4d8682f20dcf9d587fb37fe303142be1c340b616fbef68405c7`.

## Phase 4C-R1 repaired held-out design (2026-08-18)

The zero-network R1 design repairs the held-out payload contract: all 400 rows
carry visible six-field schema and evidence IDs, and the 80
`global_only`/`contextual_typed` pairs are substantively distinct by prior
scope. Canonical and transport identities are unique and disjoint from spent
Phase 4B identities.

No live authorization exists. A separate live preflight and exact user
authorization are required. Fingerprint:
`5c776023249499a5022fe901cae9f0684c22e30991fa9349a71e9af92b14bda3`.
