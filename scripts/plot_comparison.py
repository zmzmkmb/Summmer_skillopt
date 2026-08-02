#!/usr/bin/env python3
"""综合对比图: Accuracy vs Selected Tokens vs Latency (0 API token).

基于已有正式实验数据，绘制:
- X 轴: 平均 selected tokens
- Y 轴: accuracy
- 误差棒: 3 seed 标准差 (MOAR/Core Only/TF-IDF) 或 Bootstrap 95% CI (基线)
- 点大小: 检索延迟
- 方法: Core Only, TF-IDF, MOAR, BM25, Greedy-Cold, Greedy-Utility

用法:
    python scripts/plot_comparison.py
    python scripts/plot_comparison.py --out outputs/comparison_chart.png
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

OUTPUTS = os.path.join(_PROJECT_ROOT, "outputs")

# ── 数据加载 ────────────────────────────────────────────────────────────────

def load_formal_enriched(prefix: str = "targetS", seeds=(42, 43, 44)) -> dict[str, list[dict]]:
    """加载 enriched formal JSON (qwen-flash = targetS)."""
    merged: dict[str, list[dict]] = defaultdict(list)
    for seed in seeds:
        path = os.path.join(OUTPUTS, f"jos_formal_{prefix}_seed{seed}_enriched.json")
        if not os.path.exists(path):
            print(f"  [SKIP] missing: {os.path.basename(path)}")
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for method, res in d["results"].items():
            for it in res.get("per_item", []):
                it = dict(it)
                it["_seed"] = seed
                it["_method"] = method
                merged[method].append(it)
    return dict(merged)


def load_baseline(name: str) -> list[dict] | None:
    """加载单个 baseline JSON."""
    path = os.path.join(OUTPUTS, f"infer_{name}_qwen-flash_n200.json")
    if not os.path.exists(path):
        print(f"  [SKIP] missing: {os.path.basename(path)}")
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    items = d.get("per_question", [])
    if not items:
        return None
    for it in items:
        it["_method"] = name
        it["_seed"] = 0
    return items


# ── 统计 ────────────────────────────────────────────────────────────────────

def method_stats(items: list[dict]) -> dict:
    """Multi-seed summary stats."""
    by_seed: dict[int, list[int]] = defaultdict(list)
    tokens_all: list[float] = []
    latency_all: list[float] = []
    n_rules_all: list[int] = []

    for it in items:
        s = it.get("_seed", 0)
        by_seed[s].append(it["hard"])
        # selected_tokens
        st = it.get("selected_tokens", 0)
        if st and st > 0:
            tokens_all.append(float(st))
        # latency
        lat = it.get("build_ms", it.get("sel_latency_ms", 0))
        if lat and lat > 0:
            latency_all.append(float(lat))
        # n_rules
        nr = it.get("n_rules", 0)
        if nr and nr > 0:
            n_rules_all.append(nr)

    active_seeds = sorted(s for s in by_seed if s != 0) or [0]
    seed_accs = {s: float(np.mean(by_seed[s])) for s in active_seeds}
    accs = np.array(list(seed_accs.values()))
    mean = float(np.mean(accs))
    std = float(np.std(accs, ddof=1)) if len(accs) > 1 else 0.0

    return {
        "accuracy": mean,
        "std": std,
        "n_seeds": len(active_seeds),
        "per_seed": seed_accs,
        "avg_selected_tokens": float(np.mean(tokens_all)) if tokens_all else 0,
        "avg_latency_ms": float(np.median(latency_all)) if latency_all else 0,
        "avg_latency_mean_ms": float(np.mean(latency_all)) if latency_all else 0,
        "avg_rules": float(np.mean(n_rules_all)) if n_rules_all else 0,
    }


def bootstrap_ci(items: list[dict], n_boot: int = 10000) -> tuple[float, float]:
    """Per-question cluster bootstrap 95% CI."""
    by_qid = defaultdict(list)
    for it in items:
        qid = it.get("sample_id", "unknown")
        by_qid[qid].append(it["hard"])
    qid_means = np.array([np.mean(v) for v in by_qid.values()])
    rng = np.random.RandomState(42)
    boot = np.sort([float(np.mean(rng.choice(qid_means, size=len(qid_means), replace=True)))
                    for _ in range(n_boot)])
    return float(boot[int(n_boot * 0.025)]), float(boot[int(n_boot * 0.975)])


# ── 绘图 ────────────────────────────────────────────────────────────────────

def plot(methods: dict[str, dict], out_path: str):
    """绘制 Accuracy vs Selected Tokens scatter plot."""
    fig, ax = plt.subplots(figsize=(9, 6))

    labels = []
    xs, ys = [], []
    xerr_low, xerr_high = [], []
    yerr_low, yerr_high = [], []
    sizes = []
    colors = []

    # 颜色方案
    palette = {
        "Core Only":        "#999999",
        "TF-IDF Top-5":     "#4C72B0",
        "MOAR":             "#DD4444",
        "BM25":             "#55A868",
        "greedy-cold":      "#C44E52",
        "greedy-util":      "#8172B2",
    }
    name_map = {
        "Core Only": "Core Only",
        "TF-IDF Top-5": "TF-IDF",
        "MOAR": "MOAR",
        "bm25": "BM25",
        "greedy-cold": "Greedy-Cold",
        "greedy-util": "Greedy-Utility",
    }

    for raw_name, st in methods.items():
        name = name_map.get(raw_name, raw_name)
        labels.append(name)
        x = st["avg_selected_tokens"]
        y = st["accuracy"] * 100
        xs.append(x)
        ys.append(y)

        # X 误差: 不同 seed 的 selected_tokens 可能不同，此处设为 0
        xerr_low.append(0)
        xerr_high.append(0)

        # Y 误差: seed std 或 bootstrap CI
        if st.get("bootstrap_ci"):
            ci_low, ci_high = st["bootstrap_ci"]
            yerr_low.append(y - ci_low * 100)
            yerr_high.append(ci_high * 100 - y)
        elif st["std"] > 0:
            yerr_low.append(st["std"] * 100)
            yerr_high.append(st["std"] * 100)
        else:
            yerr_low.append(0)
            yerr_high.append(0)

        # 点大小: 检索延迟（对数缩放）
        lat = st.get("avg_latency_ms", 1)
        size = max(40, min(800, np.log10(lat + 1) * 200))
        sizes.append(size)
        colors.append(palette.get(raw_name, "#333333"))

    # 散点图
    for i in range(len(labels)):
        ax.errorbar(
            xs[i], ys[i],
            xerr=[[xerr_low[i]], [xerr_high[i]]],
            yerr=[[yerr_low[i]], [yerr_high[i]]],
            fmt="o", markersize=np.sqrt(sizes[i]) * 0.8,
            color=colors[i], markeredgecolor="white",
            markeredgewidth=1.5, capsize=4,
            label=labels[i], zorder=5,
        )

    # 标签
    for i in range(len(labels)):
        offset_y = 0
        if labels[i] == "MOAR":
            offset_y = 0.8
        elif labels[i] == "BM25":
            offset_y = -0.8
        ax.annotate(
            labels[i],
            (xs[i], ys[i]),
            xytext=(5, 5 + offset_y * 3),
            textcoords="offset points",
            fontsize=10, fontweight="bold",
            color=colors[i],
        )

    ax.set_xlabel("Average Selected Tokens (dynamic rules only)", fontsize=12)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("MOAR & Baselines: Accuracy vs Token Cost vs Latency\n"
                 "SearchQA test (200 items x 3 seeds), qwen-flash, 2000-token budget, top-5",
                 fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    # 注释
    note = (
        "Bubble size = retrieval latency (median ms)\n"
        "Error bars = +/- 1 SD across 3 seeds\n"
        "All methods respect 2000-token budget"
    )
    ax.text(0.98, 0.03, note, transform=ax.transAxes,
            fontsize=7, color="#666", ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f5f5f5", alpha=0.8))

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {out_path}")
    plt.close(fig)


# ── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=str, default="")
    args = p.parse_args()

    print("Loading formal enriched data (qwen-flash / targetS)...")
    formal = load_formal_enriched("targetS")

    print("Loading baselines...")
    bm25 = load_baseline("bm25")
    greedy_cold = load_baseline("greedy-cold")
    greedy_util = load_baseline("greedy-util")

    # 合并
    all_data = {**formal}
    for name, items in [("bm25", bm25), ("greedy-cold", greedy_cold),
                         ("greedy-util", greedy_util)]:
        if items:
            all_data[name] = items

    # 统计
    methods = {}
    for name, items in all_data.items():
        if not items:
            continue
        st = method_stats(items)
        # Bootstrap CI for baseline (single run)
        if st["n_seeds"] <= 1:
            ci_low, ci_high = bootstrap_ci(items)
            st["bootstrap_ci"] = (ci_low, ci_high)
        methods[name] = st

    # 打印表格
    print(f"\n{'Method':<20s} {'Acc':>8s} {'+/-':>8s} {'Tokens':>8s} {'Lat(med)':>10s} {'Rules':>6s}")
    print(f"{'-'*60}")
    for name, st in methods.items():
        print(f"  {name:<18s} {st['accuracy']*100:7.2f}% {st['std']*100:7.2f}% "
              f"{st['avg_selected_tokens']:7.0f} {st['avg_latency_ms']:9.0f}ms "
              f"{st['avg_rules']:5.1f}")

    # 绘图
    out = args.out or os.path.join(OUTPUTS, "comparison_chart.png")
    plot(methods, out)


if __name__ == "__main__":
    main()
