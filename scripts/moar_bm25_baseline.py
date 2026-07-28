#!/usr/bin/env python3
"""BM25 baseline for MOAR comparison — pure numpy + rank_bm25.

Usage:
    python scripts/moar_bm25_baseline.py \
        --skill outputs/searchqa_rag/best_skill.md \
        --limit 200
"""
from __future__ import annotations

import argparse, json, os, sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from rank_bm25 import BM25Okapi

from skillopt.rag_rule_selector import RuleMemory


def tokenize(text: str) -> list[str]:
    return text.lower().split()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", type=str, required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    args = p.parse_args()

    with open(os.path.abspath(args.skill), encoding="utf-8") as f:
        skill_content = f.read()

    rm = RuleMemory(skill_content, method="tfidf",
                     top_k=args.top_k, token_budget=args.budget)
    rules = [r.full_text for r in rm.dynamic_rules]
    n_dyn = len(rules)
    print(f"Skill: core={rm.n_core} dynamic={n_dyn}")

    if n_dyn == 0:
        print("No dynamic rules."); return

    # Build BM25 index
    tokenized = [tokenize(r) for r in rules]
    bm25 = BM25Okapi(tokenized)

    # Load queries
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    with open(os.path.join(data_dir, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    if args.limit > 0:
        items = items[:args.limit]
    print(f"Queries: {len(items)}")

    all_n_selected, all_chars, all_tokens = [], [], []
    for qi, it in enumerate(items):
        q_tokens = tokenize(it["question"])
        scores = bm25.get_scores(q_tokens)
        # Top-K by BM25, then budget-constrained concatenation
        order = np.argsort(-scores)
        selected = []
        used = 0
        for idx in order:
            if len(selected) >= args.top_k:
                break
            cost = len(rules[idx])
            if used + cost > args.budget and selected:
                break
            selected.append(int(idx))
            used += cost

        all_n_selected.append(len(selected))
        all_chars.append(used)

        if (qi + 1) % 200 == 0:
            a = np.mean(all_n_selected)
            c = np.mean(all_chars)
            print(f"  [{qi+1}/{len(items)}] avg_selected={a:.1f} avg_chars={c:.0f}")

    avg_n = float(np.mean(all_n_selected))
    avg_c = float(np.mean(all_chars))
    print(f"\nBM25 Top-{args.top_k}: avg {avg_n:.1f} rules, {avg_c:.0f} chars/query")

    out = os.path.join(_PROJECT_ROOT, "outputs",
                       f"moar_baseline_bm25_n{len(items)}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"avg_n": avg_n, "avg_chars": avg_c, "n_queries": len(items),
                    "top_k": args.top_k, "budget": args.budget}, f, indent=2)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
