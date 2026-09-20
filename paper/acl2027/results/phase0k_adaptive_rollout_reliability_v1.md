# Phase 0K: Adaptive Rollout Guard Held-Out Reliability (v1)

**Status:** completed; predeclared held-out gate failed  
**Date:** August 7, 2026  
**Scope:** synthetic offline held-out reliability evidence; no paid model/API calls, no formal 128/512 scaling, and no downstream LLM accuracy claim.

## 1. Question

Does the frozen Phase 0J `adaptive_harm0p10_slope0p10` guard retain helpful priors, reject adversarial priors, avoid all-cold false resets, and remain below the predeclared validation-token limits on 20 unseen seeds?

The seeds 101-120 were held out from the Phase 0J development grid. Thresholds, run inclusion, and the three compared methods were frozen before these results were observed.

## 2. Frozen protocol and gates

- Config: `configs/acl2027/offline_continual_phase0k_adaptive_rollout_reliability_v1.json`
- Artifact: `artifacts/acl2027_continual_phase0k_adaptive_rollout_reliability_v1`
- Seeds: 101-120
- Conditions: all-cold, helpful oracle, and adversarial priors
- Methods: selected slope-0.10 guard, margin-only ablation, and rollout sequential min-12 anchor
- Grid: 20 seeds x 3 prior conditions x 3 methods = 180/180 runs
- Calibration rule: no threshold changes or run exclusions after observing held-out results

Predeclared gate for the selected method:

1. helpful false resets: 0/20;
2. adversarial detections: 20/20;
3. all-cold false resets: 0/20;
4. mean guard tokens: at most 4,000 all-cold, 8,000 helpful, and 5,000 adversarial.

## 3. Artifact and audit

- Config SHA-256: `9d5d0d4b79dcd3d23d1c69e2755b44495e1033418f95159ff9eed3f776faa0dd`
- Aggregate fingerprint: `747672390225a22c1ec0a8f7c4dfbf764cd1b54c8e1ca4b49ed520cfd19654d4`
- Complete grid: 180/180 runs
- Missing or duplicate runs: 0
- File/config/run/aggregate fingerprint failures: 0
- Total-token identity failures: 0
- Guard route/update token identity failures: 0
- Round-history length, monotonic-token, or final-token failures: 0

The audit checked every run file against `run_manifest.json`, recomputed scientific run fingerprints with timing excluded, recomputed the aggregate fingerprint, and verified exact token identities at both run and rollout-round levels.

## 4. Main results

Means and standard deviations are across 20 seeds. Guard-token summaries are exact, unamortized validation costs.

| Method | Condition | Resets / detections | Mean reward | Guard tokens, mean +/- sd | Median / p90 / range | Mean rounds |
|---|---|---:|---:|---:|---:|---:|
| **Adaptive margin 0.10 + slope 0.10** | All-cold | **0/20 false resets** | 0.7419 | **3,340.5 +/- 120.9** | 3,327 / 3,521 / 3,142-3,578 | 2.00 |
| **Adaptive margin 0.10 + slope 0.10** | Helpful | **3/20 false resets** | 0.7584 | **9,027.9 +/- 4,284.6** | 9,248 / 13,580 / 3,258-13,954 | 5.40 |
| **Adaptive margin 0.10 + slope 0.10** | Adversarial | **19/20 detections** | 0.7349 | **4,272.8 +/- 1,098.2** | 4,006 / 5,383 / 3,089-6,488 | 2.60 |
| Margin-only ablation | All-cold | 0/20 false resets | 0.7419 | 3,340.5 +/- 120.9 | 3,327 / 3,521 / 3,142-3,578 | 2.00 |
| Margin-only ablation | Helpful | 3/20 false resets | 0.7584 | 9,027.9 +/- 4,284.6 | 9,248 / 13,580 / 3,258-13,954 | 5.40 |
| Margin-only ablation | Adversarial | 19/20 detections | 0.7349 | 3,687.2 +/- 1,008.8 | 3,344 / 5,070 / 3,068-6,488 | 2.25 |
| Min-12 anchor | All-cold | 0/20 false resets | 0.7419 | 6,673.4 +/- 223.3 | 6,644 / 6,990 / 6,310-7,118 | 4.00 |
| Min-12 anchor | Helpful | 3/20 false resets | 0.7584 | 10,626.6 +/- 3,141.8 | 12,426 / 13,680 / 6,294-13,954 | 6.35 |
| Min-12 anchor | Adversarial | 20/20 detections | 0.7419 | 6,916.2 +/- 1,558.7 | 6,563 / 6,906 / 6,162-13,465 | 4.20 |

