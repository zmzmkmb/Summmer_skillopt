#!/usr/bin/env python3
"""Smoke test + controlled comparison: MOAR vs TF-IDF vs Core Only on SearchQA.

Uses an already-trained skill and runs inference-only (no training),
comparing three retrieval methods under identical conditions.

Usage:
    python scripts/moar_searchqa_eval.py \
        --skill outputs/searchqa_rag/best_skill.md \
        --limit 200 --split valid_unseen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import (
    chat_target,
    configure_openai_compatible,
    set_optimizer_backend,
    set_optimizer_deployment,
    set_target_backend,
    set_target_deployment,
)
from skillopt.model.common import default_model_for_backend
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
        # Anthropic-compatible endpoint (DashScope Anthropic)
        from skillopt.model.anthropic_compatible_backend import (
            chat_target as _ant_ct,
            configure_anthropic_compatible,
        )
        import skillopt.model as _model
        _model.chat_target = _ant_ct  # monkey-patch for downstream calls
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


# ── Helpers ──────────────────────────────────────────────────────────────

def load_test_items(split: str, limit: int = 0) -> list[dict]:
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split")
    sub = "test" if split == "valid_unseen" else "val"
    path = os.path.join(data_dir, sub, "items.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    if limit > 0:
        items = items[:limit]
    return items


def infer_one(item: dict, system: str, user: str) -> dict:
    t0 = time.time()
    api_error = None
    try:
        import skillopt.model as _m
        resp, _ = _m.chat_target(
            system, user, max_completion_tokens=512,
            retries=2, stage="moar_eval", timeout=60,
        )
    except Exception as exc:
        resp = ""
        api_error = {"type": type(exc).__name__, "message": str(exc)[:500]}
    inf_ms = (time.time() - t0) * 1000
    ev = evaluate(resp, item.get("answers", []))
    result = {
        "sample_id": str(item["id"]),
        "hard": int(ev["em"]),
        "predicted": ev["predicted_answer"],
        "gold": item.get("answers", []),
        "response_len": len(resp),
        "inference_ms": inf_ms,
    }
    if api_error is not None:
        result["status"] = "api_error"
        result["error_type"] = api_error["type"]
        result["error"] = api_error["message"]
        result["hard"] = None  # API 失败不计入有效准确率
    else:
        result["status"] = "ok"
    return result


def build_skill_text(rm, query: str) -> tuple[str, int, int, list[int]]:
    """Build active skill for query. Returns (text, n_dynamic, total_chars, selected_indices)."""
    core = rm.core_rules_text
    dynamic = rm.retrieve(query)
    if dynamic:
        text = core + "\n\n" + dynamic
    else:
        text = core
    sel_idx = list(rm._last_selections.get(query, []))
    n_dyn = len(sel_idx)
    return text, n_dyn, len(text), sel_idx


def count_rule_redundancy(rm, query: str) -> float:
    """Estimate redundancy among selected dynamic rules via pairwise TF-IDF sim."""
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    indices = list(rm._last_selections.get(query, []))
    if len(indices) <= 1:
        return 0.0

    rv = rm._parent._rule_matrix if hasattr(rm, '_parent') else rm._rule_matrix
    if rv is not None and rv.shape[0] > 0:
        sel_emb = rv[indices]
        if hasattr(sel_emb, 'toarray'):
            sel_emb = sel_emb.toarray()
        sims = cosine_similarity(sel_emb)
        np.fill_diagonal(sims, 0.0)
        n = len(indices)
        max_pairs = n * (n - 1) / 2.0
        return float(np.sum(sims) / 2.0 / max_pairs) if max_pairs > 0 else 0.0
    return 0.0


# ── Main ─────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", type=str, required=True,
                   help="Path to trained skill .md file")
    p.add_argument("--target-model", type=str, default="qwen3.6-flash",
                   help="Target model name (qwen3.6-flash, qwen-flash, etc.)")
    p.add_argument("--optimizer-model", type=str, default="deepseek-v4-flash",
                   help="Optimizer model name (deepseek-v4-flash, deepseek-v4-pro, etc.)")
    p.add_argument("--split", type=str, default="valid_unseen")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--moar-pop-size", type=int, default=50,
                   help="NSGA-II 种群大小 (smoke: 30, full: 50)")
    p.add_argument("--moar-generations", type=int, default=30,
                   help="NSGA-II 迭代代数 (smoke: 15, full: 30)")
    p.add_argument("--moar-mutation-p", type=float, default=0.10,
                   help="NSGA-II 变异概率")
    p.add_argument("--moar-crossover-p", type=float, default=0.90,
                   help="NSGA-II 交叉概率")
    p.add_argument("--out", type=str, default="")
    return p.parse_args()


def main():
    args = parse_args()

    # ── Configure model backends (CLI-overridable) ────────────────────
    set_optimizer_backend("openai_compatible")
    set_optimizer_deployment(args.optimizer_model or "deepseek-v4-flash")
    _configure_target(args.target_model or "qwen-flash")

    # Load skill
    skill_path = args.skill
    if not os.path.isabs(skill_path):
        skill_path = os.path.join(_PROJECT_ROOT, skill_path)
    with open(os.path.abspath(skill_path), encoding="utf-8") as f:
        skill_content = f.read()

    # Load test items
    items = load_test_items(args.split, args.limit)
    questions = [it["question"] for it in items]
    print(f"Loaded {len(items)} test items from {args.split}")
    print(f"Skill: {os.path.basename(args.skill)} ({len(skill_content)} chars)")
    print(f"Config: top_k={args.top_k} budget={args.budget} workers={args.workers}")
    print(f"MOAR: pop={args.moar_pop_size} gen={args.moar_generations} "
          f"mut_p={args.moar_mutation_p} cross_p={args.moar_crossover_p}")
    print(f"{'='*60}")

    # ── Build rule memories (once) ──────────────────────────────────────
    methods = {}
    # Shared parent args
    common = dict(top_k=args.top_k, token_budget=args.budget)

    print("\nBuilding RuleMemory instances...")
    t0 = time.time()

    methods["Core Only"] = RuleMemory(skill_content, method="core_only", **common)
    methods["TF-IDF Top-5"] = RuleMemory(skill_content, method="tfidf", **common)
    methods["MOAR"] = RuleMemory(
        skill_content, method="moar",
        moar_pop_size=args.moar_pop_size,
        moar_generations=args.moar_generations,
        moar_crossover_p=args.moar_crossover_p,
        moar_mutation_p=args.moar_mutation_p,
        moar_utility_method="precision",
        moar_base_seed=args.seed,
        moar_frozen=True,
        **common,
    )

    for name, rm in methods.items():
        print(f"  {name}: core={rm.n_core} dynamic={rm.n_dynamic} total={rm.n_total}")

    print(f"  Init time: {time.time() - t0:.1f}s")

    # ── Run inference ───────────────────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, list[dict]] = {}

    for method_name, rm in methods.items():
        print(f"\n{'='*60}")
        print(f"  {method_name}")
        print(f"{'='*60}")

        system_prompts: list[str] = []
        user_prompts: list[str] = []
        build_times: list[float] = []
        n_rules_list: list[int] = []
        char_counts: list[int] = []
        selected_indices_list: list[list[int]] = []

        t_build_start = time.time()
        for q_idx, q in enumerate(questions):
            t_q0 = time.time()
            text, n_dyn, n_char, sel_idx = build_skill_text(rm, q)
            build_times.append(time.time() - t_q0)
            system_prompts.append(_build_system(text))
            user_prompts.append(_build_user(q, items[q_idx].get("context", "")))
            n_rules_list.append(n_dyn)
            char_counts.append(n_char)
            selected_indices_list.append(sel_idx)

        avg_build = np.mean(build_times)
        avg_rules = np.mean(n_rules_list)
        avg_chars = np.mean(char_counts)
        print(f"  Build: {len(questions)} queries, avg {avg_build*1000:.1f}ms/query")
        print(f"  Rules activated: avg {avg_rules:.1f}, prompt chars avg {avg_chars:.0f}")

        # Inference — preserve original ordering via index mapping
        t_infer_start = time.time()
        n_items = len(items)
        batch_results: list[dict | None] = [None] * n_items
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(infer_one, item, sp, up): i
                    for i, (item, sp, up) in enumerate(zip(items, system_prompts, user_prompts))}
            for fut in as_completed(futs):
                original_idx = futs[fut]
                batch_results[original_idx] = fut.result()

        assert all(r is not None for r in batch_results), \
            f"{sum(1 for r in batch_results if r is None)} of {n_items} results missing"
        assert [str(r["sample_id"]) for r in batch_results] == \
               [str(item["id"]) for item in items], "sample_ids misaligned — ordering bug"

        infer_time = time.time() - t_infer_start
        # 区分 API 失败和有效样本
        n_api_failures = sum(1 for r in batch_results if r.get("status") == "api_error")
        api_error_rate = n_api_failures / n_items if n_items > 0 else 0.0
        valid_items = [r for r in batch_results if r.get("status") != "api_error" and r.get("hard") is not None]
        n_valid = len(valid_items)
        hard_all = np.mean([r["hard"] for r in batch_results if r.get("hard") is not None])
        hard_valid = np.mean([r["hard"] for r in valid_items]) if valid_items else 0.0
        print(f"  Inference: {n_items} items, {infer_time:.0f}s ({infer_time/n_items:.1f}s/item)")
        print(f"  API errors: {n_api_failures}/{n_items} ({api_error_rate*100:.1f}%)")
        if api_error_rate > 0.01:
            raise RuntimeError(
                f"API 错误率 {api_error_rate*100:.1f}% 超过 1% 阈值，实验无效。"
                f"请检查网络、API key 和模型可用性。"
            )
        if n_valid > 0:
            print(f"  Accuracy (valid only): {hard_valid:.4f} ({n_valid} samples)")
        print(f"  Accuracy (all samples): {hard_all:.4f} ({n_items} samples)")

        # Enrich per-item dicts with correctly-matched rule selection data
        from skillopt.moar.tokenizer import count_tokens as _count_tokens

        api_failures = 0
        per_item = []
        for i in range(n_items):
            d = dict(batch_results[i])
            d["selected_indices"] = selected_indices_list[i] if i < len(selected_indices_list) else []
            d["n_rules"] = n_rules_list[i] if i < len(n_rules_list) else 0
            d["prompt_chars"] = char_counts[i] if i < len(char_counts) else 0
            d["build_ms"] = build_times[i] * 1000 if i < len(build_times) else 0
            # Real token count for selected rules (unified: tokenizer if available, else chars)
            sel_indices = d["selected_indices"]
            if sel_indices and hasattr(rm, 'dynamic_rules'):
                dyn_rules = rm.dynamic_rules
                sel_text = "\n\n".join(dyn_rules[idx].full_text for idx in sel_indices if idx < len(dyn_rules))
                if hasattr(rm, '_token_counter') and rm._token_counter is not None:
                    d["selected_tokens"] = rm._token_counter.count(sel_text) if sel_text else 0
                else:
                    d["selected_tokens"] = _count_tokens(sel_text) if sel_text else 0
            else:
                d["selected_tokens"] = 0
            d["budget_violated"] = d["selected_tokens"] > args.budget
            if d.get("status") == "api_error":
                api_failures += 1
            per_item.append(d)

        build_ms_arr = np.array([d["build_ms"] for d in per_item])
        results[method_name] = {
            "accuracy": float(hard_all),
            "accuracy_valid_only": float(hard_valid),
            "n_valid": n_valid,
            "n_api_failures": n_api_failures,
            "api_error_rate": float(api_error_rate),
            "avg_rules": float(avg_rules),
            "avg_chars": float(avg_chars),
            "avg_build_ms": float(avg_build * 1000),
            "build_ms_median": float(np.median(build_ms_arr)),
            "build_ms_p95": float(np.percentile(build_ms_arr, 95)),
            "build_ms_p99": float(np.percentile(build_ms_arr, 99)),
            "build_ms_max": float(np.max(build_ms_arr)),
            "infer_time_s": float(infer_time),
            "n_items": n_items,
            "api_failures": api_failures,
            "per_item": per_item,
        }

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Method':<20s} {'Acc':>8s} {'Rules':>8s} {'Chars':>8s} {'Build':>8s} {'Infer':>8s}")
    print(f"  {'-'*60}")
    for name, r in results.items():
        print(f"  {name:<20s} {r['accuracy']:8.4f} {r['avg_rules']:8.1f} "
              f"{r['avg_chars']:8.0f} {r['avg_build_ms']:7.0f}ms {r['infer_time_s']:7.0f}s")

    # Delta vs TF-IDF
    tfidf_acc = results["TF-IDF Top-5"]["accuracy"]
    for name in ["Core Only", "MOAR"]:
        delta = results[name]["accuracy"] - tfidf_acc
        print(f"  {name} vs TF-IDF: Δacc={delta:+.4f}")

    # Save
    out_path = args.out or os.path.join(
        _PROJECT_ROOT, "outputs",
        f"moar_comparison_{args.split}_n{args.limit}_{int(time.time())}.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    import subprocess
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, cwd=_PROJECT_ROOT).strip()

    # File hashes for reproducibility
    with open(os.path.abspath(skill_path), "rb") as f:
        skill_sha256 = hashlib.sha256(f.read()).hexdigest()
    items_path = os.path.join(
        _PROJECT_ROOT, "data", "searchqa_split",
        "test" if args.split == "valid_unseen" else "val", "items.json")
    dataset_sha256 = ""
    if os.path.exists(items_path):
        with open(items_path, "rb") as f:
            dataset_sha256 = hashlib.sha256(f.read()).hexdigest()

    summary = {
        "skill": os.path.abspath(skill_path),
        "skill_sha256": skill_sha256,
        "target_model": args.target_model,
        "optimizer_model": args.optimizer_model,
        "commit": commit,
        "split": args.split,
        "limit": args.limit,
        "top_k": args.top_k,
        "budget": args.budget,
        "seed": args.seed,
        "moar_pop_size": args.moar_pop_size,
        "moar_generations": args.moar_generations,
        "moar_mutation_p": args.moar_mutation_p,
        "moar_crossover_p": args.moar_crossover_p,
        "dataset_sha256": dataset_sha256,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
    }
    def _serialize(obj):
        """递归转换 numpy 类型为 Python 原生类型."""
        import numpy as _np
        if isinstance(obj, (_np.integer,)):
            return int(obj)
        if isinstance(obj, (_np.floating,)):
            return float(obj)
        if isinstance(obj, _np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_serialize(x) for x in obj]
        return obj

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(_serialize(summary), f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
