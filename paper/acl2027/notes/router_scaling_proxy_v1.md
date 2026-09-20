# Router scaling proxy v1

**Run date:** 2026-08-06  
**Status:** selector-only diagnostic; not a task-accuracy result

## Scope and configuration

This run evaluates routing behavior over the deterministic nested 8/16/32/64-rule libraries without making any LLM or external API call. It uses the first 200 materialized SearchQA test questions, `top_k=5`, a strict 2,000-token rendered-selection budget, seed 42, and the frozen historical utility file. MOAR uses population size 30 and 15 generations.

Generated artifacts:

- `paper/acl2027/results/router_scaling_proxy_v1.json`: run metadata, summaries, and per-query selections.
- `paper/acl2027/results/router_scaling_proxy_v1.csv`: generated summary table.

The base-selection precision proxy is the fraction of selected rules that belong to the fixed eight-rule SearchQA base set. The base-query hit-rate proxy is the fraction of queries selecting at least one base rule. The distractor-query rate is the fraction selecting at least one cross-task distractor. These are library-composition diagnostics, not correctness measurements.

## Headline results

| Rules | Method | Mean latency (ms) | Mean tokens | Base precision proxy | Base hit proxy | Distractor-query rate |
|---:|---|---:|---:|---:|---:|---:|
| 8 | TF-IDF | 4.18 | 1761.8 | 1.000 | 1.000 | 0.000 |
| 8 | BM25 | 0.25 | 1942.6 | 1.000 | 1.000 | 0.000 |
| 8 | Greedy-Cold | 1.83 | 1206.6 | 1.000 | 1.000 | 0.000 |
| 8 | Greedy-Utility | 2.37 | 1204.0 | 1.000 | 1.000 | 0.000 |
| 8 | MOAR | 315.97 | 1397.0 | 1.000 | 1.000 | 0.000 |
| 64 | TF-IDF | 4.43 | 1291.5 | 0.155 | 0.425 | 0.990 |
| 64 | BM25 | 0.43 | 1712.9 | 0.292 | 0.715 | 0.965 |
| 64 | Greedy-Cold | 7.10 | 499.4 | 0.193 | 0.860 | 1.000 |
| 64 | Greedy-Utility | 6.21 | 1201.8 | 0.998 | 1.000 | 0.010 |
| 64 | MOAR | 355.53 | 1188.9 | 0.580 | 0.995 | 0.975 |

All reported conditions have zero final rendered-token budget violations.

## Interpretation

1. **Library growth exposes distractor sensitivity.** TF-IDF, BM25, and Greedy-Cold lose substantial base-rule purity as cross-task distractors are added. Their 64-rule base precision proxies are 0.155, 0.292, and 0.193 respectively.
2. **Frozen utility is a strong prior, not a fair accuracy win by itself.** Greedy-Utility retains 0.998 base precision at 64 rules because the historical base rules have learned utility while newly introduced distractors are cold. This diagnostic confirms that utility can protect a known base set, but it does not demonstrate generalization or downstream answer quality.
3. **MOAR is not currently justified as the preferred selector.** At 64 rules it reaches 0.580 base precision while taking 355.53 ms/query, versus 0.998 at 6.21 ms/query for Greedy-Utility. On this machine and configuration, MOAR is about 57 times slower. It should remain a baseline until downstream accuracy or a harder utility setting shows a compensating benefit.
4. **Base hit rate alone is insufficient.** MOAR still selects a base rule on 99.5% of 64-rule queries, but selects at least one distractor on 97.5%. Reporting only hit rate would hide substantial prompt contamination.
5. **The result supports the paper thesis only weakly.** It motivates studying credit assignment and utility robustness, but cannot support claims about model accuracy, non-regression, or continual learning.

## Required follow-up experiments

The next selector study should keep the same nested libraries and paired query set while varying utility information:

1. **Frozen learned utility:** current diagnostic; known-base prior.
2. **All-cold utility:** every rule starts with identical utility.
3. **Noisy utility:** perturb utility values over multiple declared seeds.
4. **Adversarial utility:** assign high utility to plausible distractors to test failure resistance.
5. **Online utility:** update per-rule credit on a chronological stream and report regret/calibration.
6. **Downstream model evaluation:** measure exact-match/task accuracy, token use, latency, and non-regression with at least two model families.

For the paper, proxy tables should be placed in analysis or infrastructure validation, not in the main task-performance table.

## Reproduction

```bash
python scripts/build_acl2027_scaling_libraries.py
python scripts/evaluate_acl2027_router_scaling.py --limit 200
```
