# Phase 0G Reliability Expansion ? 20-Seed Prior-Guard Diagnostic

**Status:** completed  
**Date:** August 7, 2026  
**Scope:** synthetic offline reliability evidence; no paid model/API calls and no downstream LLM claim.

## 1. Purpose

The initial Phase 0G held-out study used only three test seeds. Its one-probe guard nearly matched
Relevance Top-K in exact reward per 1k tokens, but the same guard had falsely triggered on one of three
development all-cold seeds. This expansion estimates that instability over 20 new seeds and compares it
with the safer sequential `z=1.0` guard.

## 2. Frozen protocol

- Config: `configs/acl2027/offline_continual_phase0g_reliability_v1.json`
- Artifact: `artifacts/acl2027_continual_phase0g_reliability_v1`
- Seeds: 61?80
- Conditions: all-cold and adversarial
- Methods: Relevance Top-K, unguarded fixed 0.5 shared, fixed one-probe guard, fixed sequential `z=1.0`
  guard, and oracle upper bound
- Grid: 20 seeds ? 2 conditions ? 5 methods = 200/200 runs
- Aggregate fingerprint: `bea42f3cf5a0f9a49a49fed0bde8b0a458c52f5c31638cbef950741f90b26925`

All guard hyperparameters were inherited from Phase 0G. No thresholds were selected on seeds 61?80.
Primary token metrics use exact unamortized candidate-plus-Relevance validation cost.

## 3. Aggregate results

Values are mean ? standard deviation across 20 seeds.

| Condition | Method | Reward | Total tokens | Guard tokens | Reward / 1k | Amortized reward / 1k | Trigger rate | Rounds | Target |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All-cold | Relevance Top-K | 0.7378 ? 0.0214 | 76,541 ? 1,226 | 0 | 1.4466 ? 0.0594 | 1.4466 | ? | ? | 20/20 |
| All-cold | Fixed 0.5 shared, unguarded | 0.7454 ? 0.0196 | 75,190 ? 1,284 | 0 | **1.4875 ? 0.0488** | 1.4875 | ? | ? | 20/20 |
| All-cold | Fixed one-probe guard | 0.7454 ? 0.0196 | 76,921 ? 1,291 | 1,731 ? 103 | 1.4540 ? 0.0471 | 1.4686 | 2/20 | 1.00 | 20/20 |
| All-cold | Fixed sequential `z=1.0` | 0.7454 ? 0.0196 | 80,831 ? 4,113 | 5,641 ? 3,733 | 1.3863 ? 0.0722 | 1.4286 | 1/20 | 3.35 ? 2.18 | 20/20 |
| All-cold | Oracle upper bound | 0.9860 ? 0.0061 | 75,170 ? 922 | 0 | 1.9678 ? 0.0278 | 1.9678 | ? | ? | 20/20 |
| Adversarial | Relevance Top-K | 0.7378 ? 0.0214 | 76,541 ? 1,226 | 0 | 1.4466 ? 0.0594 | 1.4466 | ? | ? | 20/20 |
| Adversarial | Fixed 0.5 shared, unguarded | 0.5227 ? 0.0232 | 74,047 ? 1,565 | 0 | 1.0591 ? 0.0484 | 1.0591 | ? | ? | 0/20 |
| Adversarial | Fixed one-probe guard | 0.7454 ? 0.0196 | 76,882 ? 1,290 | 1,692 ? 100 | **1.4548 ? 0.0473** | 1.4694 | 20/20 | 1.00 | 20/20 |
| Adversarial | Fixed sequential `z=1.0` | 0.7454 ? 0.0196 | 78,480 ? 1,321 | 3,290 ? 170 | 1.4252 ? 0.0464 | 1.4526 | 20/20 | 2.00 | 20/20 |
| Adversarial | Oracle upper bound | 0.9860 ? 0.0061 | 75,170 ? 922 | 0 | 1.9678 ? 0.0278 | 1.9678 | ? | ? | 20/20 |

