# Journal Experiments Log

> **Last updated**: 2026-07-29
> **Target**: qwen3.6-flash (MaaS token-plan) | **Optimizer**: deepseek-v4-flash (DeepSeek 直连)
> **Previous Target**: qwen-flash (DashScope) — all experimental data below

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

### Math (800 train / 200 val / 351 test) ✅

| Method | Steps | Best Val | Test | Δ Test | Gate Accepts | Skill Chars |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| **Initial** | — | 49.00% | 88.03% | — | — | 323 |
| **Slow-only** | 80/80 | 89.00% | 89.17% | +1.14pp | 1 slow (epoch 2) | 3,602 |
| **Fast-only** | 25/80 | 92.50% | **93.16%** | **+5.13pp** | 3 step (3,4,12) | 9,985 |

### Complete Fast/Slow Summary

| Domain | Initial | Slow Δ | Fast Δ | Winner |
|------|:--:|:--:|:--:|:--:|
| **Law** | 34.42% | **+3.99pp** | +1.45pp | Slow |
| **Philosophy** | 56.80% | +6.40pp | **+12.00pp** | Fast |
| **Math** | 88.03% | +1.14pp | **+5.13pp** | Fast |

> **Key**: Neither mechanism dominates — task-dependent. Law favours compact slow_update (376 chars), Philosophy/Math favour step-level rule injection.

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
| Target 模型 (current) | qwen3.6-flash (MaaS token-plan) |
| Target 模型 (experiments) | qwen-flash (DashScope) |
| Optimizer 模型 | deepseek-v4-flash (DeepSeek 直连) |
| Adapter | `skillopt/envs/mmlupro/` (pure, no SearchQA template) |
| Initial skill | `skillopt/envs/mmlupro/initial_skill.md` (323 chars) |
| Config | `configs/mmlupro/default.yaml` |
| Seed | 42 |
| 日志目录 | `logs/journal_experiments.md` |

---

## Appendix A: SearchQA 多基线规则选择对照 (qwen-flash)

| Method | Accuracy (200) | Rules | Chars | Latency |
|------|:--:|:--:|:--:|:--:|
| Core Only | 64.0% | 0 | 513 | 0ms |
| BM25 | 58.0% | 1.0 | 2,576 | <1ms |
| Greedy (cold) | 57.0% | 2.0 | 1,398 | 2ms |
| TF-IDF | 68.5% | 1.0 | 1,968 | 1ms |
| **MOAR** | **70.5%** | 1.1 | 1,673 | 278ms |

## Appendix B: 规则库规模 Scaling (200 queries)

| Rules | TF-IDF ms/q | MOAR ms/q | MOAR chars |
|------:|:-----------:|:---------:|:----------:|
| 8 | 1.2 | 299 | 1,158 |
| 28 | 1.4 | 523 | 1,429 |
| 32 | 1.6 | 383 | 1,421 |
| 135 | 1.5 | 428 | 783 |

> Both sub-linear. TF-IDF flat (~1.5ms). MOAR +43% for 17× rule growth.

## Appendix C: 全部 Commits

| Commit | 内容 |
|--------|------|
| `bde2cd0` | Rule scaling experiment (8→135 rules) |
| `94e1194` | Complete 3-domain Fast/Slow ablation |
| `76ee3ff` | BM25 + Greedy inference baselines |
| `5385dd2` | BM25 + Greedy full baselines |
| `4112531` | Law + Philosophy Fast/Slow tables |
| `07bdd3b` | Tokenizer + stable rule IDs + test isolation |
| `d46557b` | NSGA-II top-K hard constraint |
