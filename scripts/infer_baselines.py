#!/usr/bin/env python3
"""Lightweight inference eval for BM25 and Greedy rule selection on SearchQA.

Extends moar_searchqa_eval.py infrastructure but uses BM25 / Greedy selectors
instead of RuleMemory.retrieve().  Only one method per invocation for speed.

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
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system
from skillopt.model import (
    chat_target, set_optimizer_backend, set_optimizer_deployment,
    set_target_backend, set_target_deployment,
)
from skillopt.rag_rule_selector import RuleMemory

# ── Helpers ──────────────────────────────────────────────────────────

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

    # Precompute features (same as eval script)
    from sklearn.metrics.pairwise import cosine_similarity
    rv = rm._rule_matrix.toarray() if hasattr(rm._rule_matrix, 'toarray') else rm._rule_matrix
    costs = np.array([len(t) for t in rules], dtype=float)
    sims = cosine_similarity(rv); np.fill_diagonal(sims, 0.0)
    w = tuple(float(x) for x in weights.split(",")[:4])

    # BM25 index — import locally to avoid hard dep for greedy-only usage
    bm25 = None
    if method == "bm25":
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "rank-bm25", "-q"])
            from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi([tokenize(r) for r in rules])

    t0 = time.time()
    results = []
    for it in items:
        q = it["question"]
        qv = rm._vectorizer.transform([q])
        rel = cosine_similarity(qv, rv).ravel()
        utils = np.zeros(n)

        if method == "bm25":
            scores = bm25.get_scores(tokenize(q))
            order = np.argsort(-scores)
            sel, used = [], 0
            for idx in order:
                if len(sel) >= top_k: break
                c = costs[idx]
                if used + c > budget and sel: break
                sel.append(int(idx)); used += c
        else:  # greedy
            sel = greedy_select(rel, utils, costs, sims, top_k, budget, w)

        dynamic_text = "\n\n".join(rules[i] for i in sorted(sel, key=lambda i: rm.dynamic_rules[i].index))
        text = core + "\n\n" + dynamic_text if dynamic_text else core
        system = _build_system(text)
        try:
            resp, _ = chat_target(system, q, max_completion_tokens=512, retries=2, stage="eval", timeout=60)
        except:
            resp = ""
        ev = evaluate(resp, it.get("answers", []))
        results.append({"hard": int(ev["em"]), "n_rules": len(sel)})

    elapsed = time.time() - t0
    acc = np.mean([r["hard"] for r in results])
    avg_rules = np.mean([r["n_rules"] for r in results])
    print(f"\n{method.upper()} {len(items)} items: acc={acc:.4f}  avg_rules={avg_rules:.1f}  time={elapsed:.0f}s")
    return acc, avg_rules

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--method", required=True, choices=["bm25","greedy"])
    p.add_argument("--skill", default="outputs/searchqa_rag/best_skill.md")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--weights", default="0.4,0.3,0.2,0.1")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--out", default="")
    args = p.parse_args()

    set_optimizer_backend("openai_compatible"); set_target_backend("openai_compatible")
    set_optimizer_deployment("deepseek-v4-flash"); set_target_deployment("qwen-flash")

    with open(os.path.abspath(args.skill), encoding="utf-8") as f:
        skill = f.read()
    with open(os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test", "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    if args.limit > 0: items = items[:args.limit]
    print(f"Skill: {os.path.basename(args.skill)} | method={args.method} | items={len(items)}")

    acc, avg_r = infer(args.method, skill, items, args.top_k, args.budget, args.weights, args.workers)

    out = args.out or os.path.join(_PROJECT_ROOT, "outputs", f"infer_{args.method}_n{len(items)}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"method": args.method, "n": len(items), "acc": acc, "avg_rules": avg_r}, f, indent=2)
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
