#!/usr/bin/env python3
"""qwen3.6-flash formal seed44 — Core Only + TF-IDF + MOAR."""
import os, sys, json, time, hashlib, numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

# ── Load .env ──
with open(os.path.join(PROJECT, ".env"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("#") or not line or "=" not in line: continue
        if line.startswith("export "): line = line[7:]
        key, _, val = line.partition("=")
        key = key.strip(); val = val.strip().strip('"').strip("'")
        if key and val and key not in os.environ: os.environ[key] = val

# ── Configure Anthropic backend ──
from skillopt.model.anthropic_compatible_backend import (
    chat_target as _ant_ct, configure_anthropic_compatible,
)
import skillopt.model as _model
_model.chat_target = _ant_ct
configure_anthropic_compatible(
    target_base_url="https://dashscope.aliyuncs.com/apps/anthropic",
    target_api_key=os.environ.get("TARGET_OPENAI_COMPATIBLE_API_KEY", ""),
    target_model="qwen3.6-flash",
)

# ── Load data ──
from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.envs.searchqa.evaluator import evaluate as _ev
from skillopt.rag_rule_selector import RuleMemory

with open(os.path.join(PROJECT, "outputs", "searchqa_rag", "best_skill.md"), encoding="utf-8") as f:
    skill_content = f.read()
items = json.load(open(os.path.join(PROJECT, "data", "searchqa_split", "test", "items.json"), encoding="utf-8"))
items = items[:200]
questions = [it["question"] for it in items]
print(f"Items: {len(items)}", flush=True)

# ── Build methods ──
common = dict(top_k=5, token_budget=2000)
methods = {}
print("Building RuleMemory...", flush=True)
t0 = time.time()
methods["Core Only"] = RuleMemory(skill_content, method="core_only", **common)
print("  Core Only done", flush=True)
methods["TF-IDF Top-5"] = RuleMemory(skill_content, method="tfidf", **common)
print("  TF-IDF done", flush=True)
methods["MOAR"] = RuleMemory(
    skill_content, method="moar",
    moar_pop_size=30, moar_generations=15,
    moar_utility_method="precision", moar_base_seed=44,
    moar_frozen=True, **common,
)
print(f"  MOAR done ({time.time()-t0:.1f}s init)", flush=True)

# ── Run ──
results = {}
import subprocess
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=PROJECT).strip()

for method_name, rm in methods.items():
    print(f"\n{method_name}...", flush=True)

    # Build prompts
    t_build = time.time()
    prompts = []
    for qi, q in enumerate(questions):
        dynamic = rm.retrieve(q)
        core = rm.core_rules_text
        text = core + "\n\n" + dynamic if dynamic else core
        prompts.append((_build_system(text), _build_user(q, items[qi].get("context", ""))))
    build_time = time.time() - t_build
    print(f"  Build: {build_time:.1f}s", flush=True)

    # Inference with 4 workers
    correct = 0
    total = 0
    empty = 0
    per_item = [None] * 200

    def _infer(idx, sys_p, usr_p, it):
        try:
            resp, _ = _ant_ct(sys_p, usr_p, max_completion_tokens=512, retries=2, stage="eval", timeout=60)
        except Exception:
            resp = ""
        ev = _ev(resp, it.get("answers", []))
        return idx, int(ev["em"]), ev["predicted_answer"], resp

    t_inf = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_infer, i, sp, up, items[i]): i
                for i, (sp, up) in enumerate(prompts)}
        for fut in as_completed(futs):
            i, hard, pred, resp = fut.result()
            per_item[i] = {"sample_id": str(items[i]["id"]), "hard": hard,
                           "predicted": pred, "gold": items[i].get("answers", [])}
            total += 1
            if hard: correct += 1
            if not resp: empty += 1
            if total % 50 == 0:
                print(f"  [{total}] acc={correct/total:.4f}", flush=True)

    inf_time = time.time() - t_inf
    acc = correct / total
    print(f"  DONE: acc={acc:.4f} inf_time={inf_time:.0f}s empty={empty}", flush=True)

    # Get selected indices
    sel_indices = [rm._last_selections.get(q, []) for q in questions]
    n_rules = [len(s) for s in sel_indices]
    results[method_name] = {
        "accuracy": acc, "avg_rules": float(np.mean(n_rules)),
        "avg_chars": 0, "avg_build_ms": 0,
        "infer_time_s": inf_time, "n_items": 200,
        "per_item": per_item,
    }

# ── Save ──
out_path = os.path.join(PROJECT, "outputs", "jos_formal_targetL_seed44.json")
summary = {"target_model": "qwen3.6-flash", "commit": commit,
           "split": "valid_unseen", "limit": 200, "top_k": 5,
           "budget": 2000, "seed": 44, "results": results}

def _serialize(obj):
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (np.floating,)): return float(obj)
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, dict): return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [_serialize(x) for x in obj]
    return obj

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(_serialize(summary), f, ensure_ascii=False, indent=2)

print(f"\nSaved: {out_path}")
for name, r in results.items():
    print(f"  {name}: acc={r['accuracy']:.4f} rules={r['avg_rules']:.1f}")
