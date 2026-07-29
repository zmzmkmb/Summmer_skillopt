#!/usr/bin/env python3
"""统计汇总 JoS formal 实验 + 基线.

用法:
    python scripts/analyze_jos_results.py                          # 仅 formal
    python scripts/analyze_jos_results.py --baselines bm25,greedy-cold  # 含基线
    python scripts/analyze_jos_results.py --bootstrap --out summary.json
"""
from __future__ import annotations
import json, os, sys, argparse
from collections import defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUT = os.path.join(PROJECT_ROOT, "outputs")

FORMAL_SEEDS = [42, 43, 44]
FORMAL_LIMIT = 200


# ── 加载 ─────────────────────────────────────────────────────

def load_formal(model_key: str) -> dict[str, list[dict]]:
    """加载同一模型的 3-seed formal JSON."""
    prefix = "targetS" if model_key == "qwen-flash" else "targetL"
    merged: dict[str, list[dict]] = defaultdict(list)
    for seed in FORMAL_SEEDS:
        path = os.path.join(OUT, f"jos_formal_{prefix}_seed{seed}.json")
        if not os.path.exists(path):
            print(f"  [WARN] missing: {os.path.basename(path)}")
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for method, res in d["results"].items():
            for it in res.get("per_item", []):
                it = dict(it)
                it["_seed"] = seed
                it["_method"] = method
                it["_model"] = d.get("target_model", model_key)
                merged[method].append(it)
    return dict(merged)


def load_baseline(name: str, model: str = "qwen-flash") -> list[dict] | None:
    """加载单个基线 JSON."""
    for pat in [f"infer_{name}_{model}_n200.json", f"infer_{name}_{model}_n{FORMAL_LIMIT}.json"]:
        p = os.path.join(OUT, pat)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        items = d.get("per_question", [])
        if not items:
            return None
        empty = sum(1 for it in items if it.get("predicted", "") == "")
        if empty == len(items):
            print(f"  [WARN] {os.path.basename(p)}: all {empty} predictions empty, skipping")
            return None
        for it in items:
            it["_method"] = name
            it["_model"] = model
            it["_seed"] = 0  # baseline = single run
        return items
    return None


# ── 统计 ─────────────────────────────────────────────────────

def method_stats(items: list[dict]) -> dict:
    """按 seed 分组的汇总统计."""
    # 分组
    by_seed: dict[int, list[int]] = defaultdict(list)
    for it in items:
        by_seed[it.get("_seed", 0)].append(it["hard"])

    real_seeds = sorted(s for s in by_seed if s != 0)
    active = real_seeds if real_seeds else [0]
    seed_accs = {s: float(np.mean(by_seed[s])) for s in active}
    accs_arr = np.array(list(seed_accs.values()))
    mean = float(np.mean(accs_arr))
    std = float(np.std(accs_arr, ddof=1)) if len(accs_arr) > 1 else 0.0

    all_hard = np.array([it["hard"] for it in items])
    n_rules = np.array([it.get("n_rules", 0) for it in items])
    sel_tokens = [it.get("selected_tokens", 0) for it in items]
    build_ms = np.array([it.get("build_ms", it.get("sel_latency_ms", 0)) for it in items])
    api_fails = sum(1 for it in items if it.get("predicted", "") == "")

    # Fallback tokens: old data uses sel_chars or prompt_chars
    if all(t == 0 for t in sel_tokens):
        sel_tokens = [it.get("sel_chars", it.get("prompt_chars", 0)) for it in items]
        if all(t > 500 for t in sel_tokens):
            sel_tokens = [max(0, t - 513) for t in sel_tokens]

    budget_viol = 0
    prev_commit = False
    for it in items:
        it_has = "selected_tokens" in it or "sel_chars" in it
        prev_commit = prev_commit or it_has
    if not prev_commit:
        sel_tokens = [0] * len(items)

    return {
        "accuracy": mean, "std": std,
        "n_items": len(items), "n_seeds": len(active),
        "per_seed": seed_accs,
        "range": (float(np.min(all_hard)), float(np.max(all_hard))),
        "avg_rules": float(np.mean(n_rules)),
        "avg_selected_tokens": float(np.mean(sel_tokens)) if sel_tokens else 0,
        "build_ms_mean": float(np.mean(build_ms)),
        "build_ms_median": float(np.median(build_ms)),
        "build_ms_p95": float(np.percentile(build_ms, 95)),
        "build_ms_p99": float(np.percentile(build_ms, 99)),
        "build_ms_max": float(np.max(build_ms)),
        "api_failures": api_fails,
        "budget_violations": int(budget_viol),
    }


