# JoS Experiment v1 — Formal Results

> Tag: `jos-experiment-v1` | Commit: `f4ae9b4` | 2026-07-29

## Summary

200-item SearchQA test set, 2000-token budget, top-5 rule selection.
All results use the same skill file (`outputs/searchqa_rag/best_skill.md`, 13,772 chars, 8 dynamic rules).

> **Audit status:** `aggregate_results.csv` is a historical, unaudited export and double-counts a copied qwen3.6-flash run. Use `audit_report.json`, `audited_results.csv`, and `audited_baselines.csv` as the canonical statistics for paper writing.

### qwen-flash (DashScope)

| Method | Acc ± SD | Rules | Sel Tokens | Budget Viol | Seeds |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 63.00% ± 0.50% | 0 | 0 | 0 | ×3 |
| TF-IDF Top-5 | 67.00% ± 1.00% | 0* | 0* | 0 | ×3 |
| **MOAR** | **70.67% ± 0.29%** | 5.0 | 1918 | 0 | ×3 |
| BM25 | 72.50% ± 0.50% | 4.5 | 1947 | 30 (10/run) | ×3 |
| Greedy-Cold | 71.50% ± 0.50% | 5.0 | 1207 | 0 | ×3 |
| Greedy-Utility | 71.67% ± 0.29% | 5.0 | 1204 | 0 | ×3 |

\* TF-IDF selected_indices were not saved in original formal runs.

### qwen3.6-flash (MaaS)

| Method | Acc ± SD | Rules | Sel Tokens | Budget Viol | Seeds |
|------|:--:|:--:|:--:|:--:|:--:|
| Core Only | 83.50% ± 0.71% | 0 | 0 | 0 | ×2 (42/43) |
| TF-IDF Top-5 | 83.50% ± 1.41% | 0* | 0* | 0 | ×2 (42/43) |
| **MOAR** | **84.50% ± 0.00%** | 5.0 | 1918 | 0 | ×2 (42/43) |

### Auxiliary targetL_anthropic condition (not directly comparable to MaaS table)

| Method | Acc +/- SD | Rules | Sel Tokens | Budget Viol | Seeds |
|------|:--:|:--:|:--:|:--:|:--:|
| BM25 | 81.67% +/- 0.29% | 4.49 | 1947 | 30 (10/run) | x3 (42/43/44) |
| Greedy-Cold | 77.25% +/- 0.35% | 5.0 | 1207 | 0 | x2 (43/44) |
| Greedy-Utility | 79.00% +/- 0.00% | 5.0 | 1204 | 0 | x2 (43/44) |

> This folder records a separate historical execution condition/commit. Greedy rep42 is not present, so these rows are provenance evidence rather than a complete main-table comparison.

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
- Greedy baselines respect the 2000-token budget; BM25 has 10 one-token-over-budget edge cases per preserved run
- BM25 and Greedy methods achieve slightly higher accuracy; BM25 uses a similar token budget (~1947 vs MOAR ~1918), while Greedy uses substantially fewer tokens (~1204)

## File Manifest

See `run_manifest.json` for full file listing and metadata. The offline audit emits `audit_report.json`, `audited_results.csv`, and `audited_baselines.csv`.

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

# Canonical audit and aggregation (offline, no API)
python scripts/audit_jos_artifacts.py --artifact-root artifacts/jos_experiment_v1
python scripts/aggregate_jos_formal.py
python scripts/aggregate_baseline_reps.py

# Additional paired/bootstrap analysis
python scripts/analyze_jos_results.py --baselines bm25,greedy-cold,greedy-util --bootstrap
```

## Notes

- Seed 44 for qwen3.6-flash is a copy of seed 42 (MaaS quota exhausted mid-run)
- TF-IDF selected_indices are missing from original formal output (pre-fix)
- Enriched files add: `selected_tokens`, `budget_violated`, corrected `n_rules`
- Budget violations in BM25 (10/200) are 1-token edge cases from `\n\n` separator
