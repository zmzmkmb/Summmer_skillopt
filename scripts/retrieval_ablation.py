#!/usr/bin/env python3
"""Inference-only retrieval ablation with multi-seed stability verification.

Tests Core Only, Core+Random, Core+TF-IDF, Core+Semantic on fixed atomized rules.
Records per-question hard scores for McNemar paired test.
"""
from __future__ import annotations

import argparse, hashlib, json, math, os, statistics, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
import random as _random
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import chat_target
from skillopt.rule_atomizer import CORE_RULES, DYNAMIC_RULES, DYNAMIC_TEXTS

# Full-text vectors for dual-channel retrieval
DYNAMIC_FULL_TEXTS: list[str] = [r.text for r in DYNAMIC_RULES]


@dataclass
class RunResult:
    method: str
    seed: int
    hard: float
    soft: float
    per_item: list[int] = field(default_factory=list)  # 0/1 per question
    time_s: float = 0.0


class AtomicRM:
    """Fixed atomized rule memory with dual-channel TF-IDF support.

    Parameters
    ----------
    lambda_trigger : float
        Weight on trigger-channel TF-IDF. 1.0=pure trigger, 0.0=pure text.
        Only used when method == "dual".
    """

    def __init__(self, top_k: int = 5, token_budget: int = 2000,
                 method: str = "tfidf", seed: int = 0, _semantic_sims=None,
                 lambda_trigger: float = 0.5, gamma: float = 0.0):
        self.top_k = top_k
        self.token_budget = token_budget
        self.method = method
        self.seed = seed
        self.lambda_trigger = lambda_trigger
        self.gamma = gamma
        self.core_text = "\n\n".join(r.text for r in CORE_RULES)

        # Build TF-IDF on triggers
        self._tfidf = TfidfVectorizer(max_features=2048, ngram_range=(1, 2), stop_words="english")
        self._tfidf_matrix = self._tfidf.fit_transform(DYNAMIC_TEXTS)

        # Build TF-IDF on full rule texts (for dual-channel)
        self._text_tfidf = TfidfVectorizer(max_features=2048, ngram_range=(1, 2), stop_words="english")
        self._text_tfidf_matrix = self._text_tfidf.fit_transform(DYNAMIC_FULL_TEXTS)

        # Build semantic embeddings (lazy)
        self._semantic_matrix = _semantic_sims
        if method == "semantic" and self._semantic_matrix is None:
            self._semantic_matrix = _build_semantic_embeddings()

    def retrieve(self, query: str) -> str:
        k = min(self.top_k, len(DYNAMIC_RULES))
        if k == 0 or self.method == "core_only":
            return ""

        if self.method == "random":
            seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16) + self.seed
            rng = _random.Random(seed)
            indices = rng.sample(range(len(DYNAMIC_RULES)), k)
        elif self.method in ("tfidf", "keyword"):
            qv = self._tfidf.transform([query])
            sims = cosine_similarity(qv, self._tfidf_matrix).flatten()
            # Keyword soft-bonus if gamma > 0
            if self.method == "keyword" and self.gamma > 0:
                sims = self._apply_keyword_bonus(query, sims)
            indices = list(np.argsort(sims)[::-1][:k])
        elif self.method == "dual":
            # Trigger channel
            qv_t = self._tfidf.transform([query])
            sims_t = cosine_similarity(qv_t, self._tfidf_matrix).flatten()
            # Text channel
            qv_x = self._text_tfidf.transform([query])
            sims_x = cosine_similarity(qv_x, self._text_tfidf_matrix).flatten()
            # Normalize each to [0,1] then fuse
            for sims in (sims_t, sims_x):
                mn, mx = sims.min(), sims.max()
                if mx - mn > 1e-9:
                    sims -= mn; sims /= (mx - mn)
            combined = self.lambda_trigger * sims_t + (1 - self.lambda_trigger) * sims_x
            indices = list(np.argsort(combined)[::-1][:k])
        elif self.method == "semantic" and self._semantic_matrix is not None:
            q_emb = _semantic_encode(query)
            sims = cosine_similarity([q_emb], self._semantic_matrix)[0]
            indices = list(np.argsort(sims)[::-1][:k])
        else:
            return ""

        selected = list(indices)  # preserve relevance rank order
        parts = []; used = 0
        for i in selected:
            t = DYNAMIC_RULES[i].text
            if used + len(t) > self.token_budget and parts: break
            parts.append(t); used += len(t) + 1
        return "\n".join(parts)

    def _apply_keyword_bonus(self, query: str, sims: np.ndarray) -> np.ndarray:
        """Add γ × K(r,q) to TF-IDF scores. K = fraction of rule keywords found in query."""
        import re as _re
        q_words = set(_re.findall(r'[a-zA-Z]{2,}', query.lower()))
        result = sims.copy()
        for i, rule in enumerate(DYNAMIC_RULES):
            if not rule.keywords:
                continue
            kw_set = set(k.lower() for k in rule.keywords)
            if not kw_set:
                continue
            hit = len(kw_set & q_words)
            K = hit / len(kw_set)
            result[i] += self.gamma * K
        return result

    def build_skill(self, query: str) -> str:
        d = self.retrieve(query)
        return (self.core_text + "\n\n" + d) if d else self.core_text


