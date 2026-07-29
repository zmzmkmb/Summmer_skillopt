#!/usr/bin/env python3
"""Unified baseline inference for BM25, Greedy-Cold, and Greedy-Utility.

SAME conditions as moar_searchqa_eval.py:
- _build_user(question, context) — same SearchQA context passages
- Same _build_system, chat_target, evaluate pipeline
- Tokenizer-based costs (same as MOAR)
- ThreadPoolExecutor for inference (same as MOAR main script)

Greedy-Cold:  zero historical utility (cold start).
Greedy-Utility: loads frozen moar_utility.json for per-rule precision scores.

Usage:
    python scripts/infer_baselines.py --method bm25 --limit 200
    python scripts/infer_baselines.py --method greedy-cold --limit 200
    python scripts/infer_baselines.py --method greedy-util --limit 200
"""
from __future__ import annotations

import argparse, json, os, sys, time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import (
    chat_target, set_optimizer_backend, set_optimizer_deployment,
    set_target_backend, set_target_deployment,
)
from skillopt.rag_rule_selector import RuleMemory


def tokenize(s): return s.lower().split()


def greedy_select(relevance, utilities, costs, sims, top_k, budget, w):
    selected, remaining, used = [], list(range(len(relevance))), 0
    for _ in range(top_k):
        best, best_i = -1e9, -1
        for j in remaining:
            c = costs[j]
            if used + c > budget and selected: continue
            s = w[0]*relevance[j] + w[1]*utilities[j] - w[2]*(c/budget)
            if selected: s -= w[3]*np.mean([sims[j,s] for s in selected])
            if s > best: best, best_i = s, j
        if best_i < 0: break
        c = costs[best_i]
        if used + c > budget and selected: break
        selected.append(best_i); used += c; remaining.remove(best_i)
    return selected


