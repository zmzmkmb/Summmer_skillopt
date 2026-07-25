#!/usr/bin/env python3
"""Inference-only retrieval ablation — fixed RuleMemory, varying selection methods.

Compares: Core Only, Core+Random, Core+TF-IDF, Core+Semantic, Full Rules
on the SearchQA test set WITHOUT retraining.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random as _random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# Project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import chat_target
from skillopt.rule_atomizer import ALL_RULES, CORE_RULES, DYNAMIC_RULES, CORE_TEXTS, DYNAMIC_TEXTS


# ── Atomic RuleMemory (fixed rules, no markdown parsing) ─────────────────

class AtomicRuleMemory:
    """RuleMemory that works with pre-atomized rules instead of parsing markdown."""

    def __init__(self, top_k: int = 5, token_budget: int = 2000, method: str = "tfidf"):
        self.top_k = top_k
        self.token_budget = token_budget
        self.method = method
        self.core_text = "\n\n".join(r.text for r in CORE_RULES)

        # Build TF-IDF index for dynamic rules
        self._vectorizer = TfidfVectorizer(
            max_features=2048, ngram_range=(1, 2), stop_words="english",
        )
        self._rule_matrix = self._vectorizer.fit_transform(DYNAMIC_TEXTS)

    def retrieve(self, query: str) -> str:
        if self.method == "core_only":
            return ""
        k = min(self.top_k, len(DYNAMIC_RULES))
        if k == 0:
            return ""

        if self.method == "random":
            seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
            rng = _random.Random(seed)
            indices = rng.sample(range(len(DYNAMIC_RULES)), k)
        elif self.method == "tfidf":
            qv = self._vectorizer.transform([query])
            sims = cosine_similarity(qv, self._rule_matrix).flatten()
            indices = list(np.argsort(sims)[::-1][:k])
        else:
            return ""

        # Sort by original index for logical order
        selected = sorted(indices)
        parts = []
        used = 0
        for i in selected:
            text = DYNAMIC_RULES[i].text
            if used + len(text) > self.token_budget and parts:
                break
            parts.append(text)
            used += len(text) + 1
        return "\n".join(parts)

    def build_skill(self, query: str) -> str:
        """Build active skill for a single query."""
        dynamic = self.retrieve(query)
        if dynamic:
            return self.core_text + "\n\n" + dynamic
        return self.core_text


# ── Single-item inference ────────────────────────────────────────────────

def infer_one(item: dict, rule_memory: AtomicRuleMemory) -> dict:
    """Run one QA item with the given rule memory. Returns result dict."""
    question = item["question"]
    context = item.get("context", "")
    gold = item.get("answers", [])

    skill = rule_memory.build_skill(question)
    system = _build_system(skill)
    user = _build_user(question, context)

    try:
        response, _ = chat_target(system, user, max_completion_tokens=512, stage="ablation")
    except Exception as exc:
        response = ""

    eval_result = evaluate(response, gold)
    return {
        "id": item["id"],
        "hard": int(eval_result["em"]),
        "soft": eval_result["f1"],
        "response": response,
    }


# ── Main ─────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", default="valid_unseen", choices=["valid_unseen", "valid_seen"])
    p.add_argument("--methods", nargs="+", default=["core_only", "random", "tfidf"],
                   help="Which retrieval methods to test")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--token-budget", type=int, default=2000)
    p.add_argument("--limit", type=int, default=0, help="Limit items (0=all)")
    p.add_argument("--workers", type=int, default=24)
    return p.parse_args()


def load_items(split: str) -> list[dict]:
    """Load test items."""
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split")
    path = os.path.join(data_dir, split if split == "test" else "test", "items.json")
    # For valid_unseen, load test split (the gold evaluation set)
    if split == "valid_unseen":
        path = os.path.join(data_dir, "test", "items.json")
    elif split == "valid_seen":
        path = os.path.join(data_dir, "val", "items.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return items


def main():
    args = parse_args()
    items = load_items(args.split)
    if args.limit > 0:
        items = items[:args.limit]
    print(f"Loaded {len(items)} items from {args.split}")

    results: dict[str, dict] = {}

    for method in args.methods:
        print(f"\n{'='*60}")
        print(f"  Method: {method}  top_k={args.top_k}  budget={args.token_budget}")
        print(f"{'='*60}")

        rm = AtomicRuleMemory(top_k=args.top_k, token_budget=args.token_budget, method=method)
        t0 = time.time()

        # For full_rules, just use all rules concatenated
        if method == "full_rules":
            full_skill = "\n\n".join(r.text for r in ALL_RULES)
            class FullRM:
                def build_skill(self, q): return full_skill
            rm = FullRM()

        # For core_only, only core rules
        if method == "core_only":
            class CoreRM:
                def build_skill(self, q): return "\n\n".join(r.text for r in CORE_RULES)
            rm = CoreRM()

        if method == "random" or method == "tfidf":
            # Use AtomicRuleMemory
            pass

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(infer_one, item, rm) for item in items]
            batch_results = [f.result() for f in futs]

        hard = sum(r["hard"] for r in batch_results)
        soft = sum(r["soft"] for r in batch_results)
        n = len(batch_results)
        elapsed = time.time() - t0

        results[method] = {"hard": hard/n, "soft": soft/n, "n": n, "time": elapsed}
        print(f"  hard={hard/n:.4f}  soft={soft/n:.4f}  time={elapsed:.0f}s")

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Method':<20} {'Hard':>8} {'Soft':>8} {'Time':>8}")
    print(f"  {'-'*44}")
    for method, r in results.items():
        print(f"  {method:<20} {r['hard']:>8.4f} {r['soft']:>8.4f} {r['time']:>7.0f}s")
    print(f"  {'='*44}")
    print(f"  TF-IDF - Random delta: {results.get('tfidf',{}).get('hard',0) - results.get('random',{}).get('hard',0):+.4f}")
    print(f"  TF-IDF - CoreOnly delta: {results.get('tfidf',{}).get('hard',0) - results.get('core_only',{}).get('hard',0):+.4f}")


if __name__ == "__main__":
    main()