# ── Semantic embedding (lazy-load sentence-transformers) ─────────────────

_SEMANTIC_MODEL = None

def _load_semantic_model():
    global _SEMANTIC_MODEL
    if _SEMANTIC_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SEMANTIC_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            print("  [semantic] loaded all-MiniLM-L6-v2")
        except ImportError:
            print("  [semantic] sentence-transformers not installed, falling back to sklearn PCA on TF-IDF")
            _SEMANTIC_MODEL = "pca"

def _semantic_encode(texts):
    """Encode text(s) to embedding vector(s). Returns numpy array."""
    _load_semantic_model()
    if isinstance(_SEMANTIC_MODEL, str) and _SEMANTIC_MODEL == "pca":
        # Fallback: use TF-IDF + PCA to 64 dims
        from sklearn.decomposition import TruncatedSVD
        tfidf = TfidfVectorizer(max_features=2048)
        all_texts = DYNAMIC_TEXTS + [texts] if isinstance(texts, str) else DYNAMIC_TEXTS + list(texts)
        m = tfidf.fit_transform(all_texts)
        svd = TruncatedSVD(n_components=64)
        emb = svd.fit_transform(m)
        return emb[-1] if isinstance(texts, str) else emb[len(DYNAMIC_TEXTS):]
    if isinstance(texts, str):
        return _SEMANTIC_MODEL.encode([texts])[0]
    return _SEMANTIC_MODEL.encode(list(texts))

def _build_semantic_embeddings():
    """Pre-compute semantic embeddings for all dynamic rules."""
    emb = _semantic_encode(DYNAMIC_TEXTS)
    if emb.ndim == 1:
        emb = emb.reshape(1, -1)
    return np.array(emb)


# ── Build RM per method ─────────────────────────────────────────────────

def build_rm(method: str, top_k: int, budget: int, seed: int,
             semantic_matrix=None, lambda_trigger: float = 0.5,
             gamma: float = 0.0) -> Any:
    if method == "core_only":
        class _RM:
            def build_skill(self, q):
                return "\n\n".join(r.text for r in CORE_RULES)
        return _RM()
    return AtomicRM(top_k=top_k, token_budget=budget, method=method,
                    seed=seed, _semantic_sims=semantic_matrix,
                    lambda_trigger=lambda_trigger, gamma=gamma)


def infer_one(item: dict, rm) -> dict:
    q = item["question"]
    skill = rm.build_skill(q)
    system = _build_system(skill)
    user = _build_user(q, item.get("context", ""))
    try:
        resp, _ = chat_target(system, user, max_completion_tokens=512, stage="ablation")
    except Exception:
        resp = ""
    ev = evaluate(resp, item.get("answers", []))
    return {"id": item["id"], "hard": int(ev["em"]), "soft": ev["f1"]}


# ── McNemar test ────────────────────────────────────────────────────────

def mcnemar_paired(results_a: list[int], results_b: list[int]) -> dict:
    """McNemar test: are A and B significantly different on the same items?"""
    a, b = np.array(results_a), np.array(results_b)
    b10 = int(np.sum((a == 1) & (b == 0)))  # A right, B wrong
    b01 = int(np.sum((a == 0) & (b == 1)))  # A wrong, B right
    n_discordant = b10 + b01
    if n_discordant < 10:
        return {"b10": b10, "b01": b01, "p": None, "warning": "<10 discordant pairs"}
    # Continuity-corrected chi-squared
    stat = (abs(b10 - b01) - 1) ** 2 / n_discordant
    from scipy.stats import chi2
    p = 1.0 - chi2.cdf(stat, 1)
    return {"b10": b10, "b01": b01, "n_discordant": n_discordant, "p": float(p),
            "significant": p < 0.05}


# ── Load ────────────────────────────────────────────────────────────────

