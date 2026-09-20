# Phase 1B SearchQA Token Plan Live Pilot V5

Date: 2026-08-09

## Protocol

V5 preserves the frozen SearchQA comparison and v4 formatting repair while adding a 1.0-second minimum interval between provider request starts, explicit retry/backoff only for HTTP 429, terminal handling for `data_inspection_failed`, and conservative full-envelope token accounting whenever provider usage is missing. Content-rejected inputs are neither altered nor retried; they remain in the metric denominator with zero EM/F1/substring EM. The absolute spend cap was CNY 200 and formal scaling remained disabled.

- Runner SHA-256: `3c62cce288e5628b1bc4608c33340a8c1b67644056c6157d5b9b15a19ac86fec`
- Config SHA-256: `c795ebfcc82944b9c3345885afc12c006109b22dc0d7728997cc0ad44accfd88`
- Plan fingerprint: `7d4367f7369b78f131a9c8dc7c1996adf031eff9cddda3e4c3cf2c7fda848ab4`

## Zero-network preflight

The immutable preflight completed all 2,448 logical calls using 2,582 deterministic attempts and 134 registered retries. Simulated accounting was 7,983,545 input tokens plus 18,436 output tokens, or 8,001,981 total tokens. There were zero paid calls. Reopening the artifact produced zero new calls and zero provider invocations.

Preflight summary fingerprint: `3b7b4aadb60bbc70de997afc9e3d9885492d8e41f48088a106256eebe5dc31c2`

## Complete live result

The live artifact completed all 2,448 logical calls with 2,579 provider attempts: 2,447 successful attempts and 132 failed attempts. All 131 format-repair attempts succeeded. One primary request returned HTTP 400 with provider code `data_inspection_failed`; it was not retried or altered, remained in the denominator with zero metrics, and was conservatively accounted as the full 8,448-token envelope because provider usage was absent. There were no HTTP 429 attempts.

Known provider usage was 7,444,769 input tokens plus 70,422 output tokens. Including the one conservative envelope, total accounted usage was 7,523,639 tokens. All 2,579 provider attempts had unique request IDs. No attempt returned reasoning content. The Token Plan accounting snapshot recorded CNY 0 charged usage, while the frozen absolute CNY 200 pre-invocation cap remained enforced.

| Method | EM | F1 | Sub-EM | Accounted tokens | Format-valid |
|---|---:|---:|---:|---:|---:|
| no_skill | 0.758929 | 0.835760 | 0.895833 | 413,438 | 336/336 |
| static_full_skill | 0.779762 | 0.850794 | 0.901786 | 1,542,840 | 335/336 |
| tfidf_topk | 0.773810 | 0.844643 | 0.901786 | 1,063,136 | 336/336 |
| skillopt_moar_frozen | **0.788690** | **0.857837** | **0.907738** | 1,103,447 | 336/336 |
| contextual_prior_diagnostic_upper_bound | 0.770833 | 0.841667 | 0.898810 | 1,063,450 | 336/336 |
| global_only_reset_comparator | 0.773810 | 0.848129 | 0.901786 | 1,063,286 | 336/336 |
| global_only_selective_full_confirmation | 0.773810 | 0.846145 | 0.898810 | 1,062,184 | 336/336 |

Live summary fingerprint: `e8f28745ef53918b1f22171be9fff77400e41da864a0c8f2a8d88363f35d214e`

## Interpretation and decision

The frequency hypothesis is not supported as the cause of the v4 interruption: the complete paced v5 run observed zero HTTP 429 attempts, while the same held-out call produced one reproducible `data_inspection_failed` rejection. The new rejection protocol prevented that single provider decision from terminating the experiment.

The frozen selective candidate tied the identity-correct reset comparator on EM, but was lower by 0.001984 F1 and 0.002976 substring EM while using about 0.10% fewer accounted tokens. It did not improve the real-task result over the reset comparator. The frozen MOAR method was the strongest measured method, exceeding the selective candidate by 0.014881 EM, 0.011692 F1, and 0.008929 substring EM at about 3.88% more accounted tokens.

Phase 1B is therefore complete as a valid negative/mixed real-model result. The evidence does not justify formal scaling of the selective guard. The next phase should reconcile the offline proxy/reward signal with the real SearchQA ranking and determine whether the continual-routing reward model or probe representativeness must change before Phase 2. Paid API and formal scaling permissions are disabled.

## Audit

The completed manifest and calls/attempts/summary file hashes match. Every call record passes the v5 resume validator; aggregate call, attempt, retry, token, and pico-currency identities pass; the summary fingerprint recomputes exactly. Related v4, v5, and handoff tests pass: `16 passed`.