Mean tokens to the sustained 0.72 target were 8,085 for Relevance Top-K, 9,568/9,529 for the one-probe
guard under all-cold/adversarial priors, and 13,478/11,127 for the sequential guard.

## 4. Reliability results

| Guard | All-cold false-trigger rate | Wilson 95% interval | Adversarial miss rate | Wilson 95% upper bound |
|---|---:|---:|---:|---:|
| Fixed one-probe | 2/20 = 10% | 2.8%?30.1% | 0/20 = 0% | 16.1% |
| Sequential `z=1.0` | 1/20 = 5% | 0.9%?23.6% | 0/20 = 0% | 16.1% |

The one-probe false triggers occurred on seeds 75 and 80. The sequential false trigger occurred on seed 75.
Every adversarial sequential run stopped as `confident-harmful` after exactly two cross-domain rounds.
For all-cold sequential runs, 18 stopped as `confident-acceptable`, one stopped as `confident-harmful`, and
one exhausted the maximum probe count.

Across all distinct Phase 0G development, held-out, and reliability seeds, the observed all-cold false-trigger
counts are:

- one-probe: 3/26;
- sequential `z=1.0`: 1/26.

These pooled counts are descriptive only because the initial development split participated in method
selection.

## 5. Paired comparison with Relevance Top-K

A seed-paired bootstrap with 50,000 resamples gives the following mean differences (guard minus Relevance):

| Condition | Guard | Reward difference | Exact reward/1k difference | 95% bootstrap interval for reward/1k difference |
|---|---|---:|---:|---:|
| All-cold | One-probe | +0.0077 | +0.0075 | -0.0124 to +0.0264 |
| Adversarial | One-probe | +0.0077 | +0.0082 | -0.0117 to +0.0272 |
| All-cold | Sequential | +0.0077 | -0.0603 | -0.0916 to -0.0293 |
| Adversarial | Sequential | +0.0077 | -0.0214 | -0.0410 to -0.0027 |

The one-probe mean efficiency is slightly above Relevance Top-K, but the paired intervals include zero; this
is not evidence of an efficiency win. The sequential guard is reliably less token-efficient in this grid.

## 6. Interpretation

### 6.1 Adversarial detection is strong but still imprecisely bounded

Both guards detected all 20 adversarial priors and restored all-cold learned-router reward. Nevertheless,
0/20 misses still permits a 95% Wilson upper bound of about 16%; substantially more trials would be needed
to claim a very small miss probability.

### 6.2 One-probe is not reliable enough to call a safe guard

A 10% all-cold trigger rate is too high for a paper claim of reliable prior classification. In the current
all-cold experiment, resetting to cold is operationally a no-op, so the trigger does not reduce downstream
reward. That makes all-cold an incomplete safety test: the real risk is falsely resetting a useful but
non-cold learned prior and discarding transferable utility.

### 6.3 Sequential validation trades safety for material cost

Sequential validation halves the observed all-cold trigger rate, but its variable all-cold probing cost
raises mean total tokens by 4,290 over Relevance Top-K. Its exact reward-per-token deficit is statistically
visible in the paired bootstrap. Increasing the confidence threshold alone is therefore unlikely to solve
the cost/reliability trade-off.

## 7. Decision

**Do not promote the one-probe guard as the final method and do not begin paid API experiments.** Also defer
full 128/512-rule formal scaling until the guard is tested on useful non-cold priors.

The next offline phase should add:

1. a benign/helpful learned-prior condition where a false reset has measurable opportunity cost;
2. deterministic stratified probe ordering that covers distinct domains and difficult rule-selection cases;
3. a small informative-probe comparison against random/stream-order probing;
4. held-out seeds and exact unamortized accounting unchanged;
5. explicit metrics for useful-prior retention, adversarial detection, false-reset loss, and guard cost.

The goal is no longer merely to reduce the all-cold trigger count. It is to demonstrate that the guard can
retain beneficial learned state while rejecting harmful state at a cumulative-token cost competitive with
Relevance Top-K.
