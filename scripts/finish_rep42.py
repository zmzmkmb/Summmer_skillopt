#!/usr/bin/env python3
"""Continuation: rep42 baselines only (Core Only, TF-IDF, MOAR already done)."""
import os, sys, json, time, hashlib, numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

with open(os.path.join(PROJECT, ".env"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        if line.startswith("export "): line = line[7:]
        key, _, val = line.partition("=")
        key = key.strip(); val = val.strip().strip('"').strip("'")
        if key and val and key not in os.environ: os.environ[key] = val

from skillopt.model.anthropic_compatible_backend import chat_target, configure_anthropic_compatible
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
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
from skillopt.moar.tracker import UtilityTracker

SEED = 42
OUT = os.path.join(PROJECT, "outputs")
BUDGET = 2000
TOP_K = 5

with open(os.path.join(PROJECT, "outputs", "searchqa_rag", "best_skill.md"), encoding="utf-8") as f:
    skill_content = f.read()
items = json.load(open(os.path.join(PROJECT, "data", "searchqa_split", "test", "items.json"), encoding="utf-8"))[:200]

_rm_tmp = RuleMemory(skill_content, method="tfidf")
rule_full_texts = [r.full_text for r in _rm_tmp.dynamic_rules]
rule_token_costs = np.array([count_tokens(t) for t in rule_full_texts])
rv_mat = np.asarray(_rm_tmp._rule_matrix.toarray() if hasattr(_rm_tmp._rule_matrix, 'toarray') else _rm_tmp._rule_matrix)
sims_mat = cosine_similarity(rv_mat); np.fill_diagonal(sims_mat, 0.0)

# Utility
util_path = os.path.join(OUT, "frozen", "moar_utility.json")
ut = UtilityTracker(persistence_path=util_path)
ut.register_rules(rule_full_texts)
frozen_utils = ut.compute_utilities("precision")

core_text = _rm_tmp.core_rules_text
bm25 = BM25Okapi([t.lower().split() for t in rule_full_texts])

def _infer_one(idx, system, user, it):
    try:
        resp, _ = chat_target(system, user, max_completion_tokens=512, retries=2, stage="eval", timeout=60)
    except Exception:
        resp = ""
    ev = _ev(resp, it.get("answers", []))
    return idx, int(ev["em"]), resp

def run_method(name, prompts):
    print(f"\n{'='*50}\n  {name}\n{'='*50}", flush=True)
    correct = 0; total = 0; empty = 0
    per_item = [None] * 200
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_infer_one, i, sp, up, items[i]): i for i, (sp, up, nr, st) in enumerate(prompts)}
        for fut in as_completed(futs):
            i, hard, resp = fut.result()
            _, _, n_rules, sel_tokens = prompts[i]
            per_item[i] = {"sample_id": str(items[i]["id"]), "hard": hard,
                           "predicted": resp, "gold": items[i].get("answers", []),
                           "n_rules": n_rules, "selected_tokens": sel_tokens,
                           "budget_violated": sel_tokens > BUDGET}
            total += 1
            if hard: correct += 1
            if not resp: empty += 1
            if total % 50 == 0:
                print(f"  [{total}] acc={correct/total:.4f}", flush=True)
    acc = correct / total
    print(f"  DONE: acc={acc:.4f} inf={time.time()-t0:.0f}s empty={empty}", flush=True)
    return per_item, acc, empty

def build_prompts(select_fn):
    results = []
    for qi, q in enumerate([it["question"] for it in items]):
        sel_idx = select_fn(q)
        dyn = "\n\n".join(rule_full_texts[i] for i in sorted(sel_idx, key=lambda x: x))
        text = core_text + "\n\n" + dyn if dyn else core_text
        nr = len(sel_idx)
        st = int(sum(rule_token_costs[i] for i in sel_idx if i < len(rule_token_costs)))
        results.append((_build_system(text), _build_user(q, items[qi].get("context", "")), nr, st))
    return results

results = {}

def sel_bm25(q):
    scores = bm25.get_scores(q.lower().split())
    order = np.argsort(-scores)
    sel, used = [], 0
    for idx in order:
        if len(sel) >= TOP_K: break
        c = rule_token_costs[idx]
        if used + c > BUDGET: continue
        sel.append(int(idx)); used += c
    return sel

def sel_greedy_cold(q):
    qv = _rm_tmp._vectorizer.transform([q])
    rel = cosine_similarity(qv, rv_mat).ravel()
    w = (0.4, 0.3, 0.2, 0.1)
    sel, rem, used = [], list(range(len(rel))), 0
    for _ in range(TOP_K):
        best, bi = -1e9, -1
        for j in rem:
            c = rule_token_costs[j]
            if used + c > BUDGET: continue
            s = w[0]*rel[j] - w[2]*(c/BUDGET)
            if sel: s -= w[3]*np.mean([sims_mat[j, s] for s in sel])
            if s > best: best, bi = s, j
        if bi < 0: break
        c = rule_token_costs[bi]
        if used + c > BUDGET: break
        sel.append(bi); used += c; rem.remove(bi)
    return sel

def sel_greedy_util(q):
    qv = _rm_tmp._vectorizer.transform([q])
    rel = cosine_similarity(qv, rv_mat).ravel()
    w = (0.4, 0.3, 0.2, 0.1)
    sel, rem, used = [], list(range(len(rel))), 0
    for _ in range(TOP_K):
        best, bi = -1e9, -1
        for j in rem:
            c = rule_token_costs[j]
            if used + c > BUDGET: continue
            s = w[0]*rel[j] + w[1]*frozen_utils[j] - w[2]*(c/BUDGET)
            if sel: s -= w[3]*np.mean([sims_mat[j, s] for s in sel])
            if s > best: best, bi = s, j
        if bi < 0: break
        c = rule_token_costs[bi]
        if used + c > BUDGET: break
        sel.append(bi); used += c; rem.remove(bi)
    return sel

all_r = {}

for label, fn in [("BM25", sel_bm25), ("Greedy-Cold", sel_greedy_cold), ("Greedy-Utility", sel_greedy_util)]:
    prompts = build_prompts(fn)
    per, acc, empty = run_method(label, prompts)
    nr = np.mean([p["n_rules"] for p in per])
    st = np.mean([p["selected_tokens"] for p in per])
    bv = sum(1 for p in per if p["budget_violated"])
    all_r[label] = {"accuracy": acc, "avg_rules": float(nr), "avg_selected_tokens": float(st),
                     "n_items": 200, "api_failures": empty, "budget_violations": int(bv), "per_item": per}

def _serial(obj):
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (np.floating,)): return float(obj)
    if isinstance(obj, (np.bool_,)): return bool(obj)
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, dict): return {k: _serial(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [_serial(x) for x in obj]
    return obj

with open(os.path.join(OUT, "jos_rep42_baselines.json"), "w", encoding="utf-8") as f:
    json.dump(_serial(all_r), f, ensure_ascii=False, indent=2)
for lbl, r in all_r.items():
    print(f"{lbl}: acc={r['accuracy']:.4f} rules={r['avg_rules']:.1f} tok={r['avg_selected_tokens']:.0f} viol={r['budget_violations']}")
print("Done.")
