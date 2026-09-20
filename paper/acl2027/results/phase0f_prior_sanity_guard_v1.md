# Phase 0F: Charged Prior-Sanity Guard (v1)

## Scope and audit

This experiment is synthetic offline instrumentation. Its reward is not downstream LLM accuracy.
The purpose is to test whether a held-out validation guard can detect harmful utility priors before the
continual task stream, while charging every candidate and Relevance Top-K validation token.

- Artifact: `artifacts/acl2027_continual_phase0f_v1`
- Config: `configs/acl2027/offline_continual_phase0f_v1.json`
- Grid: 3 seeds ? 2 utility initialisations ? 12 methods = **72/72 runs**
- Guard: phase-0 probes from all three domains; trigger when learned mean reward is more than 0.06 below Relevance Top-K
- Action: reset the utility state to an all-0.5 cold prior; the learned selector then continues normally
- Tests: **33 passed**
- File-hash audit: **72/72 passed**
- Total-token identity audit: **72/72 passed**
- Aggregate fingerprint: `00716e99c3bcf2af929c16838f30833f9f08b8b4a26192abea7e4b9bedf71fd2`

The charged identity is:

```text
total_tokens = inference_tokens
             + credit_update_tokens
             + probe_tokens
             + gate_validation_tokens
             + guard_validation_tokens
```

## Implementation

`MethodSpec` now supports:

- `prior_guard = none | reset-cold | fallback-relevance`;
- `prior_guard_tolerance`;
- `prior_guard_probe_domains`.

Before the task stream, the guard evaluates the configured learned router and Relevance Top-K on the
same held-out phase-0 events with identical top-k and token budget. Both routes are fully charged. The
artifact records per-domain scores, means, margin, trigger decision, action, candidate tokens, baseline
tokens, and total guard tokens. Guard history is included in the deterministic run fingerprint.

## Aggregate results

| Method | All-cold reward | Adversarial reward | Macro | Worst | Mean total tokens | Reward / 1k tokens | Target successes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Relevance Top-K | 0.7435 | 0.7435 | 0.7435 | 0.7435 | 77,293 | **1.4447** | 6/6 |
| Global oracle credit | 0.7876 | 0.6177 | 0.7026 | 0.6177 | 77,201 | 1.3670 | 4/6 |
| Fixed 0.50 oracle | 0.7924 | 0.6283 | 0.7104 | 0.6283 | 76,829 | 1.3877 | 5/6 |
| Adaptive s4 oracle | 0.8005 | 0.6202 | 0.7103 | 0.6202 | 76,918 | 1.3873 | 4/6 |
| **Fixed 0.50 oracle + guard** | 0.7924 | 0.7924 | 0.7924 | 0.7924 | 91,394 | 1.3028 | 6/6 |
| **Adaptive s4 oracle + guard** | **0.8005** | **0.8005** | **0.8005** | **0.8005** | 91,408 | 1.3159 | 6/6 |
| Global shared credit | 0.7430 | 0.5361 | 0.6395 | 0.5361 | 75,230 | 1.2765 | 3/6 |
| Fixed 0.50 shared | 0.7493 | 0.5244 | 0.6368 | 0.5244 | 75,133 | 1.2723 | 3/6 |
| Adaptive s4 shared | 0.7487 | 0.5403 | 0.6445 | 0.5403 | 75,301 | 1.2847 | 3/6 |
| **Fixed 0.50 shared + guard** | 0.7493 | 0.7493 | 0.7493 | 0.7493 | 88,900 | 1.2658 | 6/6 |
| **Adaptive s4 shared + guard** | 0.7487 | 0.7487 | 0.7487 | 0.7487 | 89,075 | 1.2620 | 6/6 |
| Exact oracle upper bound | 0.9831 | 0.9831 | 0.9831 | 0.9831 | 75,414 | 1.9564 | 6/6 |

`Target successes` counts seed-condition runs reaching the 0.72 sustained rolling-reward target.

## Findings

### 1. The guard perfectly separated the tested prior conditions

Across the 24 guarded runs:

- all-cold: **0/12 triggered**;
- adversarial: **12/12 triggered**.

All-cold margins ranged from -0.0543 to +0.0021, while adversarial margins ranged from -0.4299 to
-0.3441. The 0.06 tolerance therefore separated these conditions on all three diagnostic seeds.
This is only a synthetic three-seed calibration and must not be treated as a generally validated
threshold.

### 2. Reset-cold removed the adversarial-prior reward collapse

The guarded methods reproduced their corresponding all-cold task-stream reward after an adversarial
initialisation:

- adaptive s4 oracle: 0.6202 ? **0.8005** (+0.1803);
- fixed 0.50 oracle: 0.6283 ? **0.7924** (+0.1641);
- adaptive s4 shared: 0.5403 ? **0.7487** (+0.2084);
- fixed 0.50 shared: 0.5244 ? **0.7493** (+0.2249).

This safety result was achieved by resetting and continuing learned routing, not by permanently falling
back to Relevance Top-K.

### 3. Shared-credit routing now reaches the target under adversarial priors

Without the guard, both shared-credit contextual methods reached the target in 0/3 adversarial runs.
With reset-cold, both reached it in 3/3. Thus the guard solves the prior-initialisation failure even when
cheap shared credit is used.

However, the guard raises mean tokens-to-target from roughly 7.1k in clean runs to roughly 20.3k,
because approximately 13.2k?13.6k validation tokens are paid before the first task outcome.

### 4. The current guard is robust but not token-efficient enough

Compared with Relevance Top-K:

- adaptive s4 oracle + guard improves reward by +0.0570, but uses 18.0% more total tokens and has 8.7%
  lower reward per 1k tokens;
- fixed 0.50 shared + guard improves reward by only +0.0058, while using 14.8% more total tokens and
  having 12.2% lower reward per 1k tokens.

Even when all-cold is accepted without reset, the guard still pays the full candidate-plus-baseline probe
cost. Therefore the method currently retains reward gains but not cumulative-token efficiency.

### 5. The experiment validates prior diagnosis, not real-model generalisation

The guard uses synthetic expected reward on held-out simulator probes. The threshold was selected after
inspecting synthetic diagnostic seeds. A formal experiment must tune the threshold on separate
development seeds/tasks and evaluate it on untouched test streams. Real API/model experiments must use
objective task outcomes rather than simulator utility.

## Decision

**Do not scale to 128/512 rules yet.** Phase 0F passes the robustness, target-reliability, and
non-fallback criteria, but fails the token-efficiency criterion against Relevance Top-K.

The next offline experiment should be Phase 0G: a low-cost sequential prior guard.

1. Vary probe counts per domain: 1, 2, 4, and 8.
2. Add sequential early stopping once the learned-minus-relevance margin is confidently above or below
   the threshold.
3. Reuse baseline probe outcomes across methods when the probe set, budget, top-k, and stream are
   identical, while still reporting the amortised and unamortised cost separately.
4. Tune thresholds on separate development seeds and evaluate on held-out seeds.
5. Preserve the requirements: 0 false resets on acceptable priors, reliable adversarial detection,
   6/6 target success, and no permanent relevance fallback.

Only after the guarded shared-credit method approaches Relevance Top-K in reward per 1k total tokens
should the library expand to 128/512 rules or paid model experiments begin.
