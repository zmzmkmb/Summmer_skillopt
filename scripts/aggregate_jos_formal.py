#!/usr/bin/env python3
"""汇总 JoS formal 实验 — 6 个 JSON → 2 张目标模型对比表 + per-sample merge."""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(SCRIPT_DIR), "outputs")

FILES = [
    ("qwen-flash", 42, "jos_formal_targetS_seed42.json"),
    ("qwen-flash", 43, "jos_formal_targetS_seed43.json"),
    ("qwen-flash", 44, "jos_formal_targetS_seed44.json"),
    ("qwen3.6-flash", 42, "jos_formal_targetL_seed42.json"),
    ("qwen3.6-flash", 43, "jos_formal_targetL_seed43.json"),
    ("qwen3.6-flash", 44, "jos_formal_targetL_seed44.json"),
]

# ── 读取 ──────────────────────────────────────────────────
raw = defaultdict(list)  # model -> [(seed, results_dict)]
for model, seed, fname in FILES:
    path = os.path.join(OUT, fname)
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    raw[model].append((seed, d["results"]))

# ── 汇总 ──────────────────────────────────────────────────
print("=" * 72)
print("  JoS Formal Experiment Summary — 200 items × 3 seeds")
print("=" * 72)

for model, entries in raw.items():
    print(f"\n── Target: {model} ──\n")
    methods = list(entries[0][1].keys())
    header = f"{'Method':<16} {'Acc (S42/S43/S44)':<24} {'Mean±Std':<14} {'AvgRules':<10} {'AvgChars':<10}"
    print(header)
    print("-" * len(header))
    for method in methods:
        accs = []
        avgs_rules = []
        avgs_chars = []
        for seed, res in entries:
            accs.append(res[method]["accuracy"])
            avgs_rules.append(res[method]["avg_rules"])
            avgs_chars.append(res[method]["avg_chars"])
        acc_str = " / ".join(f"{a:.4f}" for a in accs)
        mean = sum(accs) / len(accs)
        std = (sum((a - mean)**2 for a in accs) / len(accs)) ** 0.5
        avg_r = sum(avgs_rules) / len(avgs_rules)
        avg_c = sum(avgs_chars) / len(avgs_chars)
        print(f"{method:<16} {acc_str:<24} {mean:.4f}±{std:.4f}  {avg_r:<10.1f} {avg_c:<10.0f}")
    # Δ vs Core Only
    print(f"\n{'':>6}Δ vs Core Only:")
    base = {s: res[methods[0]]["accuracy"] for s, res in entries}
    base_mean = sum(base.values()) / len(base)
    for method in methods[1:]:
        accs_m = []
        for seed, res in entries:
            accs_m.append(res[method]["accuracy"])
        m_mean = sum(accs_m) / len(accs_m)
        deltas = [accs_m[i] - list(base.values())[i] for i in range(len(base))]
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean)**2 for d in deltas) / len(deltas)) ** 0.5
        print(f"    {method}: +{d_mean*100:.2f}pp ± {d_std*100:.2f}pp")

print("\n" + "=" * 72)
print("  Done.")
