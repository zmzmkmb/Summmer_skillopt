#!/usr/bin/env python3
"""qwen3.6-flash Anthropic endpoint — 完整 single-rep（6方法 × 200题）. 用法: python scripts/run_targetL_full.py --seed 42"""
import os, sys, json, time, argparse, hashlib, numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

# ── Load .env ──
with open(os.path.join(PROJECT, ".env"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        if line.startswith("export "): line = line[7:]
        key, _, val = line.partition("=")
        key = key.strip(); val = val.strip().strip('"').strip("'")
        if key and val and key not in os.environ: os.environ[key] = val

# ── Configure Anthropic ──
from skillopt.model.anthropic_compatible_backend import (
    chat_target, configure_anthropic_compatible,
)
import skillopt.model as _model
_model.chat_target = chat_target
configure_anthropic_compatible(
    target_base_url="https://dashscope.aliyuncs.com/apps/anthropic",
    target_api_key=os.environ.get("TARGET_OPENAI_COMPATIBLE_API_KEY", ""),
    target_model="qwen3.6-flash",
)

from skillopt.envs.searchqa.rollout import _build_system, _build_user
from skillopt.envs.searchqa.evaluator import evaluate as _ev
from skillopt.rag_rule_selector import RuleMemory
from skillopt.moar.tokenizer import count_tokens

# ── Load data ──
with open(os.path.join(PROJECT, "outputs", "searchqa_rag", "best_skill.md"), encoding="utf-8") as f:
    skill_content = f.read()
all_items = json.load(open(os.path.join(PROJECT, "data", "searchqa_split", "test", "items.json"), encoding="utf-8"))
items = all_items[:200]
questions = [it["question"] for it in items]

# ── Token costs ──
_rm_tmp = RuleMemory(skill_content, method="tfidf")
rule_full_texts = [r.full_text for r in _rm_tmp.dynamic_rules]
rule_token_costs = np.array([count_tokens(t) for t in rule_full_texts])

# ── Args ──
p = argparse.ArgumentParser()
p.add_argument("--seed", type=int, required=True)
p.add_argument("--workers", type=int, default=4)
args = p.parse_args()
SEED = args.seed
MODEL = "qwen3.6-flash"
OUT = os.path.join(PROJECT, "outputs")
TOP_K = 5; BUDGET = 2000

print(f"Seed={SEED} items={len(items)} workers={args.workers}", flush=True)

# ── Utility for Greedy-Utility ──
util_path = os.path.join(OUT, "frozen", "moar_utility.json")
from skillopt.moar.tracker import UtilityTracker
ut = UtilityTracker(persistence_path=util_path)
ut.register_rules(rule_full_texts)
frozen_utils = ut.compute_utilities("precision")
with open(util_path, "rb") as f:
    util_sha256 = hashlib.sha256(f.read()).hexdigest()

# ── Commit ──
import subprocess
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=PROJECT).strip()

# ── Rule selection functions ──
from sklearn.metrics.pairwise import cosine_similarity
rv = _rm_tmp._rule_matrix
if hasattr(rv, 'toarray'): rv = rv.toarray()
rv_mat = np.asarray(rv)
sims_mat = cosine_similarity(rv_mat); np.fill_diagonal(sims_mat, 0.0)

def select_bm25(query, top_k, budget):
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi([t.lower().split() for t in rule_full_texts])
    scores = bm25.get_scores(query.lower().split())
    order = np.argsort(-scores)
    sel, used = [], 0
    for idx in order:
        if len(sel) >= top_k: break
        c = rule_token_costs[idx]
        if used + c > budget: continue
        sel.append(int(idx)); used += c
    return sel

def select_greedy_cold(query, top_k, budget):
    qv = _rm_tmp._vectorizer.transform([query])
    rel = cosine_similarity(qv, rv_mat).ravel()
    selected, remaining, used = [], list(range(len(rel))), 0
    w = (0.4, 0.3, 0.2, 0.1)
    for _ in range(top_k):
        best, best_i = -1e9, -1
        for j in remaining:
            c = rule_token_costs[j]
            if used + c > budget: continue
            s = w[0]*rel[j] - w[2]*(c/budget)
            if selected: s -= w[3]*np.mean([sims_mat[j, s] for s in selected])
            if s > best: best, best_i = s, j
        if best_i < 0: break
        c = rule_token_costs[best_i]
        if used + c > budget: break
        selected.append(best_i); used += c; remaining.remove(best_i)
    return selected

def select_greedy_util(query, top_k, budget):
    qv = _rm_tmp._vectorizer.transform([query])
    rel = cosine_similarity(qv, rv_mat).ravel()
    selected, remaining, used = [], list(range(len(rel))), 0
    w = (0.4, 0.3, 0.2, 0.1)
    for _ in range(top_k):
        best, best_i = -1e9, -1
        for j in remaining:
            c = rule_token_costs[j]
            if used + c > budget: continue
            s = w[0]*rel[j] + w[1]*frozen_utils[j] - w[2]*(c/budget)
            if selected: s -= w[3]*np.mean([sims_mat[j, s] for s in selected])
            if s > best: best, best_i = s, j
        if best_i < 0: break
        c = rule_token_costs[best_i]
        if used + c > budget: break
        selected.append(best_i); used += c; remaining.remove(best_i)
    return selected

# ── Inference helper ──
def _infer_one(idx, system, user, it):
    try:
        resp, _ = chat_target(system, user, max_completion_tokens=512, retries=2, stage="eval", timeout=60)
    except Exception:
        resp = ""
    ev = _ev(resp, it.get("answers", []))
    return idx, int(ev["em"]), ev["predicted_answer"], resp

def run_method(name, build_prompts_fn):
    """Run one method: build prompts -> parallel inference -> save."""
    print(f"\n{'='*50}\n  {name}\n{'='*50}", flush=True)

    t_build = time.time()
    prompts_data = build_prompts_fn()
    build_time = time.time() - t_build
    print(f"  Build: {build_time:.1f}s ({len(prompts_data)} queries)", flush=True)

    correct = 0; total = 0; empty = 0
    per_item = [None] * 200

    t_inf = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_infer_one, i, sp, up, items[i]): i
                for i, (sp, up, _, _) in enumerate(prompts_data)}
        for fut in as_completed(futs):
            i, hard, pred, resp = fut.result()
            _, _, n_rules, sel_tokens = prompts_data[i]
            per_item[i] = {
                "sample_id": str(items[i]["id"]),
                "hard": hard, "predicted": pred,
                "gold": items[i].get("answers", []),
                "selected_indices": [], "n_rules": n_rules,
                "selected_tokens": sel_tokens,
                "budget_violated": sel_tokens > BUDGET,
            }
            total += 1
            if hard: correct += 1
            if not resp: empty += 1
            if total % 50 == 0:
                print(f"  [{total}] acc={correct/total:.4f}", flush=True)

    inf_time = time.time() - t_inf
    acc = correct / total
    print(f"  DONE: acc={acc:.4f} inf={inf_time:.0f}s empty={empty}", flush=True)
    return per_item, acc, inf_time, empty

