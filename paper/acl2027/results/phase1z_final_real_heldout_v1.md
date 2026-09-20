# Phase 1Z: final real held-out adjudication and Phase 1 closure

## Decision

Phase 1Z closed as `inconclusive_without_phase1z_provider_execution`. The
preregistered execution gate failed before any held-out request: Phase 1Y
materialized only 3 of 5 required typed scopes. No Phase 1Z provider, network,
or paid call was made, and no held-out causal effect was estimated.

## Bound Phase 1Y evidence

The closure runner verified immutable hashes for the live history responses,
candidate audit, and typed candidates. The authorized 10-call history batch
produced 8 locally replayable verified trajectories: 2/2 SearchQA and 6/8
2WikiMultiHopQA. Exact usage was 11,610 input plus 501 output tokens (12,111
total), accounted locally as CNY 0.027228, with zero retries and no
`max_tokens` request field.

The candidate contract requires two distinct verified supporting tasks for
each typed scope. Three candidates satisfy it:

| Task family | Task type | Skill family | Supports |
| --- | --- | --- | ---: |
| SearchQA | single-hop | fact retrieval | 2 |
| 2WikiMultiHopQA | comparison | attribute comparison | 2 |
| 2WikiMultiHopQA | bridge comparison | bridge attribute comparison | 2 |

`entity_bridge` and `relation_inference` each have only one verified support,
so they were rejected as typed candidates. Required family coverage is 3/5,
or 0.6. The maximum candidate task-family share is 2/3, and the maximum share
of any supporting task ID is 1/6. Deterministic candidate IDs and verifier
replay passed, and no calibration, probe, held-out, Phase 1B-spent, or other
evaluation-partition ID leaked into admitted support.

## Calls and interpretation

The theoretical minimum repair is two *successful* history generations: one
additional `entity_bridge` success and one additional `relation_inference`
success. Because model success cannot be guaranteed before execution, there is
no finite exact guaranteed request count. The currently authorized additional
call count is zero.

Under the hard convergence rule, this failed prerequisite closes rather than
extends Phase 1. It neither supports nor refutes a held-out contextual typed
prior effect because that effect was not executable. It does establish the
negative result that the minimal authorized history sample did not yield the
complete independently supported candidate set required by the frozen design.
No Phase 1AA, 1AB, or other repair stage is created.

## Artifact integrity

```text
artifact:              artifacts/acl2027_phase1z_final_real_heldout_v1
aggregate fingerprint: 5c2a3c0a1140609c3e51e6a093301dcab5949d14d561e162d9cc1a8f9c2f7340
provider attempts:      0
network calls:          0
paid calls:             0
Phase 1 closed:         true
```
