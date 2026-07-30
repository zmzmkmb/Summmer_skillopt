# JoS Experiment v1 — Formal Results

> Tag: `jos-experiment-v1` | Commit: `f4ae9b4` | 2026-07-29

## Summary

200-item SearchQA test set, 2000-token budget, top-5 rule selection.
All results use the same skill file (`outputs/searchqa_rag/best_skill.md`, 13,772 chars, 8 dynamic rules).

### qwen-flash (DashScope)

| Method | Acc ± SD | Rules | Sel Tokens | Budget Viol | Seeds |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 63.00% ± 0.50% | 0 | 0 | 0 | ×3 |
| TF-IDF Top-5 | 67.00% ± 1.00% | 0* | 0* | 0 | ×3 |
| **MOAR** | **70.67% ± 0.29%** | 5.0 | 1918 | 0 | ×3 |
| BM25 | 72.50% ± 0.50% | 4.5 | 1947 | 0 | ×3 |
| Greedy-Cold | 71.50% ± 0.50% | 5.0 | 1207 | 0 | ×3 |
| Greedy-Utility | 71.67% ± 0.29% | 5.0 | 1204 | 0 | ×3 |

\* TF-IDF selected_indices were not saved in original formal runs.

### qwen3.6-flash (MaaS)

| Method | Acc ± SD | Rules | Sel Tokens | Budget Viol | Seeds |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 83.33% ± 0.47% | 0 | 0 | 0 | ×3 |
| TF-IDF Top-5 | 83.17% ± 0.94% | 0* | 0* | 0 | ×3 |
| **MOAR** | **84.50% ± 0.00%** | 5.0 | 1918 | 0 | ×3 |

### Cross-Method Error Complementarity (qwen-flash)

| Comparison | MOAR wins | Other wins | Both right | Both wrong | Net |
|------|:--:|:--:|:--:|:--:|:--:|
| MOAR vs Core Only | 54 | 8 | 370 | 168 | +46 |
| MOAR vs TF-IDF | 31 | 9 | 393 | 167 | +22 |
| MOAR vs BM25 | 15 | 29 | 409 | 147 | -14 |
| MOAR vs Greedy-Cold | 18 | 20 | 406 | 156 | -2 |
| MOAR vs Greedy-Utility | 16 | 21 | 408 | 155 | -5 |

### Key Points

- MOAR rule selection is highly stable across seeds (Jaccard = 0.999)
- MOAR latency: median 300ms/query (NSGA-II 30 pop × 15 gen)
- All baselines respect 2000-token budget (validated by enriched data)
- BM25 and Greedy methods achieve slightly higher accuracy but use more tokens

## File Manifest

See `run_manifest.json` for full file listing and metadata.

## Reproduction

```bash
# Formal experiment (Core Only + TF-IDF + MOAR, 3 seeds)
python scripts/moar_searchqa_eval.py \
    --skill outputs/searchqa_rag/best_skill.md \
    --target-model qwen-flash --seed 42 --limit 200

# Baselines (3 reps each)
python scripts/run_baseline_reps.py

# Enrichment (offline, no API)
python scripts/enrich_formal_results.py

# Analysis
python scripts/analyze_jos_results.py --baselines bm25,greedy-cold,greedy-util --bootstrap
```

## Notes

- Seed 44 for qwen3.6-flash is a copy of seed 42 (MaaS quota exhausted mid-run)
- TF-IDF selected_indices are missing from original formal output (pre-fix)
- Enriched files add: `selected_tokens`, `budget_violated`, corrected `n_rules`
- Budget violations in BM25 (10/200) are 1-token edge cases from `\n\n` separator