# ── Build prompt factories ──
common_rm = dict(top_k=TOP_K, token_budget=BUDGET)

def build_core_only():
    rm = RuleMemory(skill_content, method="core_only", **common_rm)
    results = []
    for qi, q in enumerate(questions):
        core = rm.core_rules_text
        results.append((_build_system(core), _build_user(q, items[qi].get("context", "")), 0, 0))
    return results

def build_tfidf():
    rm = RuleMemory(skill_content, method="tfidf", **common_rm)
    results = []
    for qi, q in enumerate(questions):
        dynamic = rm.retrieve(q)
        core = rm.core_rules_text
        text = core + "\n\n" + dynamic if dynamic else core
        sel_idx = rm._last_selections.get(q, [])
        n_rules = len(sel_idx)
        sel_tokens = sum(rule_token_costs[i] for i in sel_idx if i < len(rule_token_costs))
        results.append((_build_system(text), _build_user(q, items[qi].get("context", "")), n_rules, int(sel_tokens)))
    return results

def build_moar():
    rm = RuleMemory(skill_content, method="moar", moar_pop_size=30, moar_generations=15,
                    moar_frozen=True, moar_base_seed=SEED, **common_rm)
    results = []
    for qi, q in enumerate(questions):
        dynamic = rm.retrieve(q)
        core = rm.core_rules_text
        text = core + "\n\n" + dynamic if dynamic else core
        sel_idx = rm._last_selections.get(q, [])
        n_rules = len(sel_idx)
        sel_tokens = sum(rule_token_costs[i] for i in sel_idx if i < len(rule_token_costs))
        results.append((_build_system(text), _build_user(q, items[qi].get("context", "")), n_rules, int(sel_tokens)))
    return results