def infer(method, skill_content, items, top_k, budget, weights, workers):
    rm = RuleMemory(skill_content, method="tfidf", top_k=top_k, token_budget=budget)
    rules = [r.full_text for r in rm.dynamic_rules]
    core = rm.core_rules_text
    n = len(rules)

    from sklearn.metrics.pairwise import cosine_similarity
    rv = rm._rule_matrix.toarray() if hasattr(rm._rule_matrix, 'toarray') else np.asarray(rm._rule_matrix)
    try:
        from skillopt.moar.tokenizer import count_tokens
        costs = np.array([count_tokens(t) for t in rules], dtype=float)
    except Exception:
        costs = np.array([len(t) for t in rules], dtype=float)
    sims = cosine_similarity(rv); np.fill_diagonal(sims, 0.0)
    w = tuple(float(x) for x in weights.split(",")[:4])

    bm25 = None
    if "bm25" in method:
        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi([tokenize(r) for r in rules])

    # Load frozen utilities for Greedy-Utility
    frozen_utils = np.zeros(n)
    if "util" in method:
        from skillopt.moar.tracker import UtilityTracker
        for candidate in [
            os.path.join(_PROJECT_ROOT, "outputs", "moar_utility.json"),
            os.path.join(_PROJECT_ROOT, "outputs", "searchqa_rag", "moar_utility.json"),
        ]:
            if os.path.exists(candidate):
                ut = UtilityTracker(persistence_path=candidate)
                ut.register_rules(rules)
                frozen_utils = ut.compute_utilities("precision")
                print(f"  Loaded utilities from {candidate}")
                break
        else:
            print("  No utility file found — using cold start")

    # Phase 1: sequential rule selection (timed per query)
    t0 = time.time()
    sel_data: list[dict] = []
    for it in items:
        q = it["question"]; ctx = it.get("context", "")
        qv = rm._vectorizer.transform([q])
        rel = cosine_similarity(qv, rv).ravel()

        sel_start = time.time()
        if "bm25" in method:
            scores = bm25.get_scores(tokenize(q))
            order = np.argsort(-scores)
            sel, used = [], 0
            for idx in order:
                if len(sel) >= top_k: break
                c = costs[idx]
                if used + c > budget and sel: break
                sel.append(int(idx)); used += c
        else:
            sel = greedy_select(rel, frozen_utils, costs, sims, top_k, budget, w)
        sel_ms = (time.time() - sel_start) * 1000

        dynamic_text = "\n\n".join(
            rules[i] for i in sorted(sel, key=lambda i: rm.dynamic_rules[i].index))
        text = core + "\n\n" + dynamic_text if dynamic_text else core
        system = _build_system(text)
        user = _build_user(q, ctx)

        sel_data.append({
            "item": it, "system": system, "user": user,
            "sel": list(sel), "sel_ms": sel_ms,
            "sel_chars": len(dynamic_text),
            "input_chars": len(system) + len(user),
        })

    # Phase 2: parallel inference (preserving original ordering)
    n_items = len(items)
    batch_results: list[dict | None] = [None] * n_items

    def _infer_one(idx: int, system: str, user: str, it: dict) -> dict:
        try:
            inf_start = time.time()
            resp, _ = chat_target(
                system, user, max_completion_tokens=512,
                retries=2, stage="eval", timeout=60,
            )
            inf_ms = (time.time() - inf_start) * 1000
        except Exception:
            resp = ""; inf_ms = 0
        ev = evaluate(resp, it.get("answers", []))
        return {
            "sample_id": str(it["id"]),
            "hard": int(ev["em"]),
            "predicted": ev["predicted_answer"],
            "gold": it.get("answers", []),
            "inference_ms": inf_ms,
        }

    t_inf_start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_infer_one, i, d["system"], d["user"], d["item"]): i
                for i, d in enumerate(sel_data)}
        for fut in as_completed(futs):
            idx = futs[fut]
            batch_results[idx] = fut.result()

    assert all(r is not None for r in batch_results), "missing inference results"
    inf_elapsed = time.time() - t_inf_start

    # Merge selection + inference data
    per_item = []
    for i in range(n_items):
        d = dict(batch_results[i])
        sd = sel_data[i]
        d.update({
            "n_rules": len(sd["sel"]),
            "selected_indices": sd["sel"],
            "sel_chars": sd["sel_chars"],
            "input_chars": sd["input_chars"],
            "sel_latency_ms": sd["sel_ms"],
            "inference_ms": batch_results[i]["inference_ms"],
        })
        per_item.append(d)

    acc = float(np.mean([r["hard"] for r in per_item]))
    avg_r = float(np.mean([r["n_rules"] for r in per_item]))
    total_elapsed = time.time() - t0
    avg_sel_ms = float(np.mean([sd["sel_ms"] for sd in sel_data]))
    print(f"\n{method.upper()} {n_items} items: acc={acc:.4f}  avg_rules={avg_r:.1f}")
    print(f"  Selection: {avg_sel_ms:.1f}ms/q | Inference: {inf_elapsed:.0f}s total")
    return acc, avg_r, per_item


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", required=True,
                   choices=["bm25","greedy-cold","greedy-util"])
    p.add_argument("--skill", default="outputs/searchqa_rag/best_skill.md")
    p.add_argument("--target-model", type=str, default="qwen3.6-flash")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--weights", default="0.4,0.3,0.2,0.1")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--out", default="")
    return p.parse_args()


def main():
    args = parse_args()

    set_optimizer_backend("openai_compatible")
    set_target_backend("openai_compatible")
    set_optimizer_deployment("deepseek-v4-flash")
    set_target_deployment(args.target_model)

    with open(os.path.abspath(args.skill), encoding="utf-8") as f:
        skill = f.read()

    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    with open(os.path.join(data_dir, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    if args.limit > 0:
        items = items[:args.limit]
    print(f"Skill: {os.path.basename(args.skill)} | method={args.method}")
    print(f"Model: {args.target_model} | items={len(items)} | workers={args.workers}")

    import subprocess
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, cwd=_PROJECT_ROOT).strip()

    acc, avg_r, per_item = infer(
        args.method, skill, items, args.top_k, args.budget,
        args.weights, args.workers,
    )

    out = args.out or os.path.join(
        _PROJECT_ROOT, "outputs",
        f"infer_{args.method}_{args.target_model}_n{len(items)}.json",
    )
    summary = {
        "method": args.method, "target_model": args.target_model,
        "n": len(items), "acc": acc, "avg_rules": avg_r,
        "commit": commit, "per_question": per_item,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
