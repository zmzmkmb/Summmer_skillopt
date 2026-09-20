# Phase 2: Independent Expansion Design v1

## Status and Boundary

This is a zero-network, design-only extension experiment. It is independent of
Phase 1 and does not revise its thresholds, results, artifacts, or conclusion.
Phase 1 remains formally closed as `inconclusive`: Phase 1Y produced 8 verified
trajectories from 10 zero-retry `qwen3.7-plus` calls, costing exactly CNY
0.027228, but only 3/5 typed families reached two supporting tasks. Phase 1Z
therefore made zero provider calls and closed with fingerprint
`5c2a3c0a1140609c3e51e6a093301dcab5949d14d561e162d9cc1a8f9c2f7340`.
No Phase 1AA/1AB or other repair stage is created.

## Alternatives

| Arm | Calibration | History attempts | Verified supports required | Probe | Held-out | Max logical requests | Estimated CNY | Conservative ceiling |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A conservative | 12/family = 60 | 18/family = 90 | 4/family | 4/family = 20 | 8/family = 40 | 390 | 3.334560 | 4.00 |
| B stronger | 12/family = 60 | 34/family = 170 | 8/family | 8/family = 40 | 16/family = 80 | 710 | 6.197280 | 7.50 |

The history number includes two development-acquisition attempts per family and
the formal cap. Development responses are used only to assess acquisition
viability and are never accepted as formal history supports. Formal acquisition
stops when the target number of verifier-confirmed successes is reached, or at
the per-family cap. If the target is not reached, that family fails and there is
no held-out execution. The cap is not a claim that success is guaranteed.

A is the minimum practical design for a first causal read: four supports, four
probes, and eight held-out tasks per family. B is recommended because the Phase
1 failure was sparse and family-concentrated; it gives eight supports, eight
probes, and sixteen held-out tasks per family. B may add a second seed or
independent task subset only as a separately labeled replication after the
primary arm is frozen. It must not be pooled into the primary comparison.

## History Acquisition

There are five required families: `fact_retrieval`, `attribute_comparison`,
`bridge_attribute_comparison`, `entity_bridge`, and `relation_inference`.
Each accepted record must contain the raw model response, immutable task ID,
task family/type, skill family, typed scope, verifier replay, payload hash,
request hash, and complete provenance. A gold answer is a verification input,
never a model trajectory. A response that is valid but not verifier-successful
is retained as a negative acquisition outcome and is charged, but cannot become
a candidate.

The two development attempts per family are optional only as a pre-registered
acquisition diagnostic. They must be frozen before formal history starts and
cannot be selected after seeing probe or held-out results. Formal history is
append-only and family-stratified. No response from calibration, probe, or
held-out can be used to fill a missing family. If a family exhausts its cap,
the run stops for that family and the complete experiment is reported as
coverage-incomplete, not as a method failure or success.

## Causal Design and Identifiability

Every probe and held-out task is evaluated under four model-visible conditions:
`cold`, `copied_global`, `global_only`, and `contextual_typed_prior`. Each
condition/task pair has a distinct canonical request body and physical call.
The body binds arm, partition, family, task ID/type, condition, candidate ID
and version, typed scope, prompt-template version, seed, and payload hash;
`request_hash = SHA256(canonical_JSON(body))`. Thus a gate label is never the
only changing field in otherwise identical requests, and gate labels are
computed locally, never narrated to the model.

The four model conditions cannot legally reuse a response: their prompts or
contexts differ. Retaining triage and destructive gating are local state
transitions over the same preserved probe/held-out response ledger, so their
scoring may reuse exactly those response bundles. If a policy changes the
model-visible prompt, it becomes a separate condition and separate call.
This avoids the non-identifiability exposed by Phase 1S's identical
gate-label request pairs.

The primary contrast is contextual typed prior versus `global_only` on the
same held-out task IDs with separately called responses. Secondary contrasts
compare contextual against cold and copied-global. The gate retains the Phase
1T frozen thresholds: accept at mean margin >= 0.125 with at least 3 helpful
pairs and no harmful pair; reject at mean margin <= -0.125 or at least 2 harmful
pairs; otherwise abstain. Retaining keeps rejected/abstained candidates for
later recovery; destructive gating discards them irreversibly. No threshold,
condition, task, or primary metric may change after results are inspected.

## Partitions and Exclusion Audit

