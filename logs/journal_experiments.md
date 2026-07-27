# Journal Experiments Log

> **Last updated**: 2026-07-28 00:30
> Target: qwen-flash (DashScope) | Optimizer: deepseek-v4-flash (DeepSeek)

---

## Fix 1: MOAR Top-K 硬约束 ✅

- `optimize()` now accepts `top_k` parameter
- `_init_population`, `_create_offspring`, `_constraint_violations` all respect top-K
- `_repair_topk` drops random rules until |S| <= K
- Defence-in-depth assertions in `__init__.py`
- 38/38 tests pass (2 new top-K regression tests)
- Commit: `d46557b`

---

## Fix 2: Law Fast/Slow 四组消融 ✅ (partial)

| Method | Steps | Val Baseline | Best Val | Val Δ | Test Baseline | Best Test | Test Δ | Gate Accepts | Skill Chars | Status |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|------|
| **Initial** | — | 33.33% | 33.33% | — | 34.42% | 34.42% | — | — | 323 | ✅ |
| **Slow-only** | 68/68 | 38.79% | 41.82% | +3.03pp | 34.42% | **38.41%** | **+3.99pp** | 1 slow (epoch 3) | 376 | ✅ |
| **Fast-only** | 43/68 | 33.33% | 40.61% | +7.28pp | 34.42% | 35.87% | +1.45pp | 4 step (1,3,7,32) | 18,156 | ⚠️ 截断 |
| **Fast+Slow** | 26/68 | 32.73% | 36.97% | +4.24pp | 34.42% | 34.42% | 0.00pp | 3 step (3,15,16) | 14,602 | ⚠️ 截断 |

### Key findings:
1. **Slow-only wins**: best test gain (+3.99pp) with most compact skill (376 chars)
2. **Fast-only overfits**: val +7.28pp but test only +1.45pp — val/test gap 4.74pp, skill 18K chars
3. **Fast+Slow too early**: stopped at step 26, never reached slow_update
4. **165-item val set is too noisy** for gate-based early stopping

### Infrastructure issues:
- DeepSeek API balance exhausted at step 37 (402 Insufficient Balance), recovered ~2h later
- Fast-only resumed from step 37, stopped at step 43 by 11 consecutive rejects
- Fast+Slow auto-stopped at step 26 by 10 consecutive rejects
- Test evals manually run via `eval_only.py`

---

## Fix 3: Greedy + Exact baselines ✅

- `scripts/moar_baselines.py`: standalone comparison tool
- Greedy: incremental weighted selection, 1.6ms/query, avg 2.0 rules
- Exact: brute-force 2^n enumeration (n=8 → 218 subsets), 2.4ms/query, avg 1.0 rule
- Commit: `5021b40`

---

## Fix 4: 规则库规模缩放实验 ❌ (not started)

---

## Next steps (blocked by API budget):

1. [ ] Re-run Law Fast-only with larger val set (to fix overfitting)
2. [ ] Philosophy Fast/Slow ablation (299 train / 75 val)
3. [ ] Math Fast/Slow ablation (800 train / 200 val)
4. [ ] Multi-seed (seed=43, 44)
5. [ ] MOAR + BM25 baseline
6. [ ] Rule library scaling (16→50→200)