All three methods reset the same helpful seeds, 101, 108, and 113. The selected method and margin-only ablation also both missed adversarial seed 109. Thus the slope gate produced no held-out decision benefit. Under adversarial priors it added 585.6 mean guard tokens and 0.35 mean rounds relative to margin-only.

## 5. Reliability intervals

Wilson score 95% intervals for the selected method are:

| Event | Count | Observed rate | Wilson 95% interval |
|---|---:|---:|---:|
| All-cold false reset | 0/20 | 0% | 0.0%-16.1% |
| Helpful false reset | 3/20 | 15% | 5.2%-36.0% |
| Adversarial miss | 1/20 | 5% | 0.9%-23.6% |
| Adversarial detection | 19/20 | 95% | 76.4%-99.1% |

The intervals remain wide at 20 seeds. More importantly, both observed failures violate the zero-error decision gates directly; uncertainty does not rescue the gate.

## 6. Predeclared gate decision

| Gate | Requirement | Observed | Result |
|---|---:|---:|---|
| All-cold false resets | 0/20 | 0/20 | Pass |
| Helpful false resets | 0/20 | 3/20 | **Fail** |
| Adversarial detections | 20/20 | 19/20 | **Fail** |
| Mean all-cold guard tokens | <=4,000 | 3,340.5 | Pass |
| Mean helpful guard tokens | <=8,000 | 9,027.9 | **Fail** |
| Mean adversarial guard tokens | <=5,000 | 4,272.8 | Pass |

**Phase 0K fails the predeclared held-out reliability gate.** Paid API evaluation and formal 128/512 scaling remain disabled.

## 7. Failure trajectories

### 7.1 Helpful false resets

- Seed 101 triggered `confident-harmful` at round 2. Its margin moved from -0.1117 to -0.1915, with final recovery slope -0.0798.
- Seed 108 triggered `confident-harmful` at round 2. Its margin moved from -0.2460 to -0.3446, with final recovery slope -0.0986.
- Seed 113 exhausted all eight rounds and then reset. Its final margin was -0.0842 with confidence interval [-0.1573, -0.0110] and recovery slope -0.0152.

For each of these seeds, resetting the oracle prior makes the downstream run equal the corresponding all-cold trajectory. The frozen Phase 0K grid did not include an unguarded oracle run, so the reward that the helpful prior would have achieved without reset is not identifiable from this artifact. Consequently, an exact helpful-reset opportunity loss cannot be reported without a separate post-hoc counterfactual diagnostic. Any such diagnostic must be labeled post hoc, run uniformly, excluded from the held-out gate, and must not be used to tune thresholds on seeds 101-120.

### 7.2 Adversarial miss

Seed 109 stopped as `confident-acceptable` at round 2:

| Round | Paired samples | Learned mean | Cold-reference mean | Margin | 1-s.e. confidence interval |
|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 0.7510 | 0.4754 | +0.2757 | [+0.1052, +0.4462] |
| 2 | 6 | 0.7336 | 0.5149 | +0.2187 | [+0.1105, +0.3268] |

The guard therefore observed strong positive probe evidence for a genuinely adversarial prior. Its final main-stream mean reward was only 0.5314, versus 0.6713 for the same seed's all-cold trajectory. This is a probe-representativeness or prior-identity failure, not merely a destructive-reset horizon that was too short. Requiring more reset rounds would not affect an early `confident-acceptable` decision.

## 8. Interpretation

1. **Development performance did not transfer cleanly.** The 0/5 helpful and 5/5 adversarial pattern from Phase 0J became 3/20 helpful false resets and 19/20 adversarial detections.
2. **The slope gate is not supported.** It matched margin-only on every held-out decision while costing more under adversarial priors.
3. **The min-12 anchor is not a sufficient fallback.** It recovered seed 109 but retained the same three helpful false resets and exceeded all three selected-method costs.
4. **Probe validity is now the blocking scientific question.** Some helpful priors look harmful on probes, while one adversarial prior looks strongly helpful despite poor stream reward.
5. **Seeds 101-120 are spent held-out evidence.** They may be inspected for failure analysis but cannot be reused for calibration or relabeled as a new held-out test.

## 9. Decision and next step

Freeze this artifact and report the negative result. Do not tune Phase 0J thresholds on seeds 101-120, do not launch paid API work, and do not begin formal scaling.

The next phase should be a diagnostic of prior identity and probe representativeness. It should first perform a non-calibrating postmortem of the four failure trajectories, then predeclare a fresh development split and measurements of per-domain probe-to-stream agreement before proposing another guard. Any new candidate would require a later, disjoint held-out reliability test before the execution policy can change.
