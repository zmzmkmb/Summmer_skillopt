# Phase 0I: Rollout-Aware Cold-Router Guard (Development v1)

Date: 2026-08-07

## Question

Phase 0H showed that a frozen probe comparator can reject a prior that is beneficial over the full online task stream. Phase 0I therefore compares cloned learned and cold states over the same probe trajectory while applying each router's real online credit updates.

This remains a synthetic, fully offline development experiment. It is not downstream LLM accuracy evidence.

## Implementation

`MethodSpec` adds:

```python
prior_guard_evaluation: str = "frozen"  # frozen | rollout
```

In `rollout` mode:

1. the current learned state is cloned;
2. the same router is initialized cold at utility 0.5;
3. both copies route the same stratified probe sequence;
4. rewards and per-rule credits are computed independently;
5. both copied states are updated after every probe event;
6. route tokens and any extra credit-assignment tokens for both trajectories are charged exactly.

The guard does not mutate the state used by the subsequent main experiment.

## Artifact

- config: `configs/acl2027/offline_continual_phase0i_rollout_guard_dev_v1.json`
- artifact: `artifacts/acl2027_continual_phase0i_rollout_guard_dev_v1`
- grid: 5 seeds (81-85) x 3 priors x 4 methods = 60/60 runs
- aggregate fingerprint: `da992c178a4ebb2bc63e5630dd7d287a57446e5786753de57d3b4c672067d60b`
- relevant regression suite: **48 passed**

Audit:

- missing runs: 0
- file-hash failures: 0
- config/schema failures: 0
- total-token identity failures: 0
- guard route/update token identity failures: 0

## Main results

| Method | All-cold triggers | Helpful/oracle false resets | Adversarial detections | Mean guard tokens: all-cold / oracle / adversarial | Oracle reward |
|---|---:|---:|---:|---:|---:|
| Frozen sequential, min 6 samples | 0/5 | 1/5 | 5/5 | 3,365 / 5,154 / 3,357 | 0.7445 |
| Rollout sequential, min 6 samples | 0/5 | 1/5 | 5/5 | 3,369 / 4,120 / 3,362 | 0.7445 |
| Rollout sequential, min 12 samples | 0/5 | **0/5** | **5/5** | 6,767 / 9,591 / 6,736 | **0.7553** |
| Rollout full 8 rounds | 0/5 | **0/5** | **5/5** | 13,543 / 13,715 / 13,466 | **0.7553** |

## Key finding

Rollout evaluation fixes the seed-83 false reset **only when the guard is not allowed to make a harmful-prior decision too early**.

For seed 83:

- frozen sequential min-6 resets after 6 rounds with margin -0.1700;
- rollout sequential min-6 resets prematurely after 2 rounds with margin -0.1385;
- rollout sequential min-12 continues to 8 rounds, recovers to margin -0.0186, and retains the helpful prior under the 0.06 tolerance;
- full rollout reaches the same decision.

Thus online state updates are necessary but not sufficient. A short rollout can initially reinforce or expose a misleading local disadvantage. The decision horizon must be long enough to measure trajectory value.

## Cost trade-off

The safe development setting, rollout sequential min-12, achieves the desired 5-seed decision pattern:

```text
all-cold false resets: 0/5
helpful-prior false resets: 0/5
adversarial detections: 5/5
```

But its mean guard cost is high:

- 6,767 tokens for all-cold;
- 9,591 tokens for helpful priors;
- 6,736 tokens for adversarial priors.

Its exact reward per 1k tokens is about 1.2990-1.3054 across conditions, below the lower-cost guards. Full eight-round rollout is much worse at roughly 13.5k guard tokens.

This is a successful **safety diagnostic**, not yet a token-efficient proposed method.

## Decision

Phase 0I passes the development decision-quality gate but fails the efficiency gate. Do not launch paid API experiments or the formal 128/512 scaling grid yet.

Proceed to a low-cost adaptive-horizon phase:

1. record cumulative margin and confidence bounds after every rollout round;
2. enforce a minimum observation horizon before any destructive reset;
3. allow early acceptance of clearly helpful priors;
4. allow early rejection only when harm is both large and non-recovering;
5. use margin trend/recovery evidence to prevent the seed-83 premature reset;
6. calibrate on separate seeds, then run a 20-seed reliability check.

The target is to retain the Phase 0I decision pattern while bringing adversarial/all-cold guard cost back toward 3.4k and helpful-prior cost well below 9.6k tokens.