def build_baseline(name, select_fn):
    results = []
    for qi, q in enumerate(questions):
        sel_idx = select_fn(q, TOP_K, BUDGET)
        dynamic_text = "\n\n".join(rule_full_texts[i] for i in sorted(sel_idx, key=lambda i: i))
        core = _rm_tmp.core_rules_text
        text = core + "\n\n" + dynamic_text if dynamic_text else core
        n_rules = len(sel_idx)
        sel_tokens = sum(rule_token_costs[i] for i in sel_idx if i < len(rule_token_costs))
        results.append((_build_system(text), _build_user(q, items[qi].get("context", "")), n_rules, int(sel_tokens)))
    return results

# ── Run ──
all_results = {}
all_per_item = {}

for label, fn in [
    ("Core Only", build_core_only),
    ("TF-IDF Top-5", build_tfidf),
    ("MOAR", build_moar),
    ("BM25", lambda: build_baseline("BM25", select_bm25)),
    ("Greedy-Cold", lambda: build_baseline("Greedy-Cold", select_greedy_cold)),
    ("Greedy-Utility", lambda: build_baseline("Greedy-Utility", select_greedy_util)),
]:
    per, acc, inf_t, empty = run_method(label, fn)
    all_per_item[label] = per
    n_r = np.mean([p["n_rules"] for p in per])
    n_t = np.mean([p["selected_tokens"] for p in per])
    bv = sum(1 for p in per if p["budget_violated"])
    all_results[label] = {
        "accuracy": acc, "avg_rules": float(n_r),
        "avg_selected_tokens": float(n_t),
        "infer_time_s": inf_t, "n_items": 200,
        "api_failures": empty, "budget_violations": bv,
        "per_item": per,
    }
    print(f"  {label}: acc={acc:.4f} rules={n_r:.1f} tokens={n_t:.0f} viol={bv}", flush=True)

# ── Save ──
def _serial(obj):
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (np.floating,)): return float(obj)
    if isinstance(obj, (np.bool_,)): return bool(obj)
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, dict): return {k: _serial(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [_serial(x) for x in obj]
    return obj

with open(os.path.join(PROJECT, "outputs", "searchqa_rag", "best_skill.md"), "rb") as f:
    skill_sha256 = hashlib.sha256(f.read()).hexdigest()

summary = {
    "target_model": MODEL, "commit": commit,
    "split": "valid_unseen", "limit": 200,
    "top_k": TOP_K, "budget": BUDGET, "seed": SEED,
    "skill_sha256": skill_sha256,
    "utility_sha256": util_sha256,
    "results": all_results,
}

out_path = os.path.join(OUT, f"jos_formal_targetL_rep{SEED}.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(_serial(summary), f, ensure_ascii=False, indent=2)

print(f"\nSaved: {out_path}")
for name, r in all_results.items():
    print(f"  {name}: acc={r['accuracy']:.4f} rules={r['avg_rules']:.1f} tok={r['avg_selected_tokens']:.0f}")
