#!/usr/bin/env python3
"""从 validation 集生成冷冻 utility 文件,供 Greedy-Utility 基线使用.

用法:
    python scripts/build_utility.py --skill outputs/searchqa_rag/best_skill.md --limit 200

生成文件: outputs/frozen/moar_utility.json (用于 --utility-file)
"""
from __future__ import annotations
import argparse, json, os, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skillopt.envs.searchqa.evaluator import evaluate
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.model import (
    chat_target, configure_openai_compatible,
    set_target_backend, set_target_deployment,
)
from skillopt.rag_rule_selector import RuleMemory
from skillopt.moar.tracker import UtilityTracker


def _load_env(path: str | None = None):
    """加载 .env 文件中的环境变量."""
    import os as _os
    if path is None:
        path = _os.path.join(PROJECT_ROOT, ".env")
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
    """根据模型名配置正确的 API endpoint."""
    _load_env()
    if "3.6" in model_name or model_name.startswith("qwen3"):
        # MaaS token-plan
        configure_openai_compatible(
            target_base_url=os.environ.get(
                "TARGET_OPENAI_COMPATIBLE_BASE_URL",
                "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            ),
            target_api_key=os.environ.get("TARGET_OPENAI_COMPATIBLE_API_KEY", ""),
            target_model=model_name,
        )
    else:
        # DashScope
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


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", default="outputs/searchqa_rag/best_skill.md")
    p.add_argument("--target-model", default="qwen-flash")
    p.add_argument("--limit", type=int, default=0, help="0=all val items")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", default="outputs/frozen/moar_utility.json")
    return p.parse_args()


def main():
    args = parse_args()

    skill_path = args.skill
    if not os.path.isabs(skill_path):
        skill_path = os.path.join(PROJECT_ROOT, skill_path)
    skill_path = os.path.abspath(skill_path)
    with open(skill_path, encoding="utf-8") as f:
        skill_content = f.read()

    # Load validation items
    val_path = os.path.join(PROJECT_ROOT, "data", "searchqa_split", "val", "items.json")
    with open(val_path, encoding="utf-8") as f:
        val_items = json.load(f)
    if args.limit > 0:
        val_items = val_items[:args.limit]
    print(f"Validation items: {len(val_items)}")

    # Build MOAR memory (UNfrozen — will record utilities)
    print("Building MOAR memory (unfrozen, seed={})...".format(args.seed))
    rm = RuleMemory(
        skill_content,
        method="moar",
        top_k=args.top_k,
        token_budget=args.budget,
        moar_pop_size=30,
        moar_generations=15,
        moar_frozen=False,
        moar_base_seed=args.seed,
        moar_utility_path=os.path.join(PROJECT_ROOT, args.out),
    )

    # Configure target model
    _configure_target(args.target_model)
    print(f"Target model: {args.target_model}")

    correct = 0
    total = 0

    for i, item in enumerate(val_items):
        q = item["question"]
        ctx = item.get("context", "")

        # MOAR selection
        dynamic = rm.retrieve(q, top_k=args.top_k, token_budget=args.budget)
        core = rm.core_rules_text
        full_skill = core + "\n\n" + dynamic if dynamic else core

        # Inference
        system = _build_system(full_skill)
        user = _build_user(q, ctx)
        try:
            resp, _ = chat_target(system, user, max_completion_tokens=512,
                                  retries=1, stage="utility_build", timeout=60)
        except Exception:
            resp = ""

        ev = evaluate(resp, item.get("answers", []))
        is_correct = int(ev["em"]) == 1
        total += 1
        if is_correct:
            correct += 1

        # Feed back to utility tracker
        rm.update_utilities([{
            "question": q,
            "hard": int(is_correct),
        }])

        if (i + 1) % 20 == 0:
            acc = correct / total
            print(f"  [{i+1}/{len(val_items)}] acc={acc:.4f} "
                  f"n_rules_avg={rm.n_dynamic}", flush=True)

    final_acc = correct / total
    print(f"\nVal accuracy: {correct}/{total} = {final_acc:.4f}")

    # Final save
    rm._tracker.save()
    print(f"Utility file saved to: {args.out}")
    print("Done. Use with: --utility-file outputs/frozen/moar_utility.json")


if __name__ == "__main__":
    main()
