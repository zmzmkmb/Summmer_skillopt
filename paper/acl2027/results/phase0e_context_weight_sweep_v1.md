# Phase 0E: Global?Contextual Shrinkage Sweep (v1)

## Scope and audit

This experiment uses synthetic oracle per-rule credit to isolate estimator quality. It is not downstream
LLM accuracy and does not assume that oracle credit is available in deployment.

- Artifact: `artifacts/acl2027_continual_phase0e_v1`
- Config: `configs/acl2027/offline_continual_phase0e_v1.json`
- Grid: 3 seeds ? 2 utility initialisations ? 11 methods = **66/66 runs**
- Tests: **28 passed**
- File-hash audit: **66/66 passed**
- Total-token identity audit: **66/66 passed**
- Aggregate fingerprint: `25958030f9bec6855d59e7f8bbb9fed991c73b76c6ff16beaa336e07e51409b5`

## Methods

The sweep compared:

- global utility;
- fixed contextual weights 0.25, 0.50, 0.75, and 1.00;
- confidence-adaptive weights with evidence scales 2, 4, 8, and 16;
- Relevance Top-K and an exact oracle upper bound.

Adaptive weighting starts from global pooling and increases each rule's local-domain weight as its
local selection evidence accumulates.

## Aggregate results

| Method | All-cold reward | Adversarial reward | Macro reward | Worst-condition reward | Mean tokens | Harmful selection |
|---|---:|---:|---:|---:|---:|---:|
| Relevance Top-K | 0.7435 | **0.7435** | **0.7435** | **0.7435** | 77,293 | 0.3411 |
| Global oracle credit | 0.7876 | 0.6177 | 0.7026 | 0.6177 | 77,201 | 0.2427 |
| Fixed context 0.25 | 0.7965 | 0.6244 | **0.7104** | 0.6244 | 77,055 | 0.2385 |
| Fixed context 0.50 | 0.7924 | **0.6283** | **0.7104** | **0.6283** | 76,829 | 0.2424 |
| Fixed context 0.75 | 0.7981 | 0.5999 | 0.6990 | 0.5999 | 76,790 | 0.2474 |
| Fixed context 1.00 | 0.7974 | 0.5617 | 0.6796 | 0.5617 | **76,482** | 0.2486 |
| Adaptive scale 2 | **0.8007** | 0.6162 | 0.7085 | 0.6162 | 76,872 | 0.2331 |
| Adaptive scale 4 | 0.8005 | 0.6202 | 0.7103 | 0.6202 | 76,918 | **0.2317** |
| Adaptive scale 8 | 0.7910 | 0.6215 | 0.7063 | 0.6215 | 77,038 | 0.2354 |
| Adaptive scale 16 | 0.7917 | 0.6215 | 0.7066 | 0.6215 | 77,131 | 0.2376 |
| Exact oracle upper bound | 0.9831 | 0.9831 | 0.9831 | 0.9831 | 75,414 | 0.0362 |

## Findings

### 1. Moderate shrinkage fixes the fixed-0.75 failure

Fixed weights 0.25 and 0.50 obtained the best macro reward, about **0.7104**, improving over global
0.7026. Fixed 0.50 also had the best learned-router worst-condition reward, 0.6283.

The previous default 0.75 over-localised under adversarial initialisation. Full localisation (1.00) was
worse still, dropping adversarial reward to 0.5617.

### 2. Adaptive shrinkage is competitive and reduces harmful selections

Adaptive scale 4 reached macro reward 0.7103, essentially matching the best fixed settings, while
achieving the lowest harmful-rule selection rate, 0.2317. It improved over global in adversarial reward
on average by +0.0025 and in all-cold reward by +0.0129.

However, with only three seeds, the paired gains are not uniformly positive. This is evidence that the
mechanism is promising, not final statistical confirmation.

### 3. Relevance Top-K is still the strongest robust baseline

Even with synthetic oracle credit, no learned utility method beat Relevance Top-K on macro or
worst-condition reward because adversarial initial utilities remain damaging over the 150-task horizon.

This is a critical negative result. The next method must include prior validation/reset or a fallback to
relevance routing; estimator tuning alone is insufficient.

### 4. Cumulative-token convergence confirms the robustness gap

For the 0.72 rolling-reward target:

- Relevance Top-K: 3/3 successes in both conditions, about 7.1k tokens.
- Fixed context 0.50: 3/3 all-cold successes at 7.0k tokens; only 2/3 adversarial successes, mean 33.5k
  tokens among successes.
- Adaptive scale 4: 3/3 all-cold successes at 7.0k tokens; only 1/3 adversarial success at 36.5k tokens.

Thus, average final reward alone would hide the main deployment risk: under a bad prior, learned routing
may fail to reach the target at all within the available cumulative-token budget.

## Decision

**Do not scale to 128/512 yet.** The current evidence supports adaptive/moderate shrinkage as an
estimator component, but the complete learned router is still less robust than Relevance Top-K.

The next offline method experiment should add a charged prior-sanity guard:

1. Evaluate the learned router and Relevance Top-K on a small held-out probe set.
2. If the learned prior underperforms by more than a tolerance, reset utilities to cold or temporarily
   fall back to relevance routing.
3. Charge every guard probe token.
4. Combine the guard with adaptive scale 4 and fixed 0.50.
5. Test both oracle credit and shared credit.

Only after the guarded method beats Relevance Top-K on worst-condition reward and retains acceptable
reward per 1k total tokens should rule-library scaling begin.
