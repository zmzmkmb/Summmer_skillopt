# Phase 1Y: verified history and typed skill-candidate materialization

## Purpose

Phase 1Y binds the frozen SearchQA and 2WikiMultiHopQA history partitions and
admits only successful model trajectories that a local automatic verifier can
replay. The run is strictly local: dataset download, network access, provider
execution, and paid calls are disabled.

## Partition and source audit

The audit selected the exact Phase 1T partitions for each task family:

| Task family | Calibration | History | Probe | Held out |
| --- | ---: | ---: | ---: | ---: |
| SearchQA | 12 | 120 | 24 | 120 |
| 2WikiMultiHopQA | 12 | 120 | 24 | 120 |

All eight sets are pairwise disjoint. The Phase 1B source contains 2,448 call
records and 360 unique spent SearchQA test IDs. None intersects the frozen
SearchQA history, probe, or held-out subset.

The local source scan found no usable history trajectory. SearchQA history is
available only as selected IDs and has no local question, context, answer, or
model-response payload. The 2Wiki history has complete gold task payloads but
no model responses. Gold records are not trajectories and were rejected with
`gold_record_is_not_trajectory` and `missing_model_response`.

The 24 Phase 1X calibration responses were replayed as a source-consistency
check. All 24 replay results matched their recorded joint-correct labels, but
all were excluded because calibration records are not history records.

## Materialization result

```text
history records audited:     240
verified trajectories:         0
typed candidates:              0
network calls:                 0
provider calls:                0
paid calls:                    0
decision: negative_materialization_no_verified_history_phase1z_blocked
```

The audit retained deterministic trajectory and candidate IDs, task family,
task type, skill family, typed scope where available, supporting task IDs,
source trajectory IDs, payload hash, verifier status, provenance, and rejection
reasons for every record. The 2Wiki history covers 47 compositional, 32
comparison, 30 bridge-comparison, and 11 inference tasks. No task-family or
task-type coverage can be claimed for admitted candidates because the admitted
set is empty. Concentration is therefore reported as `empty_candidate_set`,
not as a successful diversity result. No evaluation-partition leakage was
detected.

Eleven of twelve audit checks are true. The sole false check is intentionally
`candidate_contract_coverage_met`: it records the scientific gate failure and
is not an artifact-integrity failure.

## Call and cost conclusion

The candidate contract requires at least 10 verified history successes: two
SearchQA successes and eight 2Wiki successes. Eight deterministic 2Wiki
requests, two per frozen task type, can be frozen locally. Their plan hash is
`8408e0439a88822623e84c2cdec4e966fcdda2ebc338ec056c367f7b90651e31`.
The two SearchQA requests cannot be frozen because the selected history task
payloads are absent. Consequently, the exact number of currently authorizable
history calls is zero and no provider request is authorized.

The earlier 1,152-call figure is only the unoptimized product of 288 tasks and
four provisional conditions. It is not an audited minimum. With zero typed
candidates, Phase 1Z response reuse and paired identification cannot be
specified, so its exact minimum call count and cost are currently undefined.
Phase 1Y incurred CNY 0. The conditional 10-success history estimate remains
CNY 0.370601 under the frozen conservative Phase 1W pricing assumptions, but
it is not an executable plan and is not authorization.

## Artifact integrity

The final artifact is
`artifacts/acl2027_phase1y_verified_history_skill_candidates_v4`. Earlier v1,
v2, and v3 construction attempts are not evidence and are not referenced by
experiment state.

```text
aggregate fingerprint: 52895ba69533b371ad371732d84a0a40e3708e5cb9bd08af6527db50e3439cfc
audit:                 f516383ae33e4166c5074e3adb5c3f11152617c90540894751b1e9ed6eaaf5a7
candidate records:     00b335dfabf4953d801ca041ce5174116986d9bf6e934627a19c38b17bd6b206
request plan:          ef0794155f10cfd1df59eb229c77720788f0850f12ae77f0767c9ea4d6a9e969
config:                cddb95de20ed710cdae8ff0e9abb214106e381fa87806ac2267bf43a8bcc36dd
```

Phase 1Y is complete with a negative materialization result. Phase 1Z is the
only remaining Phase 1 stage and is blocked rather than executable. No model,
provider, or network call was made.
