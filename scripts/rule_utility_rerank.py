#!/usr/bin/env python3
"""Rule-level historical contribution re-ranking.

Phase 1: Run TF-IDF retrieval on val set, compute per-rule utility U(r).
Phase 2: Test re-ranked retrieval (α·TF-IDF + β·U(r)) on test set.
"""
from __future__ import annotations

import argparse, json, os, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

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
from skillopt.rule_atomizer import CORE_RULES, DYNAMIC_RULES, DYNAMIC_TEXTS

# ── Rule utility tracker ────────────────────────────────────────────────

class RuleScorer:
    """Track per-rule utility from observed results and re-rank with it."""

    def __init__(self, top_k: int = 5, token_budget: int = 2000,
                 alpha: float = 0.5, beta: float = 0.5):
        self.top_k = top_k
        self.budget = token_budget
        self.alpha = alpha
        self.beta = beta
        self.core_text = "\n\n".join(r.text for r in CORE_RULES)

        # TF-IDF
        self.tfidf = TfidfVectorizer(max_features=2048, ngram_range=(1, 2), stop_words="english")
        self.tfidf_matrix = self.tfidf.fit_transform(DYNAMIC_TEXTS)

        # Per-rule stats
        self.rule_selected = defaultdict(int)   # times rule was in top-K
        self.rule_correct = defaultdict(int)    # times selected AND answer correct

    # ── Phase 1: observe ──────────────────────────────────────────────

    def record_trial(self, query: str, correct: bool) -> None:
        """Record which rules would be selected for this query and outcome."""
        qv = self.tfidf.transform([query])
        sims = cosine_similarity(qv, self.tfidf_matrix).flatten()
        k = min(self.top_k, len(DYNAMIC_RULES))
        indices = list(np.argsort(sims)[::-1][:k])
        for i in indices:
            self.rule_selected[i] += 1
            if correct:
                self.rule_correct[i] += 1

    def compute_utility(self) -> dict[int, float]:
        """Compute U(r) = inverse-frequency bonus (-log(freq), clipped).

        Rules that match everything (freq near 1.0) get nearly 0 bonus.
        Rules that match very specific queries (low freq) get rewarded.
        """
        total = max(self.rule_selected.values(), default=1)
        util = {}
        for i in range(len(DYNAMIC_RULES)):
            n = self.rule_selected.get(i, 0)
            freq = n / total if total > 0 else 0.0
            # IDF-style: -log(freq + epsilon), clipped to [-0.5, 1.0]
            import math
            idf_bonus = -math.log(max(freq, 0.02))
            util[i] = max(-0.5, min(1.0, idf_bonus / 3.0))
        return util

    # ── Phase 2: re-rank ─────────────────────────────────────────────

    def retrieve_with_utility(self, query: str, utility: dict[int, float]) -> str:
        """Retrieve and re-rank: S(r,q) = α·TF-IDF_norm(r,q) + β·U(r)."""
        qv = self.tfidf.transform([query])
        tfidf_sims = cosine_similarity(qv, self.tfidf_matrix).flatten()

        # Normalize TF-IDF to [0,1]
        tfidf_min, tfidf_max = tfidf_sims.min(), tfidf_sims.max()
        if tfidf_max - tfidf_min > 1e-9:
            tfidf_norm = (tfidf_sims - tfidf_min) / (tfidf_max - tfidf_min)
        else:
            tfidf_norm = np.ones_like(tfidf_sims) * 0.5

        # Combined score
        scores = np.zeros(len(DYNAMIC_RULES))
        for i in range(len(DYNAMIC_RULES)):
            u = utility.get(i, 0.5)
            scores[i] = self.alpha * tfidf_norm[i] + self.beta * u

        k = min(self.top_k, len(DYNAMIC_RULES))
        indices = list(np.argsort(scores)[::-1][:k])
        selected = sorted(indices)

        parts = []; used = 0
        for i in selected:
            t = DYNAMIC_RULES[i].text
            if used + len(t) > self.budget and parts: break
            parts.append(t); used += len(t) + 1
        return "\n".join(parts)

    def build_skill_tfidf(self, query: str) -> str:
        """Build skill with TF-IDF-only retrieval."""
        qv = self.tfidf.transform([query])
        sims = cosine_similarity(qv, self.tfidf_matrix).flatten()
        k = min(self.top_k, len(DYNAMIC_RULES))
        indices = sorted(np.argsort(sims)[::-1][:k])
        parts = []; used = 0
        for i in indices:
            t = DYNAMIC_RULES[i].text
            if used + len(t) > self.budget and parts: break
            parts.append(t); used += len(t) + 1
        d = "\n".join(parts)
        return (self.core_text + "\n\n" + d) if d else self.core_text

    def build_skill_reranked(self, query: str, utility: dict[int, float]) -> str:
        """Build skill with utility-re-ranked retrieval."""
        d = self.retrieve_with_utility(query, utility)
        return (self.core_text + "\n\n" + d) if d else self.core_text


