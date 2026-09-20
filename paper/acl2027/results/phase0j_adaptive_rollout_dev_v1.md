# Phase 0J: Low-Cost Adaptive Rollout Horizon (Development v1)

Date: 2026-08-07

## Question

Can the Phase 0I rollout-aware cold-router guard preserve the development decision pattern while reducing validation cost toward the Phase 0G approximately 3.4k-token level?

This is a synthetic, fully offline calibration on development seeds 81-85. It is not held-out evidence and not downstream LLM accuracy evidence.

## Implementation

The guard now records after every paired rollout round:

- cumulative learned and cold-reference reward;
- cumulative margin and standard error;
- lower and upper confidence bounds;
- a configurable recent cumulative-margin recovery slope;
- cumulative route, credit-update, and total validation tokens.

Destructive reset can additionally require a minimum rollout horizon, a minimum amount of harm beyond the tolerance boundary, and non-recovery under a configured slope threshold. Early confident acceptance remains unchanged. Defaults preserve the prior sequential behavior.

## Artifact and audit

- config: `configs/acl2027/offline_continual_phase0j_adaptive_rollout_dev_v1.json`
- artifact: `artifacts/acl2027_continual_phase0j_adaptive_rollout_dev_v1`
- grid: 5 seeds (81-85) x 3 priors x 6 methods = 90/90 runs
- config SHA-256: `070ffe4d3fc31590dcb4d8c90b71a4aa3c464732fed3aef4306946ad05303217`
- aggregate fingerprint: `86223b91333e9e42a4b3ac632a0f0852b89ea839a9a77e7b87e73a3e1abc1a78`
- regression suite: **56 passed**

Exact audit results:

- missing or duplicate runs: 0
- file/config/run/aggregate fingerprint failures: 0
- total-token identity failures: 0
- guard route/update token identity failures: 0
- round-history length, monotonic token, or final-token failures: 0

## Main results

| Method | All-cold false resets | Helpful false resets | Adversarial detections | Mean guard tokens: all-cold / helpful / adversarial | Helpful reward |
|---|---:|---:|---:|---:|---:|
| Rollout sequential min-6 anchor | 0/5 | 1/5 | 5/5 | 3,369 / 4,120 / 3,362 | 0.7445 |
| Harm margin 0.05 + slope <= 0.10 | 0/5 | 1/5 | 5/5 | 3,369 / 4,120 / 4,022 | 0.7445 |
| **Harm margin 0.10 + slope <= 0.10** | **0/5** | **0/5** | **5/5** | **3,369 / 6,172 / 4,022** | **0.7553** |
| Harm margin 0.10 + slope <= 0.25 | 0/5 | 0/5 | 5/5 | 3,369 / 6,172 / 3,362 | 0.7553 |
| Harm margin 0.10, no slope gate | 0/5 | 0/5 | 5/5 | 3,369 / 6,172 / 3,362 | 0.7553 |
| Rollout sequential min-12 anchor | 0/5 | 0/5 | 5/5 | 6,767 / 9,591 / 6,736 | 0.7553 |

The conservative selected development setting is `adaptive_harm0p10_slope0p10`. Relative to the Phase 0I min-12 anchor, it reduces mean guard tokens by 49.8% for all-cold priors, 35.6% for helpful priors, and 40.3% for adversarial priors while preserving the same 0/5, 0/5, 5/5 decision pattern.

## Seed-83 trajectory

At round 2 the helpful seed-83 prior has cumulative margin -0.1385 and positive recovery slope +0.0497. The old min-6 rule resets it because its upper confidence bound is below the -0.06 tolerance boundary. The adaptive rule does not reset because the margin is not at least 0.10 below that boundary. It continues to round 8, recovers to margin -0.0186, and is retained.

The 0.05 harm-margin variant still resets seed 83, so recovery slope alone at the tested 0.10 threshold is insufficient. The 0.10 margin-only ablation matches the best development cost and decisions, meaning the incremental value of the slope gate is not established on development seeds. The stricter slope-0.10 candidate is retained for held-out testing because it delays one strongly recovering adversarial trajectory rather than treating the more permissive 0.25 threshold as validated safety evidence.

## Decision

Phase 0J passes its development decision-quality and efficiency gates. It does not justify paid API experiments or the formal 128/512 scaling grid because all thresholds were selected on only five development seeds.

Freeze `adaptive_harm0p10_slope0p10` and compare it with the margin-only ablation and the Phase 0I min-12 anchor on a separate 20-seed reliability split (101-120), with no threshold changes after results are observed.