def mcnemar_by_id(a_items: list[dict], b_items: list[dict]) -> dict:
    """配对 McNemar: 按 sample_id 匹配,忽略多余项."""
    b_map = {it["sample_id"]: it["hard"] for it in b_items}
    pairs = [(it["hard"], b_map[it["sample_id"]])
             for it in a_items if it["sample_id"] in b_map]
    if not pairs:
        return {"error": "no matching sample_ids"}
    a_arr = np.array([p[0] for p in pairs])
    b_arr = np.array([p[1] for p in pairs])
    b01 = int(((a_arr == 0) & (b_arr == 1)).sum())
    b10 = int(((a_arr == 1) & (b_arr == 0)).sum())
    n_discord = b01 + b10
    if n_discord == 0:
        return {"statistic": 0.0, "p_value": 1.0, "b01": 0, "b10": 0,
                "n_discord": 0, "n_pairs": len(pairs)}
    # chi-squared with Yates correction
    import scipy.stats as _st
    stat = (abs(b01 - b10) - 1) ** 2 / n_discord
    p = 1.0 - _st.chi2.cdf(stat, 1)
    return {"statistic": float(stat), "p_value": float(p),
            "b01": b01, "b10": b10, "n_discord": n_discord,
            "n_pairs": len(pairs)}


def jaccard_stability(items: list[dict]) -> dict:
    """规则选择 Jaccard 稳定性(跨 seed)."""
    by_seed: dict[int, list[list[int]]] = defaultdict(list)
    for it in items:
        s = it.get("_seed", 0)
        if s == 0:
            continue
        idx = it.get("selected_indices", [])
        by_seed[s].append(idx)

    seeds = sorted(by_seed.keys())
    if len(seeds) < 2:
        return {"n_seeds": len(seeds), "pairwise_jaccard": [], "mean_jaccard": None}

    pairwise = []
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            a, b = seeds[i], seeds[j]
            jac = []
            for ia, ib in zip(by_seed[a], by_seed[b]):
                sa, sb = set(ia), set(ib)
                if not sa and not sb:
                    jac.append(1.0)
                elif not sa or not sb:
                    jac.append(0.0)
                else:
                    jac.append(len(sa & sb) / len(sa | sb))
            pairwise.append({"seeds": (a, b), "mean_jaccard": float(np.mean(jac)),
                             "std": float(np.std(jac, ddof=1)) if len(jac) > 1 else 0})
    means = [pw["mean_jaccard"] for pw in pairwise]
    return {"n_seeds": len(seeds), "pairwise_jaccard": pairwise,
            "mean_jaccard": float(np.mean(means)) if means else None}


# ── 打印 ─────────────────────────────────────────────────────

def print_table(model: str, methods: dict[str, list[dict]]):
    """打印单模型完整对比表."""
    if not methods:
        return

    print(f"\n{'='*80}")
    print(f"  Target: {model}")
    print(f"{'='*80}")

    stats = {name: method_stats(items) for name, items in methods.items()}

    # 准确率表
    hdr = f"  {'Method':<20s} {'Acc +/- Std':<16s} {'Rules':<8s} {'SelTok':<8s} {'Lat(med)':<10s}"
    print(hdr)
    print(f"  {'-'*60}")
    for name, st in stats.items():
        acc_str = f"{st['accuracy']*100:.2f}% +/-{st['std']*100:.2f}%"
        rules = f"{st['avg_rules']:.1f}"
        toks = f"{st['avg_selected_tokens']:.0f}"
        lat = f"{st['build_ms_median']:.0f}ms"
        print(f"  {name:<20s} {acc_str:<16s} {rules:<8s} {toks:<8s} {lat:<10s}")
        if st["api_failures"] > 0:
            print(f"    [WARN] API failures: {st['api_failures']}/{st['n_items']}")
        if st["budget_violations"] > 0:
            print(f"    [WARN] budget violation: {st['budget_violations']}/{st['n_items']}")

    # Per-seed
    has_seeds = any(st["n_seeds"] > 1 for st in stats.values())
    if has_seeds:
        print(f"\n  Per-seed accuracy:")
        all_seeds = sorted(set(s for st in stats.values() for s in st["per_seed"]))
        seed_hdr = f"  {'Method':<20s}" + "".join(f" {'S'+str(s):>10s}" for s in all_seeds)
        print(seed_hdr)
        print(f"  {'-'*len(seed_hdr)}")
        for name, st in stats.items():
            if not st["per_seed"]:
                print(f"  {name:<20s} (single run)")
                continue
            s_str = "".join(f" {st['per_seed'].get(s,0)*100:9.2f}%" for s in all_seeds)
            print(f"  {name:<20s}{s_str}")

    # Delta
    base = stats.get("Core Only")
    if base and base["accuracy"] > 0:
        print(f"\n  Delta vs Core Only:")
        for name, st in stats.items():
            if name == "Core Only":
                continue
            d = (st["accuracy"] - base["accuracy"]) * 100
            print(f"    {name:<20s} {d:+.2f} pp")

    tfidf = stats.get("TF-IDF Top-5")
    if tfidf and tfidf["accuracy"] > 0:
        print(f"\n  Delta vs TF-IDF Top-5:")
        for name, st in stats.items():
            if name == "TF-IDF Top-5":
                continue
            d = (st["accuracy"] - tfidf["accuracy"]) * 100
            print(f"    {name:<20s} {d:+.2f} pp")

    # McNemar
    moar_items = methods.get("MOAR")
    if moar_items:
        print(f"\n  Paired McNemar (MOAR vs others, by sample_id):")
        for name, items in methods.items():
            if name == "MOAR":
                continue
            m = mcnemar_by_id(moar_items, items)
            if "error" in m:
                print(f"    MOAR vs {name:<20s}: {m['error']}")
            else:
                sig = " *" if m["p_value"] < 0.05 else ""
                print(f"    MOAR vs {name:<20s}: chi2={m['statistic']:.2f} "
                      f"p={m['p_value']:.4f} ({m['b10']} better/{m['b01']} worse of {m['n_pairs']} pairs){sig}")

    # Latency
    print(f"\n  Selection latency:")
    for name, st in stats.items():
        print(f"    {name:<20s} mean={st['build_ms_mean']:.0f}ms "
              f"median={st['build_ms_median']:.0f}ms "
              f"P95={st['build_ms_p95']:.0f}ms "
              f"P99={st['build_ms_p99']:.0f}ms "
              f"max={st['build_ms_max']:.0f}ms")

    return stats