For each family, materialize disjoint gold-bearing task IDs in this order:
12 calibration tasks, 2 development-acquisition IDs, the formal history IDs,
the probe IDs, and the held-out IDs. A uses 4 probe and 8 held-out IDs per
family; B uses 8 and 16. The exact source dataset manifest hash, ordered IDs,
payload hashes, selector hash, and pairwise-disjointness matrix are frozen
before any response is requested.

The selector is the lexicographic order of
`SHA256(phase2-v1:<partition>:<family>:<seed>:<task_id>)`. The audit must reject
all Phase 1B-spent SearchQA IDs, all Phase 1 calibration/probe/held-out IDs,
all Phase 1X calibration IDs, and every prior calibration/probe/held-out ID.
It must also reject duplicate task IDs, duplicate payload hashes where a
distinct task is required, missing gold fields, and answer/support leakage.

## Measurements and Evidence Classes

Report answer accuracy, support accuracy, and joint accuracy for every
condition, plus paired margins, helpful and harmful pair counts, false-safe,
false-harm, abstention, retained-candidate recovery, and useful candidates
lost by destructive gating. Report cumulative input/output/total tokens and
reward per 1,000 cumulative tokens, including invalid responses and every
candidate/fallback response. All metrics are stratified by task family, task
type, and skill family.

Partition/hash/verifier/condition and state-transition results are protocol
evidence. Calibration and verified history rates are capability evidence.
Only the pre-registered paired held-out contrasts and safety/retention outcomes
are method-effect evidence. Candidate coverage is a capability prerequisite,
not a positive method result.

## Pre-Registered Conclusions

The minimum sample is the full A or B partition, with at least the stated valid
probe count per family and the complete held-out count per family. A positive
conclusion requires the primary held-out margin and the pre-registered safety
and retention criteria to pass. A negative conclusion requires the specified
harm/failure criteria to pass. All other complete outcomes are inconclusive.
An incomplete history, integrity failure, unknown usage, provider exception,
authorization drift, or cost ceiling is a protocol/ execution stop and cannot
be relabeled as a negative method result. There is no positive early stopping;
only those terminal safety/integrity/accounting stops are allowed.

## Calls, Tokens, and Cost

The exact logical request counts are 390 (A) and 710 (B): calibration is 60
requests; history is 90/170 maximum attempts; probes are 20/40 tasks times
four conditions (80/160); held-out is 40/80 tasks times four conditions
(160/320). With zero retries, the worst-case physical attempt counts equal
these logical counts. Known-usage invalid outputs consume an attempt; unknown
usage and provider exceptions hard-stop rather than retry.

Planning envelopes are 2,200 input + 256 output tokens per calibration request,
2,200 + 512 per history attempt, and 2,500 + 512 per probe/held-out request.
At CNY 2/M input and CNY 8/M output, the component estimates are:

| Arm | Calibration | History acquisition | Probe | Held-out causal pilot | Total |
|---|---:|---:|---:|---:|---:|
| A | 0.386880 | 0.764640 | 0.727680 | 1.455360 | 3.334560 |
| B | 0.386880 | 1.444320 | 1.455360 | 2.910720 | 6.197280 |

These are planning estimates, not fabricated usage. The future runner must
record exact integer input/output/total usage, append one immutable ledger row,
and recompute CNY before permitting another request. Conservative local
ceilings are CNY 4.00 for A and CNY 7.50 for B. The future authorization must
also require zero retries, no `max_tokens`, exact append-only resume, unknown
usage hard stop, provider-exception hard stop, request/authorization drift
hard stop, and cost-ceiling hard stop. This document opens none of those
permissions.

## What Phase 2 Can Establish

If complete and positive, Phase 2 can support a bounded claim that, on the
specified eligible substrate and disjoint task streams, contextual typed priors
outperformed the frozen comparators under the frozen verifier and that the
retaining policy had the reported safety/recovery behavior. If complete and
negative, it can rule out that pre-registered effect at this substrate,
coverage, and sample size; it cannot rule out all models, tasks, or priors.
Either outcome can strengthen protocol and capability evidence only when those
audits pass.

Phase 2 still cannot turn Phase 1 into a success, erase Phase 1's real-task
method-effect `inconclusive` conclusion, establish universal transfer, prove
that more history is itself causal, or separate model capability from prior
quality beyond the frozen contrasts. The next step is a new authorization
decision after this design is independently reviewed; no authorization is
needed for the present design-only work.
