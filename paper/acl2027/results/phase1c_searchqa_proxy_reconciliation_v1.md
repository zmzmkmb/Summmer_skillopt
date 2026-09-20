# Phase 1C: SearchQA Proxy-to-Real Reconciliation

Date: 2026-08-10

## Protocol

This phase is a no-paid, no-network diagnostic over immutable Phase 0N summaries
and the completed Phase 1B v5 Token Plan calls. The Phase 1B SearchQA test
answers are used only for preregistered descriptive paired analysis. No
threshold, prompt, method, or label was changed using held-out answers.

Inputs and their SHA-256 fingerprints are recorded in the Phase 1C artifact
`analysis.json`. The analysis unit for SearchQA is the exact paired
`seed:item_id`; all methods use the same 112 evaluation items per seed.

## Real-task paired results

| Comparison | n | EM delta | F1 delta | Sub-EM delta | Token delta |
|---|---:|---:|---:|---:|---:|
| selective guard - reset | 336 | 0.000000 | -0.001984 | -0.002976 | -3.28 |
| frozen MOAR - reset | 336 | +0.014881 | +0.009708 | +0.005952 | +119.53 |

The selective guard tied reset on EM. At the paired item level it had 1 win,
334 ties, and 1 loss on EM; it had 1 win, 333 ties, and 2 losses on both F1
and Sub-EM. Its token difference was negligible: 7 paired token wins, 321
ties, and 8 losses. The small aggregate token reduction therefore does not
support a meaningful efficiency-superiority claim.

The frozen MOAR result was positive in all three seeds on EM (+0.017857,
+0.008929, +0.017857). Its F1 gain was positive in seeds 202701 and 202703,
but slightly negative in seed 202702. MOAR used more tokens in 249/336 pairs,
with a mean increase of 119.53 accounted tokens per item.

## Offline-to-real comparison

The Phase 0N selective guard had a mean reward advantage of +0.004357 over
the identity-correct global reset comparator across 40 paired rows, with 2
wins, 36 ties, and 2 losses. Against copied-global reset, the advantage was
+0.016360, with 17 wins, 21 ties, and 2 losses.

This provides a concrete reconciliation: the offline advantage is concentrated
against the copied-global comparator and nearly disappears against the
identity-correct reset comparator. On real SearchQA, the selective guard does
not improve the identity-correct reset comparator. The evidence does not
localize a repairable threshold failure without fresh development evidence;
the most defensible explanation is a combination of comparator mismatch and
task-specific probe/reward utility.

## Guard and transport diagnostics

All six Phase 1B guard summaries (three seeds, two guarded methods) selected
`acceptable`, took 8 probe rounds, did not trigger a reset, and did not mutate
candidate state. The guard consequently made no downstream policy distinction
between the two guarded methods in this pilot.

There were 2,448 completed logical calls and 2,579 provider attempts. The
artifact records 131 ordinary failed attempts and one terminal
`data_inspection_failed` provider rejection. The rejection remains in the
provenance and metric denominator according to the frozen v5 policy. No HTTP
429 attempt was observed, and this analysis made zero network calls.

## Decision

1. The selective non-regression guard is not supported as a primary claim of
   real-task superiority. Keep it as a safety/diagnostic component unless a
   fresh development protocol produces a preregistered improvement.
2. The strongest current method claim is frozen MOAR skill routing improving
   real-task quality over reset and no-skill baselines, with a measurable token
   tradeoff.
3. The strongest analysis claim is that offline proxy gains do not transfer
   automatically to real-task gains, especially when the offline comparator
   differs from the real-task comparator.
4. Do not spend more API budget or enable formal scaling from this phase alone.
   A future development phase may revise the proxy/reward model only with fresh
   development or fabricated evidence, followed by a new frozen held-out test.

## Reproducibility

Config: `configs/acl2027/searchqa_phase1c_proxy_reconciliation_v1.json`

Analysis artifact: `artifacts/acl2027_searchqa_phase1c_proxy_reconciliation_v1`

The artifact contains `analysis.json` and `run_manifest.json`, including input
fingerprints, the no-network declaration, and the analysis result fingerprint.
Related tests: `tests/test_acl2027_searchqa_phase1c.py` and
`tests/test_acl2027_experiment_handoff.py` passed (8 tests).
