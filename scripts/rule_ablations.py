#!/usr/bin/env python3
"""Leave-one-out rule ablation: measure each dynamic rule's marginal contribution.

For each rule r_j, tests Core + (all dynamic except r_j) on val set.
Δ_j = score_full - score_without_j.  Positive = rule adds value.
"""
from __future__ import annotations

import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import chat_target
from skillopt.rule_atomizer import CORE_RULES, DYNAMIC_RULES


def load_items(split, limit=0):
    d = os.path.join(_ROOT, "data", "searchqa_split", "test" if split == "valid_unseen" else "val")
    with open(os.path.join(d, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    return items[:limit] if limit > 0 else items


def precompute_skills(items, top_k, budget, excluded_idx):
    """Pre-compute skill strings for all items under one config."""
    rules = [r for i, r in enumerate(DYNAMIC_RULES) if i != excluded_idx]
    texts = [r.text for r in rules]
    core = "\n\n".join(r.text for r in CORE_RULES)
    tfidf = TfidfVectorizer(max_features=2048, ngram_range=(1,2), stop_words="english")
    mat = tfidf.fit_transform(texts)
    skills = []
    for it in items:
        qv = tfidf.transform([it["question"]])
        sims = cosine_similarity(qv, mat).flatten()
        k = min(top_k, len(rules))
        indices = sorted(np.argsort(sims)[::-1][:k])
        parts = []; used = 0
        for idx in indices:
            t = rules[idx].text
            if used + len(t) > budget and parts: break
            parts.append(t); used += len(t) + 1
        d = "\n".join(parts)
        skills.append((core + "\n\n" + d) if d else core)
    return skills


def infer_one(item, skill):
    sys = _build_system(skill)
    usr = _build_user(item["question"], item.get("context", ""))
    try:
        resp, _ = chat_target(sys, usr, max_completion_tokens=512, stage="ablation")
    except Exception:
        resp = ""
    return {"hard": int(evaluate(resp, item.get("answers", []))["em"])}


def evaluate_precomputed(items, precomputed_skills, workers=48):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(infer_one, items[i], precomputed_skills[i]) for i in range(len(items))]
        results = [f.result() for f in futs]
    return np.mean([r["hard"] for r in results])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="valid_seen")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--workers", type=int, default=48)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    items = load_items(args.split, args.limit)
    print(f"Ablation: {len(items)} items, top_k={args.top_k}")

    # Precompute all 19 configs (full + each leave-one-out)
    print("Precomputing TF-IDF configs...")
    all_skills = {}
    all_skills["full"] = precompute_skills(items, args.top_k, args.budget, None)
    print(f"  full (n={len(DYNAMIC_RULES)}): done")
    for i in range(len(DYNAMIC_RULES)):
        all_skills[f"minus_{i}"] = precompute_skills(items, args.top_k, args.budget, i)
        print(f"  -R{i:02d} ({DYNAMIC_RULES[i].id}): done")

    # Evaluate full
    t0 = time.time()
    full_score = evaluate_precomputed(items, all_skills["full"], args.workers)
    print(f"\n  FULL (n={len(DYNAMIC_RULES)}): hard={full_score:.4f} ({time.time()-t0:.0f}s)")

    # Leave-one-out
    deltas = {}
    for i in range(len(DYNAMIC_RULES)):
        t0 = time.time()
        score = evaluate_precomputed(items, all_skills[f"minus_{i}"], args.workers)
        delta = full_score - score
        deltas[i] = delta
        label = "+" if delta > 0.003 else ("-" if delta < -0.003 else "~")
        print(f"  -R{i:02d} ({DYNAMIC_RULES[i].id}): hard={score:.4f} Δ={delta:+.4f} {label} "
              f"({DYNAMIC_RULES[i].text[:50]}...) ({time.time()-t0:.0f}s)")

    # Summary
    pos = [(i, d) for i, d in deltas.items() if d > 0.001]
    neg = [(i, d) for i, d in deltas.items() if d < -0.001]
    zero = [(i, d) for i, d in deltas.items() if abs(d) <= 0.001]
    print(f"\n{'='*60}")
    print(f"  SUMMARY: +{len(pos)} positive, ~{len(zero)} neutral, -{len(neg)} negative")
    print(f"{'='*60}")
    for label, items_list in [("Positive contributors", pos), ("Near-zero", zero), ("Negative (remove)", neg)]:
        if items_list:
            print(f"\n  {label}:")
            for i, d in sorted(items_list, key=lambda x: -x[1]):
                print(f"    R{i:02d} Δ={d:+.4f} — {DYNAMIC_RULES[i].text[:80]}")

    # Save
    out = {"full_score": float(full_score), "n_items": len(items),
           "deltas": {DYNAMIC_RULES[i].id: float(d) for i, d in deltas.items()}}
    out_path = os.path.join(_ROOT, "outputs", "rule_ablation.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
