# Phase 0A offline continual-routing results (v1)

**Date:** August 6, 2026  
**Scope:** deterministic synthetic instrumentation only; these rewards are not downstream LLM accuracy.

## Run status

- Complete grid: **96/96 runs**
- Seeds: **41, 42, 43**
- Utility conditions: **All-Cold, noisy, shuffled, adversarial**
- Methods: **8** policy/credit combinations
- Tasks per run: **120**, with cross-domain probes after each block
- Aggregate fingerprint: `4dff00ec504ed4b8c7da0d3611f1ea8d3d6e31e09fa972bb3a12a64d56946ee2`

## All-Cold main diagnostic

| Method | Mean reward | Total tokens | Reward / 1K tokens | Cumulative regret | Utility rank corr. | Target successes |
|---|---:|---:|---:|---:|---:|---:|
| oracle_upper_bound | 0.829 +/- 0.020 | 49,240 | 2.021 | 0.0 | 0.955 | 3/3 |
| relevance_topk | 0.398 +/- 0.027 | 56,872 | 0.838 | 51.8 | -0.033 | 0/3 |
| greedy_shared | 0.396 +/- 0.013 | 56,634 | 0.839 | 52.0 | 0.138 | 0/3 |
| greedy_loo | 0.398 +/- 0.025 | 143,911 | 0.332 | 51.8 | 0.222 | 0/3 |
| ucb_shared | 0.390 +/- 0.008 | 57,324 | 0.817 | 52.7 | 0.098 | 0/3 |
| thompson_shared | 0.375 +/- 0.006 | 57,029 | 0.789 | 54.5 | 0.241 | 0/3 |
| exact_utility_loo | 0.398 +/- 0.021 | 145,206 | 0.329 | 51.7 | 0.243 | 0/3 |
| random | 0.099 +/- 0.005 | 56,726 | 0.210 | 87.6 | -0.033 | 0/3 |

## Findings

1. **The accounting harness works.** Every run records inference, credit-update, probe, and cumulative tokens; deterministic tests reproduce stream and result fingerprints.
2. **Leave-one-out credit is currently uneconomical.** `greedy_loo` uses **2.53x** the tokens of relevance Top-K while achieving essentially the same synthetic reward.
3. **Online global utility is not yet a winning signal.** Greedy shared, UCB, and Thompson do not consistently beat relevance Top-K under All-Cold initialization.
4. **There is substantial recoverable headroom.** The oracle upper bound exceeds relevance Top-K by **0.432 mean reward**, so the problem is not saturated.
5. **The configured Tokens-to-Target gate is intentionally strict.** At target reward 0.72, only the oracle reaches the target in all three seeds; no deployable policy reaches it.
6. **Utility corruption matters most for exploration-heavy policies.** Thompson is visibly less stable under shuffled/adversarial priors, while relevance Top-K is invariant by construction.

## Decision

Phase 0A passes the **instrumentation/reproducibility gate** but fails the **method-quality gate**. Do not start paid SearchQA calls yet.

## Immediate Phase 0B work

1. Replace the single global utility estimate with a contextual estimate conditioned on task/domain features.
2. Add a practical per-rule credit estimator that does not require one leave-one-out model call per selected rule.
3. Add validation-based non-regression gates and report safety together with plasticity and update acceptance rate.
4. Connect BM25, TF-IDF, current Greedy, and MOAR adapters to this same cost ledger.
5. After the contextual baseline improves, extend the provenance-preserving rule suite to 128 and then 512 rules.

The next code milestone is therefore **contextual online credit + non-regression gate**, not a paid API sweep.
