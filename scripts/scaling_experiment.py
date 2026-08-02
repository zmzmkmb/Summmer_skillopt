#!/usr/bin/env python3
"""Scaling experiment: MOAR vs TF-IDF vs Greedy-Cold across rule library sizes.

Measures retrieval latency and selection stats as rule count grows.
No LLM inference — pure selection performance.
Greedy-Cold uses weighted greedy selection with zero utility (cold start).

Usage:
    python scripts/scaling_experiment.py --limit 200
"""
from __future__ import annotations

import argparse, json, os, sys, time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from skillopt.rag_rule_selector import RuleMemory
from scripts.infer_baselines import greedy_select

LIB_DIR = os.path.join(_PROJECT_ROOT, "outputs", "rule_libraries")
SIZES = [("0008", 6), ("0024", 31), ("0050", 94), ("0200", 136)]

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=200)
    return p.parse_args()

def time_method(name, skill, queries, top_k, budget, weights):
    rm = RuleMemory(skill, method="tfidf",
                     top_k=top_k, token_budget=budget)
    n = rm.n_dynamic
    results = []

    # Greedy-Cold (utility = 0)
    for method_label, rm_method in [("TF-IDF", "tfidf"), ("Greedy-Cold", "greedy"), ("MOAR", "moar")]:
        t0 = time.time()
        n_sel_list, n_char_list = [], []

        if rm_method == "greedy":
            # Greedy-Cold: uses same TF-IDF infrastructure for relevance, zero utility
            mr = RuleMemory(skill, method="tfidf", top_k=top_k, token_budget=budget)
            rv = mr._rule_matrix.toarray() if hasattr(mr._rule_matrix, 'toarray') else np.asarray(mr._rule_matrix)
            rules = [r.full_text for r in mr.dynamic_rules]
            try:
                from skillopt.moar.tokenizer import count_tokens
                costs = np.array([count_tokens(t) for t in rules], dtype=float)
            except Exception:
                costs = np.array([len(t) for t in rules], dtype=float)
            from sklearn.metrics.pairwise import cosine_similarity
            sims = cosine_similarity(rv); np.fill_diagonal(sims, 0.0)
            n_d = len(rules)
            for q in queries:
                qv = mr._vectorizer.transform([q])
                rel = cosine_similarity(qv, rv).ravel()
                sel = greedy_select(rel, np.zeros(n_d), costs, sims, top_k, budget,
                                    (0.4, 0.3, 0.2, 0.1))
                n_sel_list.append(len(sel))
                sel_chars = sum(len(rules[i]) for i in sel)
                n_char_list.append(sel_chars)
        else:
            mr = RuleMemory(skill, method=rm_method, top_k=top_k,
                            token_budget=budget,
                            moar_pop_size=30, moar_generations=15)
            for q in queries:
                txt = mr.retrieve(q, top_k=top_k, token_budget=budget)
                # 从检索器内部获取结构化选择数，避免 Markdown heading 计数遗漏 ### 规则
                sel = mr._last_selections.get(q, [])
                n_sel_list.append(len(sel))
                n_char_list.append(len(txt))

        elapsed = time.time() - t0
        avg_sel = float(np.mean(n_sel_list))
        avg_char = float(np.mean(n_char_list))
        ms_per = elapsed / len(queries) * 1000
        results.append({
            "method": rm_method, "n_rules": n, "n_queries": len(queries),
            "avg_selected": avg_sel, "avg_chars": avg_char,
            "time_ms_per_query": ms_per,
        })
        print(f"  {rm_method:12s} | n={n:3d} | {avg_sel:.1f} rules | "
              f"{avg_char:.0f} chars | {ms_per:.1f} ms/q")

    return results

def main():
    args = parse_args()
    # Load test queries
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    with open(os.path.join(data_dir, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    if args.limit > 0: items = items[:args.limit]
    queries = [it["question"] for it in items]
    print(f"Queries: {len(queries)}, top_k=5, budget=2000\n")

    weights = (0.4, 0.3, 0.2, 0.1)
    all_results = []

    print(f"{'Method':6s} | {'n':3s} | {'sel':>4s} | {'chars':>5s} | {'ms/q':>6s}")
    print("-" * 45)

    for filename, expected_n in SIZES:
        path = os.path.join(LIB_DIR, f"rules_{filename}.md")
        with open(path, encoding="utf-8") as f:
            skill = f.read()
        n = skill.count("## Rule ") + skill.count("## ")
        if n < 2: n = expected_n
        print(f"--- {n} rules ({len(skill)//1024}KB) ---")
        res = time_method(filename, skill, queries, top_k=5, budget=2000, weights=weights)
        all_results.extend(res)

    # Save
    out_path = os.path.join(_PROJECT_ROOT, "outputs", "scaling_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved: {out_path}")

if __name__ == "__main__":
    main()
