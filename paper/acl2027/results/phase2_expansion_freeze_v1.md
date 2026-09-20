# Phase 2 B Expansion Freeze v1

Status: `design_only_blocked_preflight`. This is an independent Phase 2
extension and does not revise the Phase 1 conclusion: Phase 1 is closed and
the real-task method effect is inconclusive.

## Frozen protocol

The recommended stronger arm has five skill families:
`fact_retrieval`, `attribute_comparison`, `bridge_attribute_comparison`,
`entity_bridge`, and `relation_inference`. Each family targets 12 calibration,
2 development-acquisition, 32 formal-history attempts, 8 disjoint probe tasks,
and 16 disjoint held-out tasks. The four model conditions are `cold`,
`copied_global`, `global_only`, and `contextual_typed_prior`; each distinct
condition/task pair requires a distinct canonical request body and physical
call. The model configuration is `qwen3.7-plus`, temperature 0, zero retries,
and no `max_tokens` field.

The fixed target arithmetic is 60 calibration calls, at most 170 history
attempts, 160 probe calls, and 320 held-out calls: 710 logical requests and
710 worst-case physical attempts when retries are zero. The planned cost is
CNY 6.197280, with a conservative CNY 7.50 ceiling.

Stage 0 is zero-network preflight. Stages 1-3 retain every response, failure,
invalid/refusal/incomplete result, and exact known usage. Stage 4 requires at
least eight independent verifier-confirmed supporting trajectories per family.
If it fails, the result is `coverage-incomplete`, not method failure, and
Stages 5-6 are prohibited. History cannot be supplemented after probe results,
and held-out outputs cannot create or change candidates.

Accept/reject/abstain thresholds remain the immutable Phase 1T values:
accept at margin >= 0.125, helpful >= 3, and harmful = 0; reject at margin <=
-0.125 or harmful >= 2; otherwise abstain. Gate labels are computed locally.
Saved response ledgers may serve retaining/destructive local state transitions
only when model-visible prompt/context is unchanged.

## Preflight block

The exact source manifest and hashes are recorded in
`artifacts/acl2027_phase2_expansion_freeze_v1/partition_audit.json`. Local
2Wiki payloads cover four families, but SearchQA has only the 12 Phase 1U
calibration payloads locally. The required Phase 2 `fact_retrieval` payload
capacity is 70 records, and its train/validation/test directories currently
provide only ID manifests for this purpose. Consequently no legal complete
five-family partition can be selected, and no request body can be frozen for
execution. No task is fabricated, silently remapped, or selected from an
unaudited split.

The artifact therefore records empty ordered partitions, the selector formula
`SHA256("phase2-v1:<partition>:<family>:<seed>:<task_id>")`, selector hash,
payload-hash schema, pairwise disjointness matrix, namespaced Phase 1
exclusion audit, and family/type capacity audit. `request_plan.json` records
the 710-request target but has `materialized_logical_requests: 0` and an empty
plan. This is a blocked preflight, not a partial experiment and not evidence
of method failure.

## Analysis and authorization boundary

Preregistered outputs are answer, support, and joint accuracy; paired margin;
helpful/harmful pair counts; false-safe/false-harm; abstention; retained
candidate recovery; useful candidates lost by destructive gating; cumulative
input/output/total tokens; and reward per 1,000 cumulative tokens, stratified
by task family, task type, and skill family. The primary comparison is
`contextual_typed_prior` versus `global_only`; secondary comparisons are the
two cold/copied-global comparisons and retaining versus destructive gating.
Evidence is labeled protocol, capability, or method-effect evidence. Positive
claims are bounded to the frozen substrate and protocol; negative claims only
exclude the preregistered effect at this sample size; other complete outcomes
are inconclusive. More candidates or coverage is not method evidence.

No network, provider, model, Qwen, or paid call occurred. Phase 2 remains
planned/design-only, with paid API and formal scaling disabled. Clearing the
missing payload preflight and a new explicit user authorization are both
required before any execution.
