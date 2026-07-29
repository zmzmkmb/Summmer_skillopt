#!/usr/bin/env python3
"""JoS sanity check: 2 targets × 4 methods × 200 queries × 3 seeds.

Verifies the four scenarios reviewer describes:
  Case 1: MOAR improves accuracy on both models (ideal)
  Case 2: MOAR saves tokens with similar accuracy (strong result)
  Case 3: New model near-ceiling → MOAR helps on harder tasks
  Case 4: MOAR worse on new model → utility model-dependency

Per-sample JSON output for statistical analysis.

Usage:
    python scripts/jos_sanity_check.py \
        --target-s qwen-flash \
        --target-l qwen3.6-flash \
        --limit 200 --seeds 42,43,44
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import (
    chat_target, set_optimizer_backend, set_optimizer_deployment,
    set_target_backend, set_target_deployment,
)
from skillopt.rag_rule_selector import RuleMemory


@dataclass
class SampleResult:
    sample_id: str
    target_model: str
    method: str
    seed: int
    selected_rule_indices: list[int] = field(default_factory=list)
    selected_rule_tokens: int = 0
    input_tokens_est: int = 0
    selection_latency_ms: float = 0.0
    inference_latency_ms: float = 0.0
    correct: bool = False
    predicted: str = ""
    gold: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "sample_id": self.sample_id, "target_model": self.target_model,
            "method": self.method, "seed": self.seed,
            "selected_rule_indices": self.selected_rule_indices,
            "selected_rule_tokens": self.selected_rule_tokens,
            "input_tokens_est": self.input_tokens_est,
            "selection_latency_ms": self.selection_latency_ms,
            "inference_latency_ms": self.inference_latency_ms,
            "correct": self.correct, "predicted": self.predicted,
            "gold": self.gold,
        }


def make_seed(base: int, sample_id: str) -> int:
    raw = f"{base}:{sample_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "little")


def load_items(limit: int) -> list[dict]:
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    with open(os.path.join(data_dir, "items.json"), encoding="utf-8") as f:
        items = json.load(f)
    return items[:limit] if limit > 0 else items


def infer_one(item, system, model_name):
    """Run one Q&A inference and return result."""
    user = _build_user(item["question"], item.get("context", ""))
    try:
        t0 = time.time()
        resp, _ = chat_target(system, user, max_completion_tokens=512,
                               retries=2, stage="sanity", timeout=60)
        elapsed = time.time() - t0
    except Exception:
        resp = ""; elapsed = 0
    ev = evaluate(resp, item.get("answers", []))
    return resp, elapsed, int(ev["em"]), ev["predicted_answer"]


def run_round(
    skill_content: str, items: list[dict], target_model: str,
    methods: list[str], seed_base: int, cfg: dict,
) -> list[SampleResult]:
    """Run one round with all methods on all items."""
    top_k = cfg["top_k"]; budget = cfg["budget"]
    results = []

    for method in methods:
        # Build RM once per method
        rm_kwargs = dict(skill_content=skill_content, top_k=top_k,
                         token_budget=budget, method=method)
        if method == "moar":
            rm_kwargs.update(moar_pop_size=30, moar_generations=15)

        rm = RuleMemory(**rm_kwargs)

        for item in items:
            sid = str(item["id"])

            # Selection
            t_sel0 = time.time()
            dynamic_text = rm.retrieve(item["question"], top_k=top_k,
                                        token_budget=budget)
            sel_time = (time.time() - t_sel0) * 1000

            # Get selected indices (for MOAR: from last_selections)
            selected_indices: list[int] = []
            if hasattr(rm, '_engine'):
                indices = rm._engine._last_selections.get(item["question"], [])
                selected_indices = list(indices)

            # Build system prompt
            core = rm.core_rules_text
            full = core + "\n\n" + dynamic_text if dynamic_text else core
            system = _build_system(full)

            # Inference
            resp, inf_time, correct, predicted = infer_one(item, system, target_model)

            # Estimate tokens (cl100k_base)
            try:
                from skillopt.moar.tokenizer import count_tokens
                input_tokens = count_tokens(system + "\n" + item["question"])
            except Exception:
                input_tokens = len(system) + len(item["question"])

            sel_tokens = len(dynamic_text)

            results.append(SampleResult(
                sample_id=sid, target_model=target_model,
                method=method, seed=seed_base,
                selected_rule_indices=selected_indices,
                selected_rule_tokens=sel_tokens,
                input_tokens_est=input_tokens,
                selection_latency_ms=sel_time,
                inference_latency_ms=inf_time * 1000,
                correct=bool(correct), predicted=predicted,
                gold=item.get("answers", []),
            ))

            # Progress
            if len(results) % 100 == 0:
                acc = np.mean([r.correct for r in results[-100:]])
                print(f"  [{len(results)}] acc={acc:.3f}", flush=True)

    return results


def summarize(results: list[SampleResult]):
    """Print summary table."""
    methods = sorted(set(r.method for r in results))
    targets = sorted(set(r.target_model for r in results))

    print(f"\n{'='*70}")
    print(f"  Sanity Check Summary (n={len(results)//len(methods)//len(targets)} each)")
    print(f"{'='*70}")
    print(f"  {'Method':<12s}", end="")
    for t in targets:
        print(f" | {t:>20s}", end="")
    print(f" | {'Δ':>8s}")
    print(f"  {'-'*12}", end="")
    for _ in targets:
        print(f" | {'-'*20}", end="")
    print(f" | {'-'*8}")

    for method in methods:
        print(f"  {method:<12s}", end="")
        accs = []
        for t in targets:
            subset = [r.correct for r in results
                      if r.method == method and r.target_model == t]
            acc = np.mean(subset) if subset else 0
            avg_tok = np.mean([r.input_tokens_est for r in results
                               if r.method == method and r.target_model == t])
            print(f" | acc={acc:.4f} tok={avg_tok:.0f}", end="")
            accs.append(acc)
        delta = accs[-1] - accs[0] if len(accs) >= 2 else 0
        print(f" | {delta:+.4f}")

    print()
    for method in methods:
        for t in targets:
            subset = [r for r in results if r.method == method and r.target_model == t]
            if subset:
                avg_sel = np.mean([r.selection_latency_ms for r in subset])
                avg_inf = np.mean([r.inference_latency_ms for r in subset])
                print(f"  {method}/{t}: sel={avg_sel:.1f}ms inf={avg_inf:.0f}ms")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target-s", default="qwen-flash", help="Target-S (old/small)")
    p.add_argument("--target-s-url", default="", help="Base URL for Target-S")
    p.add_argument("--target-l", default="qwen3.6-flash", help="Target-L (new/large)")
    p.add_argument("--target-l-url", default="", help="Base URL for Target-L")
    p.add_argument("--target-l-key", default="", help="API key for Target-L")
    p.add_argument("--skill", default="outputs/searchqa_rag/best_skill.md")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--seeds", type=str, default="42,43,44")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--methods", type=str, default="core_only,tfidf,moar")
    p.add_argument("--out", type=str, default="")
    return p.parse_args()


def main():
    args = parse_args()
    methods = [m.strip() for m in args.methods.split(",")]
    seeds = [int(s) for s in args.seeds.split(",")]

    with open(os.path.abspath(args.skill), encoding="utf-8") as f:
        skill_content = f.read()
    items = load_items(args.limit)
    print(f"Skill: {os.path.basename(args.skill)} ({len(skill_content)} chars)")
    print(f"Items: {len(items)} | Methods: {methods} | Seeds: {seeds}")

    all_results = []

    for seed_base in seeds:
        for model_name in [args.target_s, args.target_l]:
            print(f"\n{'='*60}")
            print(f"  Target={model_name} Seed={seed_base}")
            print(f"{'='*60}")

            # Configure target endpoint
            if model_name == args.target_s:
                # Old model: DashScope
                base = args.target_s_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
                key = os.environ.get("TARGET_S_OPENAI_COMPATIBLE_API_KEY",
                    os.environ.get("TARGET_OPENAI_COMPATIBLE_API_KEY", ""))
            else:
                # New model: MaaS
                base = args.target_l_url or "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
                key = args.target_l_key or os.environ.get("TARGET_OPENAI_COMPATIBLE_API_KEY", "")

            set_optimizer_backend("openai_compatible")
            set_target_backend("openai_compatible")
            set_optimizer_deployment("deepseek-v4-flash")
            set_target_deployment(model_name)

            # Override env if provided
            if key:
                import skillopt.model.openai_compatible_backend as _be
                # We can't easily override per-round, so use a simple approach:
                # train.py handles this via env vars — we set them before launch
                pass

            results = run_round(skill_content, items, model_name, methods,
                                seed_base, {"top_k": args.top_k,
                                            "budget": args.budget})
            all_results.extend(results)

    # Summarize
    if all_results:
        summarize(all_results)

    # Save per-sample
    out_path = args.out or os.path.join(
        _PROJECT_ROOT, "outputs",
        f"jos_sanity_n{args.limit}_m{len(methods)}_s{len(seeds)}.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in all_results], f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_path} ({len(all_results)} samples)")


if __name__ == "__main__":
    main()