def load_items(split: str, limit: int = 0) -> list[dict]:
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split")
    path = os.path.join(data_dir, "test", "items.json") if split == "valid_unseen" \
           else os.path.join(data_dir, "val", "items.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return items[:limit] if limit > 0 else items


# ── Main ────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", default="valid_unseen")
    p.add_argument("--methods", nargs="+", default=["core_only","random","tfidf"])
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--n-seeds", type=int, default=3)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=48)
    p.add_argument("--lambda-trigger", type=float, default=0.5,
                   help="Weight on trigger channel for dual method (0.0=text-only, 1.0=trigger-only)")
    p.add_argument("--gamma", type=float, default=0.0,
                   help="Keyword soft-bonus weight for keyword method")
    return p.parse_args()


def main():
    args = parse_args()
    items = load_items(args.split, args.limit)
    ids = [it["id"] for it in items]
    n = len(items)
    print(f"Items: {n} | Methods: {args.methods} | Seeds: {args.n_seeds} | Top-K: {args.top_k}")

    # Pre-compute semantic matrix once
    sem_matrix = None
    if "semantic" in args.methods:
        print("Pre-computing semantic embeddings...")
        sem_matrix = _build_semantic_embeddings()

    all_results: list[RunResult] = []
    per_item: dict[str, dict[int, list[int]]] = {m: {} for m in args.methods}  # method -> seed -> [hards]

    for method in args.methods:
        for seed in range(args.n_seeds):
            t0 = time.time()
            rm = build_rm(method, args.top_k, args.budget, seed, sem_matrix,
                          lambda_trigger=args.lambda_trigger, gamma=args.gamma)
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                batch = [ex.submit(infer_one, item, rm) for item in items]
                batch = [f.result() for f in batch]
            hards = [r["hard"] for r in batch]
            softs = [r["soft"] for r in batch]
            elapsed = time.time() - t0
            rr = RunResult(method, seed, np.mean(hards), np.mean(softs),
                           per_item=hards, time_s=elapsed)
            all_results.append(rr)
            per_item[method][seed] = hards
            print(f"  {method:>12s} seed={seed}: hard={rr.hard:.4f} soft={rr.soft:.4f} time={elapsed:.0f}s")

    # ── Summary table ─────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  SUMMARY — Mean ± Std over seeds")
    print(f"{'='*70}")
    print(f"  {'Method':<14s} {'Mean Hard':>10s} {'Std':>8s} {'Min':>8s} {'Max':>8s} {'Time':>8s}")
    print(f"  {'-'*56}")
    for method in args.methods:
        mrs = [r for r in all_results if r.method == method]
        hards = [r.hard for r in mrs]
        times = [r.time_s for r in mrs]
        print(f"  {method:<14s} {np.mean(hards):>10.4f} {np.std(hards, ddof=1):>8.4f} "
              f"{min(hards):>8.4f} {max(hards):>8.4f} {np.mean(times):>7.0f}s")

    # ── McNemar tests ─────────────────────────────────────────────────
    # Use seed=0 per-question results for pairwise comparison
    print(f"\n{'='*70}")
    print("  McNemar paired tests (seed=0, per-question correctness)")
    print(f"{'='*70}")
    pairs_to_test = []
    if "tfidf" in args.methods and "random" in args.methods:
        pairs_to_test.append(("tfidf", "random", "TF-IDF vs Random"))
    if "tfidf" in args.methods and "core_only" in args.methods:
        pairs_to_test.append(("tfidf", "core_only", "TF-IDF vs Core Only"))
    if "random" in args.methods and "core_only" in args.methods:
        pairs_to_test.append(("random", "core_only", "Random vs Core Only"))

    for ma, mb, label in pairs_to_test:
        a_seeds = per_item.get(ma, {})
        b_seeds = per_item.get(mb, {})
        if 0 not in a_seeds or 0 not in b_seeds:
            continue
        r = mcnemar_paired(a_seeds[0], b_seeds[0])
        sig = ""
        if r.get("significant"):
            sig = " * SIGNIFICANT (p<0.05)"
        elif r.get("p") is not None:
            sig = f" (p={r['p']:.4f})"
        else:
            sig = f" (discordant<10)"
        print(f"  {label}: {ma} correct={r['b10']}, {mb} correct={r['b01']}, "
              f"discordant={r.get('n_discordant','?')}{sig}")

    # ── Save per-question results ─────────────────────────────────────
    out_path = os.path.join(_PROJECT_ROOT, "outputs", "ablation_per_item.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    save_data = {}
    for method, seeds in per_item.items():
        save_data[method] = {str(s): h for s, h in seeds.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=1)
    print(f"\n  Per-question results saved to: {out_path}")


if __name__ == "__main__":
    main()