# ── Bootstrap ────────────────────────────────────────────────

def bootstrap_ci(items: list[dict], n_boot: int = 10000) -> dict:
    """按 question ID 聚类 bootstrap 95% CI."""
    by_qid = defaultdict(list)
    for it in items:
        qid = it.get("sample_id", "unknown")
        by_qid[qid].append(it["hard"])
    qid_means = np.array([np.mean(v) for v in by_qid.values()])
    rng = np.random.RandomState(42)
    boot_means = np.sort([float(np.mean(rng.choice(qid_means, size=len(qid_means), replace=True)))
                          for _ in range(n_boot)])
    ci_low = boot_means[int(n_boot * 0.025)]
    ci_high = boot_means[int(n_boot * 0.975)]
    return {"mean": float(np.mean(qid_means)), "ci95_low": ci_low, "ci95_high": ci_high,
            "n_questions": len(qid_means)}


# ── Main ─────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baselines", type=str, default="bm25,greedy-cold")
    p.add_argument("--model", type=str, default="qwen-flash")
    p.add_argument("--bootstrap", action="store_true")
    p.add_argument("--out", type=str, default="")
    return p.parse_args()


def main():
    args = parse_args()

    print("Loading formal experiment data...")
    f_qwen = load_formal("qwen-flash")
    f_qwen36 = load_formal("qwen3.6-flash")

    # Filter out qwen3.6-flash seed 44 (all empty)
    f_qwen36_clean = {}
    for method, items in f_qwen36.items():
        good = [it for it in items if it.get("predicted", "") != ""]
        if good:
            f_qwen36_clean[method] = good
            print(f"  qwen3.6-flash {method}: kept {len(good)}/{len(items)} non-empty items")
        else:
            print(f"  qwen3.6-flash {method}: ALL EMPTY, skipping")

    # Load baselines
    baselines = {}
    if args.baselines:
        for name in args.baselines.split(","):
            name = name.strip()
            print(f"Loading baseline: {name} ({args.model})...")
            items = load_baseline(name, args.model)
            if items:
                baselines[name] = items
                acc = np.mean([i["hard"] for i in items])
                print(f"  {name}: {len(items)} items, acc={acc:.4f}")

    # Print qwen-flash
    all_qwen = {**f_qwen, **baselines}
    print_table("qwen-flash", all_qwen)

    # Print qwen3.6-flash (cleaned)
    if f_qwen36_clean and any(
        any(it.get("predicted", "") != "" for it in items)
        for items in f_qwen36_clean.values()
    ):
        print_table("qwen3.6-flash", f_qwen36_clean)

    # Jaccard stability
    print(f"\n{'='*80}")
    print("  Rule Selection Stability (Jaccard)")
    print(f"{'='*80}")
    for method in ["MOAR", "TF-IDF Top-5"]:
        if method in f_qwen:
            jac = jaccard_stability(f_qwen[method])
            print(f"  {method}: n_seeds={jac['n_seeds']} mean_J={jac.get('mean_jaccard', 'N/A')}")
            for pw in jac.get("pairwise_jaccard", []):
                print(f"    S{pw['seeds'][0]} vs S{pw['seeds'][1]}: "
                      f"J={pw['mean_jaccard']:.4f} +/- {pw['std']:.4f}")

    # Bootstrap
    if args.bootstrap:
        print(f"\n{'='*80}")
        print("  Bootstrap 95% CI (per-question, 10k resamples)")
        print(f"{'='*80}")
        for name, items in all_qwen.items():
            ci = bootstrap_ci(items)
            print(f"  {name:<20s}: {ci['mean']*100:.2f}% "
                  f"[{ci['ci95_low']*100:.2f}%, {ci['ci95_high']*100:.2f}%]")

    # Save
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        out_data = {name: method_stats(items) for name, items in all_qwen.items()}
        # Convert numpy types
        clean = {}
        for k, v in out_data.items():
            clean[k] = {kk: (float(vv) if isinstance(vv, (np.floating, np.integer)) else vv)
                        for kk, vv in v.items()
                        if not isinstance(vv, (list, dict, np.ndarray))}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        print(f"\nSaved: {args.out}")

    print(f"\n{'='*80}")
    print("  Done.")


if __name__ == "__main__":
    main()
