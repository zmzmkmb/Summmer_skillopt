#!/usr/bin/env python3
"""Unified baseline inference for BM25, Greedy-Cold, and Greedy-Utility.

SAME conditions as moar_searchqa_eval.py:
- _build_user(question, context) — same SearchQA context passages
- Same _build_system, chat_target, evaluate pipeline
- Tokenizer-based costs (same as MOAR)
- ThreadPoolExecutor for inference (same as MOAR main script)

Greedy-Cold:  zero historical utility (cold start).
Greedy-Utility: loads frozen moar_utility.json for per-rule precision scores.

Usage:
    python scripts/infer_baselines.py --method bm25 --limit 200
    python scripts/infer_baselines.py --method greedy-cold --limit 200
    python scripts/infer_baselines.py --method greedy-util --limit 200
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import (
    chat_target, configure_openai_compatible,
    set_optimizer_backend, set_optimizer_deployment,
    set_target_backend, set_target_deployment,
)
from skillopt.rag_rule_selector import RuleMemory


def _load_env(path: str | None = None):
    import os as _os
    if path is None:
        path = _os.path.join(_PROJECT_ROOT, ".env")
    if not _os.path.exists(path):
        return
    with open(path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("#") or not _line or "=" not in _line:
                continue
            if _line.startswith("export "):
                _line = _line[7:]
            _key, _, _val = _line.partition("=")
            _key = _key.strip()
            _val = _val.strip().strip('\"').strip("'")
            if _key and _val and _key not in _os.environ:
                _os.environ[_key] = _val


def _configure_target(model_name: str):
    _load_env()
    if "3.6" in model_name or model_name.startswith("qwen3"):
        from skillopt.model.anthropic_compatible_backend import (
            chat_target as _ant_ct,
            configure_anthropic_compatible,
        )
        import skillopt.model as _model
        _model.chat_target = _ant_ct
        configure_anthropic_compatible(
            target_base_url=os.environ.get(
                "TARGET_OPENAI_COMPATIBLE_BASE_URL",
                "https://dashscope.aliyuncs.com/apps/anthropic",
            ),
            target_api_key=os.environ.get("TARGET_OPENAI_COMPATIBLE_API_KEY", ""),
            target_model=model_name,
        )
    else:
        configure_openai_compatible(
            target_base_url=os.environ.get(
                "TARGET_S_OPENAI_COMPATIBLE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            target_api_key=os.environ.get("TARGET_S_OPENAI_COMPATIBLE_API_KEY", ""),
            target_model=model_name,
        )
    set_target_backend("openai_compatible")
    set_target_deployment(model_name)


def tokenize(s): return s.lower().split()


def greedy_select(relevance, utilities, costs, sims, top_k, budget, w):
    selected, remaining, used = [], list(range(len(relevance))), 0
    for _ in range(top_k):
        best, best_i = -1e9, -1
        for j in remaining:
            c = costs[j]
            if used + c > budget: continue
            s = w[0]*relevance[j] + w[1]*utilities[j] - w[2]*(c/budget)
            if selected: s -= w[3]*np.mean([sims[j,s] for s in selected])
            if s > best: best, best_i = s, j
        if best_i < 0: break
        c = costs[best_i]
        if used + c > budget: break
        selected.append(best_i); used += c; remaining.remove(best_i)
    return selected


def infer(method, skill_content, items, top_k, budget, weights, workers, **kwargs):
    utility_file = kwargs.get("utility_file", "")
    extra: dict = {}
    rm = RuleMemory(skill_content, method="tfidf", top_k=top_k, token_budget=budget)
    rules = [r.full_text for r in rm.dynamic_rules]
    core = rm.core_rules_text
    n = len(rules)

    from sklearn.metrics.pairwise import cosine_similarity
    rv = rm._rule_matrix.toarray() if hasattr(rm._rule_matrix, 'toarray') else np.asarray(rm._rule_matrix)
    try:
        from skillopt.moar.tokenizer import count_tokens
        costs = np.array([count_tokens(t) for t in rules], dtype=float)
    except Exception:
        costs = np.array([len(t) for t in rules], dtype=float)
    sims = cosine_similarity(rv); np.fill_diagonal(sims, 0.0)
    w = tuple(float(x) for x in weights.split(",")[:4])

    bm25 = None
    if "bm25" in method:
        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi([tokenize(r) for r in rules])

    # Load frozen utilities for Greedy-Utility
    frozen_utils = np.zeros(n)
    utility_sha256 = ""
    if "util" in method:
        utility_path = utility_file
        if not utility_path or not os.path.exists(utility_path):
            raise FileNotFoundError(
                "Greedy-Utility requires a frozen utility file.\n"
                "  Pass --utility-file <path> or ensure the file exists."
            )
        from skillopt.moar.tracker import UtilityTracker
        ut = UtilityTracker(persistence_path=utility_path)
        ut.register_rules(rules)
        frozen_utils = ut.compute_utilities("precision")
        nonzero_count = int((frozen_utils > 0).sum())
        if nonzero_count == 0:
            raise ValueError(
                f"Greedy-Utility: all {len(frozen_utils)} rule utilities are zero. "
                "Utility file appears unpopulated — re-run build_utility.py first."
            )
        with open(utility_path, "rb") as f:
            utility_sha256 = hashlib.sha256(f.read()).hexdigest()
        print(f"  Loaded utilities from {utility_path} "
              f"(SHA256: {utility_sha256[:16]}..., nonzero={nonzero_count}/{len(frozen_utils)})")
        extra["utility_file"] = utility_path
        extra["utility_sha256"] = utility_sha256
        extra["utility_nonzero_rules"] = nonzero_count

    # Phase 1: sequential rule selection (timed per query)
    t0 = time.time()
    sel_data: list[dict] = []
    for it in items:
        q = it["question"]; ctx = it.get("context", "")
        qv = rm._vectorizer.transform([q])
        rel = cosine_similarity(qv, rv).ravel()

        sel_start = time.time()
        if "bm25" in method:
            scores = bm25.get_scores(tokenize(q))
            order = np.argsort(-scores)
            sel, used = [], 0
            for idx in order:
                if len(sel) >= top_k: break
                c = costs[idx]
                if used + c > budget: continue
                sel.append(int(idx)); used += c
        else:
            sel = greedy_select(rel, frozen_utils, costs, sims, top_k, budget, w)
        sel_ms = (time.time() - sel_start) * 1000

        dynamic_text = "\n\n".join(
            rules[i] for i in sorted(sel, key=lambda i: rm.dynamic_rules[i].index))
        text = core + "\n\n" + dynamic_text if dynamic_text else core
        system = _build_system(text)
        user = _build_user(q, ctx)

        sel_data.append({
            "item": it, "system": system, "user": user,
            "sel": list(sel), "sel_ms": sel_ms,
            "sel_chars": len(dynamic_text),
            "input_chars": len(system) + len(user),
        })

    # Phase 2: parallel inference (preserving original ordering)
    n_items = len(items)
    batch_results: list[dict | None] = [None] * n_items

    def _infer_one(idx: int, system: str, user: str, it: dict) -> dict:
        api_error = None
        try:
            inf_start = time.time()
            import skillopt.model as _m
            resp, _ = _m.chat_target(
                system, user, max_completion_tokens=512,
                retries=2, stage="eval", timeout=60,
            )
            inf_ms = (time.time() - inf_start) * 1000
        except Exception as exc:
            resp = ""; inf_ms = 0
            api_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        ev = evaluate(resp, it.get("answers", []))
        result = {
            "sample_id": str(it["id"]),
            "hard": int(ev["em"]),
            "predicted": ev["predicted_answer"],
            "gold": it.get("answers", []),
            "inference_ms": inf_ms,
        }
        if api_error is not None:
            result["status"] = "api_error"
            result["error_type"] = api_error["type"]
            result["error"] = api_error["message"]
            result["hard"] = None
        else:
            result["status"] = "ok"
        return result

    t_inf_start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_infer_one, i, d["system"], d["user"], d["item"]): i
                for i, d in enumerate(sel_data)}
        for fut in as_completed(futs):
            idx = futs[fut]
            batch_results[idx] = fut.result()

    assert all(r is not None for r in batch_results), "missing inference results"
    inf_elapsed = time.time() - t_inf_start

    # Merge selection + inference data
    from skillopt.moar.tokenizer import count_tokens as _count_tokens

    api_failures = 0
    per_item = []
    for i in range(n_items):
        d = dict(batch_results[i])
        sd = sel_data[i]
        sel_indices = sd["sel"]
        # Real token count for selected rules
        sel_text = ""
        if sel_indices:
            sel_texts = [rules[idx] for idx in sel_indices if idx < len(rules)]
            sel_text = "\n\n".join(sel_texts)
        sel_tokens = _count_tokens(sel_text) if sel_text else 0
        d.update({
            "n_rules": len(sd["sel"]),
            "selected_indices": sd["sel"],
            "sel_chars": sd["sel_chars"],
            "selected_tokens": sel_tokens,
            "budget_violated": sel_tokens > budget,
            "input_chars": sd["input_chars"],
            "sel_latency_ms": sd["sel_ms"],
            "inference_ms": batch_results[i]["inference_ms"],
        })
        if d.get("status") == "api_error":
            api_failures += 1
        per_item.append(d)

    n_api_failures = api_failures
    api_error_rate = n_api_failures / n_items if n_items > 0 else 0.0
    valid_items = [r for r in per_item if r.get("status") != "api_error" and r.get("hard") is not None]
    n_valid = len(valid_items)
    acc = float(np.mean([r["hard"] for r in per_item if r.get("hard") is not None]))
    acc_valid = float(np.mean([r["hard"] for r in valid_items])) if valid_items else 0.0
    avg_r = float(np.mean([r["n_rules"] for r in per_item]))
    total_elapsed = time.time() - t0
    avg_sel_ms = float(np.mean([sd["sel_ms"] for sd in sel_data]))
    sel_ms_arr = np.array([sd["sel_ms"] for sd in sel_data])
    print(f"\n{method.upper()} {n_items} items: acc={acc:.4f}  avg_rules={avg_r:.1f}")
    if n_api_failures > 0:
        print(f"  API errors: {n_api_failures}/{n_items} ({api_error_rate*100:.1f}%)")
        if n_valid > 0:
            print(f"  Accuracy (valid only): {acc_valid:.4f} ({n_valid} samples)")
        if api_error_rate > 0.01:
            raise RuntimeError(
                f"API error rate {api_error_rate*100:.1f}% exceeds 1% threshold; experiment invalid."
            )
    print(f"  Selection: {avg_sel_ms:.1f}ms/q | Inference: {inf_elapsed:.0f}s total")
    return acc, avg_r, per_item, {
        "avg_sel_ms": avg_sel_ms,
        "sel_ms_median": float(np.median(sel_ms_arr)),
        "sel_ms_p95": float(np.percentile(sel_ms_arr, 95)),
        "sel_ms_p99": float(np.percentile(sel_ms_arr, 99)),
        "sel_ms_max": float(np.max(sel_ms_arr)),
        "api_failures": api_failures,
        **extra,
    }


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", required=True,
                   choices=["bm25","greedy-cold","greedy-util"])
    p.add_argument("--skill", default="outputs/searchqa_rag/best_skill.md")
    p.add_argument("--target-model", type=str, default="qwen3.6-flash")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--weights", default="0.4,0.3,0.2,0.1")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--utility-file", type=str, default="",
                   help="Required for greedy-util: path to frozen moar_utility.json")
    p.add_argument("--out", default="")
    return p.parse_args()


def main():
    args = parse_args()

    set_optimizer_backend("openai_compatible")
    set_optimizer_deployment("deepseek-v4-flash")
    _configure_target(args.target_model)

    skill_path = args.skill
    if not os.path.isabs(skill_path):
        skill_path = os.path.join(_PROJECT_ROOT, skill_path)
    with open(os.path.abspath(skill_path), encoding="utf-8") as f:
        skill = f.read()

    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    with open(os.path.join(data_dir, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    if args.limit > 0:
        items = items[:args.limit]
    print(f"Skill: {os.path.basename(skill_path)} | method={args.method}")
    print(f"Model: {args.target_model} | items={len(items)} | workers={args.workers}")

    import subprocess
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, cwd=_PROJECT_ROOT).strip()

    acc, avg_r, per_item, extra = infer(
        args.method, skill, items, args.top_k, args.budget,
        args.weights, args.workers,
        utility_file=args.utility_file,
    )

    # File hashes
    with open(skill_path, "rb") as f:
        skill_sha256 = hashlib.sha256(f.read()).hexdigest()
    items_path = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test", "items.json")
    dataset_sha256 = ""
    if os.path.exists(items_path):
        with open(items_path, "rb") as f:
            dataset_sha256 = hashlib.sha256(f.read()).hexdigest()

    out = args.out or os.path.join(
        _PROJECT_ROOT, "outputs",
        f"infer_{args.method}_{args.target_model}_n{len(items)}.json",
    )
    summary = {
        "method": args.method, "target_model": args.target_model,
        "n": len(items), "acc": acc, "avg_rules": avg_r,
        "commit": commit,
        "skill_sha256": skill_sha256,
        "dataset_sha256": dataset_sha256,
        "budget": args.budget, "top_k": args.top_k,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **extra,
        "per_question": per_item,
    }
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