# ── Inference ──────────────────────────────────────────────────────────

def infer_one(item, build_fn, *args):
    q = item["question"]
    skill = build_fn(q, *args)
    system = _build_system(skill)
    user = _build_user(q, item.get("context", ""))
    try:
        resp, _ = chat_target(system, user, max_completion_tokens=512, stage="rerank")
    except Exception:
        resp = ""
    ev = evaluate(resp, item.get("answers", []))
    return {"id": item["id"], "hard": int(ev["em"])}

def load_items(split: str, limit: int = 0) -> list[dict]:
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split")
    path = os.path.join(data_dir, "test", "items.json") if split == "valid_unseen" \
           else os.path.join(data_dir, "val", "items.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return items[:limit] if limit > 0 else items


# ── Main ──────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--alpha", type=float, default=0.5, help="TF-IDF weight")
    p.add_argument("--beta", type=float, default=0.5, help="Utility weight")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--workers", type=int, default=48)
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def main():
    args = parse_args()
    print(f"Top-K={args.top_k} Budget={args.budget} α={args.alpha} β={args.beta}")

    # Phase 1: compute U(r) on val set
    val_items = load_items("valid_seen")  # 200 items
    print(f"\nPhase 1: Computing U(r) on val set ({len(val_items)} items)...")
    rs = RuleScorer(top_k=args.top_k, token_budget=args.budget,
                    alpha=args.alpha, beta=args.beta)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [(ex.submit(infer_one, item, rs.build_skill_tfidf), item) for item in val_items]
        for fut, item in futs:
            result = fut.result()
            rs.record_trial(item["question"], result["hard"] == 1)
    utility = rs.compute_utility()
    t1 = time.time()

    print(f"  Completed in {t1-t0:.0f}s")
    print(f"\n  Rule utilities U(r):")
    for i in sorted(utility, key=utility.get, reverse=True):
        r = DYNAMIC_RULES[i]
        n = rs.rule_selected.get(i, 0)
        c = rs.rule_correct.get(i, 0)
        print(f"    R{r.id[-2:]}: U={utility[i]:.3f} (correct={c}/{n} selected) {r.text[:60]}...")

    # Phase 2: test on hold-out test set
    test_items = load_items("valid_unseen", args.limit)
    print(f"\nPhase 2: Testing on test set ({len(test_items)} items)...")

    def run_method(label, build_fn, *extra_args):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            batch = [ex.submit(infer_one, item, build_fn, *extra_args) for item in test_items]
            batch = [f.result() for f in batch]
        hard = np.mean([r["hard"] for r in batch])
        elapsed = time.time() - t0
        print(f"  {label:>20s}: hard={hard:.4f} time={elapsed:.0f}s")
        return hard

    tfidf = run_method("TF-IDF (baseline)", rs.build_skill_tfidf)
    reranked = run_method("TF-IDF+Utility", rs.build_skill_reranked, utility)
    print(f"\n  TF-IDF+Utility - TF-IDF delta: {reranked - tfidf:+.4f}")


if __name__ == "__main__":
    main()
