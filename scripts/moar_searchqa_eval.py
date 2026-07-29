#!/usr/bin/env python3
"""Smoke test + controlled comparison: MOAR vs TF-IDF vs Core Only on SearchQA.

Uses an already-trained skill and runs inference-only (no training),
comparing three retrieval methods under identical conditions.

Usage:
    python scripts/moar_searchqa_eval.py \
        --skill outputs/searchqa_rag/best_skill.md \
        --limit 200 --split valid_unseen
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import (
    chat_target,
    set_optimizer_backend,
    set_optimizer_deployment,
    set_target_backend,
    set_target_deployment,
)
from skillopt.model.common import default_model_for_backend
from skillopt.rag_rule_selector import RuleMemory


# ── Helpers ──────────────────────────────────────────────────────────────

def load_test_items(split: str, limit: int = 0) -> list[dict]:
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split")
    sub = "test" if split == "valid_unseen" else "val"
    path = os.path.join(data_dir, sub, "items.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    if limit > 0:
        items = items[:limit]
    return items


def infer_one(item: dict, system: str) -> dict:
    user = _build_user(item["question"], item.get("context", ""))
    try:
        resp, _ = chat_target(
            system, user, max_completion_tokens=512,
            retries=2, stage="moar_eval", timeout=60,
        )
    except Exception as exc:
        resp = ""
    ev = evaluate(resp, item.get("answers", []))
    return {
        "id": item["id"],
        "hard": int(ev["em"]),
        "response_len": len(resp),
    }


def build_skill_text(rm, query: str) -> tuple[str, int, int]:
    """Build active skill for query. Returns (text, n_dynamic, total_chars)."""
    core = rm.core_rules_text
    dynamic = rm.retrieve(query)
    if dynamic:
        text = core + "\n\n" + dynamic
    else:
        text = core
    # Count selected dynamic rules
    n_dyn = dynamic.count("## ") if dynamic else 0
    return text, n_dyn, len(text)


def count_rule_redundancy(rm, query: str) -> float:
    """Estimate redundancy among selected dynamic rules via pairwise TF-IDF sim."""
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    k = min(rm.top_k, rm.n_dynamic)
    if k <= 1:
        return 0.0

    # Use TF-IDF to get indices (MOAR delegates internally, but RuleMemory
    # doesn't expose selected indices — we estimate via the parent's _tfidf_select)
    # Get actual selected indices (not the first K rules)
    if hasattr(rm, '_engine'):
        last_sel = rm._engine._last_selections.get(query, [])
        indices = list(last_sel) if last_sel else list(range(min(k, rm.n_dynamic)))
    elif hasattr(rm, '_last_selections'):
        last_sel = getattr(rm, '_last_selections', {}).get(query, [])
        indices = list(last_sel) if last_sel else list(range(min(k, rm.n_dynamic)))
    else:
        indices = list(range(min(k, rm.n_dynamic)))

    if len(indices) <= 1:
        return 0.0

    rv = rm._parent._rule_matrix if hasattr(rm, '_parent') else rm._rule_matrix
    if rv is None or hasattr(rv, 'toarray'):
        pass
    if rv is not None and rv.shape[0] > 0:
        sel_emb = rv[indices]
        if hasattr(sel_emb, 'toarray'):
            sel_emb = sel_emb.toarray()
        sims = cosine_similarity(sel_emb)
        np.fill_diagonal(sims, 0.0)
        n = len(indices)
        max_pairs = n * (n - 1) / 2.0
        return float(np.sum(sims) / 2.0 / max_pairs) if max_pairs > 0 else 0.0
    return 0.0


# ── Main ─────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", type=str, required=True,
                   help="Path to trained skill .md file")
    p.add_argument("--target-model", type=str, default="qwen3.6-flash",
                   help="Target model name (qwen3.6-flash, qwen-flash, etc.)")
    p.add_argument("--optimizer-model", type=str, default="deepseek-v4-flash",
                   help="Optimizer model name (deepseek-v4-flash, deepseek-v4-pro, etc.)")
    p.add_argument("--split", type=str, default="valid_unseen")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=str, default="")
    return p.parse_args()


def main():
    args = parse_args()

    # ── Configure model backends (CLI-overridable) ────────────────────
    set_optimizer_backend("openai_compatible")
    set_target_backend("openai_compatible")
    set_optimizer_deployment(args.optimizer_model or "deepseek-v4-flash")
    set_target_deployment(args.target_model or "qwen-flash")

    # Load skill
    with open(os.path.abspath(args.skill), encoding="utf-8") as f:
        skill_content = f.read()

    # Load test items
    items = load_test_items(args.split, args.limit)
    questions = [it["question"] for it in items]
    print(f"Loaded {len(items)} test items from {args.split}")
    print(f"Skill: {os.path.basename(args.skill)} ({len(skill_content)} chars)")
    print(f"Config: top_k={args.top_k} budget={args.budget} workers={args.workers}")
    print(f"{'='*60}")

    # ── Build rule memories (once) ──────────────────────────────────────
    methods = {}
    # Shared parent args
    common = dict(top_k=args.top_k, token_budget=args.budget)

    print("\nBuilding RuleMemory instances...")
    t0 = time.time()

    methods["Core Only"] = RuleMemory(skill_content, method="core_only", **common)
    methods["TF-IDF Top-5"] = RuleMemory(skill_content, method="tfidf", **common)
    methods["MOAR"] = RuleMemory(
        skill_content, method="moar",
        moar_pop_size=30, moar_generations=15,
        moar_utility_method="precision",
        moar_base_seed=args.seed,
        moar_frozen=True,
        **common,
    )

    for name, rm in methods.items():
        print(f"  {name}: core={rm.n_core} dynamic={rm.n_dynamic} total={rm.n_total}")

    print(f"  Init time: {time.time() - t0:.1f}s")

    # ── Run inference ───────────────────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, list[dict]] = {}

    for method_name, rm in methods.items():
        print(f"\n{'='*60}")
        print(f"  {method_name}")
        print(f"{'='*60}")

        system_prompts: list[str] = []
        build_times: list[float] = []
        n_rules_list: list[int] = []
        char_counts: list[int] = []

        t_build_start = time.time()
        for q in questions:
            t_q0 = time.time()
            text, n_dyn, n_char = build_skill_text(rm, q)
            build_times.append(time.time() - t_q0)
            system = _build_system(text)
            system_prompts.append(system)
            n_rules_list.append(n_dyn)
            char_counts.append(n_char)
        avg_build = np.mean(build_times)
        avg_rules = np.mean(n_rules_list)
        avg_chars = np.mean(char_counts)
        print(f"  Build: {len(questions)} queries, avg {avg_build*1000:.1f}ms/query")
        print(f"  Rules activated: avg {avg_rules:.1f}, prompt chars avg {avg_chars:.0f}")

        # Inference
        t_infer_start = time.time()
        batch_results = []
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(infer_one, item, sp): i
                    for i, (item, sp) in enumerate(zip(items, system_prompts))}
            for fut in as_completed(futs):
                batch_results.append(fut.result())

        infer_time = time.time() - t_infer_start
        hard = np.mean([r["hard"] for r in batch_results])
        print(f"  Inference: {len(batch_results)} items, {infer_time:.0f}s ({infer_time/len(batch_results):.1f}s/item)")
        print(f"  Accuracy: {hard:.4f}")

        results[method_name] = {
            "accuracy": float(hard),
            "avg_rules": float(avg_rules),
            "avg_chars": float(avg_chars),
            "avg_build_ms": float(avg_build * 1000),
            "infer_time_s": float(infer_time),
            "n_items": len(batch_results),
            "per_item": [{"id": r["id"], "hard": r["hard"]} for r in batch_results],
        }

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Method':<20s} {'Acc':>8s} {'Rules':>8s} {'Chars':>8s} {'Build':>8s} {'Infer':>8s}")
    print(f"  {'-'*60}")
    for name, r in results.items():
        print(f"  {name:<20s} {r['accuracy']:8.4f} {r['avg_rules']:8.1f} "
              f"{r['avg_chars']:8.0f} {r['avg_build_ms']:7.0f}ms {r['infer_time_s']:7.0f}s")

    # Delta vs TF-IDF
    tfidf_acc = results["TF-IDF Top-5"]["accuracy"]
    for name in ["Core Only", "MOAR"]:
        delta = results[name]["accuracy"] - tfidf_acc
        print(f"  {name} vs TF-IDF: Δacc={delta:+.4f}")

    # Save
    out_path = args.out or os.path.join(
        _PROJECT_ROOT, "outputs",
        f"moar_comparison_{args.split}_n{args.limit}_{int(time.time())}.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    summary = {
        "skill": os.path.abspath(args.skill),
        "split": args.split,
        "limit": args.limit,
        "top_k": args.top_k,
        "budget": args.budget,
        "seed": args.seed,
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
