# Journal Experiments Log

> **Last updated**: 2026-07-28 00:20
> Target: qwen-flash (DashScope) | Optimizer: deepseek-v4-flash (DeepSeek)

---

## Fix 1: MOAR 实现修正 ✅

| 修正项 | 修改文件 | Commit |
|------|------|:--:|
| Top-K 硬约束 | `nsga2.py` | `d46557b` |
| 真实 tokenizer (tiktoken cl100k_base) | `tokenizer.py`, `features.py`, `__init__.py` | `07bdd3b` |
| 规则稳定 ID (SHA256 hash) | `tracker.py` | `07bdd3b` |
| 测试集隔离 (frozen flag) | `tracker.py`, `__init__.py` | `07bdd3b` |
| 38/38 tests pass | — | `07bdd3b` |

---

## Fix 2: Fast/Slow 四组消融

### Law (660 train / 165 val / 276 test) ✅

| Method | Steps | Best Val | Test | Δ Test | Gate Accepts | Skill Chars |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| **Initial** | — | 33.33% | 34.42% | — | — | 323 |
| **Slow-only** | 68/68 | 41.82% | **38.41%** | **+3.99pp** | 1 slow (epoch 3) | 376 |
| **Fast-only** | 43/68 | 40.61% | 35.87% | +1.45pp | 4 step | 18,156 |
| **Fast+Slow** | 26/68 | 36.97% | 34.42% | 0.00pp | 3 step | 14,602 |

### Philosophy (299 train / 75 val / 125 test) ✅

| Method | Steps | Best Val | Test | Δ Test | Gate Accepts | Skill Chars |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| **Initial** | — | 58.67% | 56.80% | — | — | 323 |
| **Slow-only** | 32/32 | 62.67% | 63.20% | +6.40pp | 2 slow (epoch 2,4) | 3,694 |
| **Fast-only** | 14/32 | 66.67% | **68.80%** | **+12.00pp** | 2 step (step 2,4) | 7,563 |
| **Fast+Slow** | — | — | — | — | — | — |

### Math (800 train / 200 val / 351 test) 🔄

| Method | Steps | Best Val | Test | Δ Test | Gate Accepts | Skill Chars |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| **Initial** | — | 49.00% | 88.03% | — | — | 323 |
| **Slow-only** | 80/80 | 89.00% | 89.17% | +1.14pp | 1 slow (epoch 2) | 3,602 |
| **Fast-only** | 🔄 | — | — | — | — | — |
| **Fast+Slow** | — | — | — | — | — | — |

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
