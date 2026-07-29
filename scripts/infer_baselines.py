#!/usr/bin/env python3
"""Unified baseline inference eval for BM25 and Greedy-Cold on SearchQA.

SAME input conditions as moar_searchqa_eval.py:
- Uses _build_user(question, context) so BM25/Greedy/MOAR all see the same
  SearchQA context passages.
- Uses the same _build_system, chat_target, evaluate pipeline.
- BM25 and Greedy-Cold use tokenizer-based costs (same as MOAR).

Greedy-Cold: utility weights are zero (no historical feedback).
For Greedy-Utility, use moar_searchqa_eval.py with moar_utility_path.

Usage:
    python scripts/infer_baselines.py --method bm25 --limit 200
    python scripts/infer_baselines.py --method greedy --limit 200
"""
from __future__ import annotations

import argparse, json, os, sys, time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

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
    # Use tokenizer for cost (same as MOAR), fallback to char length
    try:
        from skillopt.moar.tokenizer import count_tokens
        costs = np.array([count_tokens(t) for t in rules], dtype=float)
    except Exception:
        costs = np.array([len(t) for t in rules], dtype=float)
    sims = cosine_similarity(rv); np.fill_diagonal(sims, 0.0)
    w = tuple(float(x) for x in weights.split(",")[:4])

    bm25 = None
    if method == "bm25":
        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi([tokenize(r) for r in rules])

    t0 = time.time()
    results = []
    for it in items:
        q = it["question"]
        ctx = it.get("context", "")
        qv = rm._vectorizer.transform([q])
        rel = cosine_similarity(qv, rv).ravel()
        utils = np.zeros(n)

        # --- rule selection ---
        sel_start = time.time()
        if method == "bm25":
            scores = bm25.get_scores(tokenize(q))
            order = np.argsort(-scores)
            sel, used = [], 0
            for idx in order:
                if len(sel) >= top_k: break
                c = costs[idx]
                if used + c > budget and sel: break
                sel.append(int(idx)); used += c
        else:
            sel = greedy_select(rel, utils, costs, sims, top_k, budget, w)
        sel_ms = (time.time() - sel_start) * 1000

        # --- build prompt (same as MOAR main script) ---
        dynamic_text = "\n\n".join(
            rules[i] for i in sorted(sel, key=lambda i: rm.dynamic_rules[i].index))
        text = core + "\n\n" + dynamic_text if dynamic_text else core
        system = _build_system(text)
        user = _build_user(q, ctx)

        # --- inference ---
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

        results.append({
            "sample_id": str(it["id"]),
            "hard": int(ev["em"]),
            "n_rules": len(sel),
            "selected_indices": list(sel),
            "sel_chars": len(dynamic_text),
            "input_chars": len(system) + len(user),
            "sel_latency_ms": sel_ms,
            "inference_ms": inf_ms,
            "predicted": ev["predicted_answer"],
            "gold": it.get("answers", []),
        })

    elapsed = time.time() - t0
    acc = float(np.mean([r["hard"] for r in results]))
    avg_r = float(np.mean([r["n_rules"] for r in results]))
    print(f"\n{method.upper()} {len(items)} items: acc={acc:.4f}  avg_rules={avg_r:.1f}  time={elapsed:.0f}s")
    return acc, avg_r, results


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", required=True, choices=["bm25","greedy"])
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
    print(f"Model: {args.target_model} | items={len(items)}")

    acc, avg_r, results = infer(
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
        "per_question": results,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
