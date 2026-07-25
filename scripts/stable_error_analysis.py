#!/usr/bin/env python3
"""Multi-seed stability analysis on val set. Identifies stable vs noisy errors.

Phase 1: Run TF-IDF Top-5 on val set with 3 seeds, flag stable errors.
Phase 2: Map each stable error to the rules retrieved for it.
"""
from __future__ import annotations

import argparse, json, os, sys, time
from collections import Counter, defaultdict
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
from skillopt.rule_atomizer import CORE_RULES, DYNAMIC_RULES, DYNAMIC_TEXTS


def load_items(split, limit=0):
    d = os.path.join(_ROOT, "data", "searchqa_split",
                     "test" if split == "valid_unseen" else "val")
    with open(os.path.join(d, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    return items[:limit] if limit > 0 else items


class TFIDFRunner:
    def __init__(self, top_k=5, budget=2000):
        self.top_k = top_k
        self.budget = budget
        self.core = "\n\n".join(r.text for r in CORE_RULES)

    def precompute(self, items):
        texts = [r.trigger for r in DYNAMIC_RULES]
        self.tfidf = TfidfVectorizer(max_features=2048, ngram_range=(1,2), stop_words="english")
        self.mat = self.tfidf.fit_transform(texts)

        self.item_skills = []
        self.item_rule_ids = []
        for it in items:
            q = it["question"]
            qv = self.tfidf.transform([q])
            sims = cosine_similarity(qv, self.mat).flatten()
            k = min(self.top_k, len(DYNAMIC_RULES))
            indices = sorted(np.argsort(sims)[::-1][:k])
            self.item_rule_ids.append([DYNAMIC_RULES[i].id for i in indices])
            parts = []; used = 0
            for i in indices:
                t = DYNAMIC_RULES[i].text
                if used + len(t) > self.budget and parts: break
                parts.append(t); used += len(t) + 1
            d = "\n".join(parts)
            self.item_skills.append((self.core + "\n\n" + d) if d else self.core)

    def infer(self, item, idx):
        skill = self.item_skills[idx]
        sys = _build_system(skill)
        usr = _build_user(item["question"], item.get("context", ""))
        try:
            resp, _ = chat_target(sys, usr, max_completion_tokens=512, stage="stable")
        except Exception:
            resp = ""
        return {"hard": int(evaluate(resp, item.get("answers", []))["em"])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="valid_seen")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--workers", type=int, default=48)
    p.add_argument("--n-seeds", type=int, default=3)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    items = load_items(args.split, args.limit)
    n = len(items)
    print(f"Stability analysis: {n} items, {args.n_seeds} seeds, top_k={args.top_k}")

    runner = TFIDFRunner(args.top_k)
    runner.precompute(items)

    # Run multiple seeds
    all_hards = []
    import random as _random
    _random.seed(42)
    seeds = [_random.randint(0, 9999) for _ in range(args.n_seeds)]

    for si, seed in enumerate(seeds):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            batch = [ex.submit(runner.infer, items[i], i) for i in range(n)]
            hards = [f.result()["hard"] for f in batch]
        all_hards.append(hards)
        acc = np.mean(hards)
        print(f"  seed={seed}: hard={acc:.4f} ({time.time()-t0:.0f}s)")

    # Classify each item
    stable_correct = 0; stable_wrong = 0; noisy = 0
    stable_errors = []; noisy_errors = []

    for i in range(n):
        scores = [all_hards[s][i] for s in range(args.n_seeds)]
        if all(s == 1 for s in scores):
            stable_correct += 1
        elif all(s == 0 for s in scores):
            stable_wrong += 1
            stable_errors.append(i)
        else:
            noisy += 1
            noisy_errors.append(i)

    print(f"\n  Stable correct: {stable_correct} ({stable_correct/n:.2%})")
    print(f"  Stable wrong:   {stable_wrong} ({stable_wrong/n:.2%})  ← rule fix targets")
    print(f"  Noisy (fluctuating): {noisy} ({noisy/n:.2%})  ← model noise, ignore")

    # Map stable errors to retrieved rules
    rule_error_count = Counter()
    rule_total_count = Counter()
    for i in range(n):
        rids = runner.item_rule_ids[i]
        for rid in rids:
            rule_total_count[rid] += 1
            if i in stable_errors:
                rule_error_count[rid] += 1

    print(f"\n=== Rule retrieval analysis ===")
    print(f"  {'Rule':<6} {'Retrieved':>8} {'Errors':>8} {'Error%':>8} {'Text'}")
    print(f"  {'-'*80}")
    for rid in sorted(rule_total_count, key=lambda r: rule_error_count.get(r,0)/max(rule_total_count.get(r,1),1), reverse=True):
        n_ret = rule_total_count[rid]
        n_err = rule_error_count.get(rid, 0)
        err_pct = n_err / n_ret * 100 if n_ret > 0 else 0
        rule = [r for r in DYNAMIC_RULES if r.id == rid][0]
        print(f"  {rid:<6} {n_ret:>8} {n_err:>8} {err_pct:>7.1f}% {rule.text[:60]}...")

    # Show sample stable errors
    print(f"\n=== Sample stable errors (first 5) ===")
    for idx in stable_errors[:5]:
        it = items[idx]
        rids = runner.item_rule_ids[idx]
        print(f"  Q: {it['question'][:80]}...")
        print(f"  A: {it.get('answers', ['?'])[0]}")
        print(f"  Rules: {rids}")
        print()

    # Save for downstream rule editing
    out = {
        "n_items": n, "stable_correct": stable_correct, "stable_wrong": stable_wrong,
        "noisy": noisy,
        "stable_error_indices": stable_errors,
        "all_hards": [[int(x) for x in hards] for hards in all_hards],
        "rule_retrieval": [[str(r) for r in runner.item_rule_ids[i]] for i in range(n)],
        "rule_error_rate": {rid: {"retrieved": rule_total_count[rid],
                                   "errors": rule_error_count.get(rid, 0)}
                            for rid in rule_total_count},
    }
    out_path = os.path.join(_ROOT, "outputs", "stable_error_analysis.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
