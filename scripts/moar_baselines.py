#!/usr/bin/env python3
"""Greedy + Exact multi-objective baselines for comparison with NSGA-II.

Greedy: Incrementally select the rule with highest combined weighted score,
        stopping when budget or top-K is exhausted.

Exact: Enumerate all 2^n subsets (feasible for n <= 20), evaluate combined
       objective, return the true optimal solution.

Usage:
    python scripts/moar_baselines.py \
        --skill outputs/searchqa_rag/best_skill.md \
        --limit 200 --method greedy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from itertools import combinations

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from skillopt.rag_rule_selector import RuleMemory


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", type=str, required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--weights", type=str, default="0.4,0.3,0.2,0.1")
    p.add_argument("--method", type=str, default="greedy",
                   choices=["greedy", "exact", "both"])
    return p.parse_args()


def greedy_select(
    relevance: np.ndarray,
    utilities: np.ndarray,
    token_costs: np.ndarray,
    pairwise_sims: np.ndarray,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> list[int]:
    """Greedy multi-objective rule selection.

    At each step, select the unselected rule that maximizes the weighted
    combined score, accounting for redundancy with already-selected rules.
    Stop when budget or top-K limits are reached.

    Returns list of selected rule indices.
    """
    n = len(relevance)
    selected: list[int] = []
    remaining = list(range(n))
    used_budget = 0

    for _ in range(top_k):
        best_score = -np.inf
        best_idx = -1
        for j in remaining:
            cost = token_costs[j]
            if used_budget + cost > budget and selected:
                continue  # can't fit this rule

            # Combined score with redundancy penalty
            score = (
                weights[0] * relevance[j]
                + weights[1] * utilities[j]
                - weights[2] * (cost / budget)
            )
            # Redundancy penalty: avg similarity with already-selected rules
            if selected:
                avg_sim = np.mean([pairwise_sims[j, s] for s in selected])
                score -= weights[3] * avg_sim

            if score > best_score:
                best_score = score
                best_idx = j

        if best_idx < 0:
            break

        cost = token_costs[best_idx]
        if used_budget + cost > budget and selected:
            break

        selected.append(best_idx)
        used_budget += cost
        remaining.remove(best_idx)

    return selected


def exact_select(
    relevance: np.ndarray,
    utilities: np.ndarray,
    token_costs: np.ndarray,
    pairwise_sims: np.ndarray,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> list[int]:
    """Exact optimal selection via brute-force enumeration.

    Only feasible for n <= 20 rules (2^n subsets).
    For n > 20, warns and falls back to greedy.
    """
    n = len(relevance)
    if n > 20:
        print(f"  [exact] n={n} > 20, falling back to greedy")
        return greedy_select(relevance, utilities, token_costs,
                             pairwise_sims, top_k, budget, weights)

    best_score = -np.inf
    best_subset: list[int] = []
    checked = 0

    # Enumerate subsets by size (empty to top_k), evaluate all
    for k in range(1, top_k + 1):
        for combo in combinations(range(n), k):
            checked += 1
            combo_list = list(combo)
            total_cost = sum(token_costs[i] for i in combo_list)
            if total_cost > budget:
                continue  # budget violation

            # Compute combined score
            sel_rel = np.sum(relevance[list(combo_list)])
            sel_util = np.sum(utilities[list(combo_list)])
            cost_norm = total_cost / budget

            # Redundancy
            if len(combo_list) >= 2:
                pairs = [(i, j) for idx_i, i in enumerate(combo_list)
                         for j in combo_list[idx_i + 1:]]
                avg_sim = np.mean([pairwise_sims[i, j] for i, j in pairs])
            else:
                avg_sim = 0.0

            score = (
                weights[0] * sel_rel / top_k
                + weights[1] * sel_util / top_k
                - weights[2] * cost_norm
                - weights[3] * avg_sim
            )

            if score > best_score:
                best_score = score
                best_subset = list(combo_list)

        if checked % 5000 == 0:
            print(f"  [exact] checked {checked} subsets...", flush=True)

    print(f"  [exact] total checked: {checked} subsets, best_score={best_score:.4f}")
    return best_subset


def main():
    args = parse_args()
    weights = parse_weights(args.weights)

    # Load skill
    with open(os.path.abspath(args.skill), encoding="utf-8") as f:
        skill_content = f.read()

    rm = RuleMemory(skill_content, method="tfidf",
                     top_k=args.top_k, token_budget=args.budget)

    print(f"Skill: core={rm.n_core} dynamic={rm.n_dynamic}")
    print(f"Config: top_k={args.top_k} budget={args.budget} weights={weights}")

    if rm.n_dynamic == 0:
        print("No dynamic rules to select from.")
        return

    # Load test queries
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    with open(os.path.join(data_dir, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    if args.limit > 0:
        items = items[:args.limit]

    queries = [it["question"] for it in items]
    print(f"Queries: {len(queries)}")

    # Precompute features
    rv = rm._rule_matrix
    if hasattr(rv, 'toarray'):
        rv = rv.toarray()

    rule_texts = [r.full_text for r in rm.dynamic_rules]
    token_costs = np.array([len(t) for t in rule_texts], dtype=float)
    pairwise_sims = cosine_similarity(rv)
    np.fill_diagonal(pairwise_sims, 0.0)

    n_dyn = rm.n_dynamic
    utilities = np.ones(n_dyn) * 0.0  # cold-start: no historical utility

    # ── Run selection ──────────────────────────────────────────────────
    results: dict[str, dict] = {}
    all_n_selected: list[int] = []
    all_chars: list[int] = []

    t0 = time.time()
    for qi, q in enumerate(queries):
        qv = rm._vectorizer.transform([q])
        rel = cosine_similarity(qv, rv).ravel()

        if args.method in ("greedy", "both"):
            selected = greedy_select(
                rel, utilities, token_costs, pairwise_sims,
                args.top_k, args.budget, weights,
            )
        elif args.method == "exact":
            selected = exact_select(
                rel, utilities, token_costs, pairwise_sims,
                args.top_k, args.budget, weights,
            )
        else:
            selected = []

        all_n_selected.append(len(selected))
        total_chars = sum(int(token_costs[i]) for i in selected)
        all_chars.append(total_chars)

        if (qi + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"  [{qi+1}/{len(queries)}] avg_selected={np.mean(all_n_selected):.1f} "
                  f"avg_chars={np.mean(all_chars):.0f} ({elapsed:.0f}s)")

    elapsed = time.time() - t0
    avg_n = float(np.mean(all_n_selected))
    avg_chars = float(np.mean(all_chars))

    print(f"\n{'='*60}")
    print(f"  {args.method.upper()} Results")
    print(f"{'='*60}")
    print(f"  Avg rules selected: {avg_n:.2f}")
    print(f"  Avg dynamic chars:  {avg_chars:.0f}")
    print(f"  Time: {elapsed:.1f}s ({elapsed/len(queries)*1000:.1f}ms/query)")

    # Save
    out_path = os.path.join(_PROJECT_ROOT, "outputs",
        f"moar_baseline_{args.method}_n{len(queries)}.json")
    summary = {
        "method": args.method, "top_k": args.top_k, "budget": args.budget,
        "weights": list(weights), "n_queries": len(queries),
        "avg_n_selected": avg_n, "avg_chars": avg_chars,
        "time_s": elapsed,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {out_path}")


def parse_weights(s: str) -> tuple[float, float, float, float]:
    parts = [float(x.strip()) for x in s.split(",")]
    t = tuple(parts[:4])
    if len(t) < 4:
        t = (0.4, 0.3, 0.2, 0.1)
    return t


if __name__ == "__main__":
    main()
