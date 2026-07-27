# Journal Experiments Log

> **Last updated**: 2026-07-28 00:20
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

## Fix 2: Fast/Slow 四组消融

### Law (660 train / 165 val / 276 test) ✅

| Method | Steps | Val Baseline | Best Val | Val Δ | Test Baseline | Best Test | Test Δ | Gate Accepts | Skill | Status |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|------|
| **Initial** | — | 33.33% | — | — | 34.42% | — | — | — | 323 | ✅ |
| **Slow-only** | 68/68 | 38.79% | 41.82% | +3.03pp | 34.42% | **38.41%** | **+3.99pp** | 1 slow (epoch 3) | 376 | ✅ |
| **Fast-only** | 43/68 | 33.33% | 40.61% | +7.28pp | 34.42% | 35.87% | +1.45pp | 4 step (1,3,7,32) | 18,156 | ⚠️ 截断 |
| **Fast+Slow** | 26/68 | 32.73% | 36.97% | +4.24pp | 34.42% | 34.42% | 0.00pp | 3 step (3,15,16) | 14,602 | ⚠️ 截断 |

**结论**: Slow_update 用 48× 更少字符（376 vs 18,156）达到更好 test 增益（+3.99pp vs +1.45pp）。Step-level optimizer 在 Law 上过拟合：val/test 差距 4.74pp，165 题 val 集噪声过大。

### Philosophy (299 train / 75 val / 125 test) 🔄

| Method | Steps | Best Val | Gate Accepts | Status |
|------|:--:|:--:|:--:|------|
| **Initial** | — | 56.80% (test) | — | ✅ |
| **Slow-only** | 32/32 | 62.67% | 2 slow (epoch 2,4) | ✅ from `mmlupro_philosophy_true` |
| **Fast-only** | 1/32 | 58.67% (baseline) | 0 | 🔄 running |
| **Fast+Slow** | — | — | — | ⬜ |

### Math 🔲
### History 🔲

---

## Fix 3: Greedy + Exact baselines ✅

- `scripts/moar_baselines.py`: standalone comparison tool
- Greedy: 1.6ms/query, avg 2.0 rules selected
- Exact (2^8=218 subsets): 2.4ms/query, avg 1.0 rule
- Commit: `5021b40`

---

## Fix 4: 规则库规模缩放实验 ⬜

---

## 实验环境

| 项目 | 值 |
|------|:--|
| Target 模型 | qwen-flash (DashScope) |
| Optimizer 模型 | deepseek-v4-flash (DeepSeek) |
| Adapter | `skillopt/envs/mmlupro/` (pure, no SearchQA template) |
| Initial skill | `skillopt/envs/mmlupro/initial_skill.md` (323 chars) |
| Config | `configs/mmlupro/default.yaml` |
| Seed | 42 |
| 日志目录 | `logs/journal_experiments.md` |
