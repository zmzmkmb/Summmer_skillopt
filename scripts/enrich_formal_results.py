#!/usr/bin/env python3
"""离线补算 enrichment — 从已有 formal JSON 中纠正 avg_rules/selected_tokens/budget_violated.

不打电话、不修改原文件。
"""
import hashlib, json, os, sys
import numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT, "outputs")

from skillopt.moar.tokenizer import count_tokens
from skillopt.rag_rule_selector import RuleMemory

# Load skill + build rule token costs once
with open(os.path.join(OUT, "searchqa_rag", "best_skill.md"), encoding="utf-8") as f:
    skill_content = f.read()
skill_sha256 = hashlib.sha256(skill_content.encode("utf-8")).hexdigest()

rm = RuleMemory(skill_content, method="tfidf")
rule_token_costs = np.array([count_tokens(r.full_text) for r in rm.dynamic_rules])

FILES = [
    "jos_formal_targetS_seed42.json",
    "jos_formal_targetS_seed43.json",
    "jos_formal_targetS_seed44.json",
    "jos_formal_targetL_seed42.json",
    "jos_formal_targetL_seed43.json",
    "jos_formal_targetL_seed44.json",
]

for fname in FILES:
    path = os.path.join(OUT, fname)
    if not os.path.exists(path):
        print(f"SKIP {fname} (missing)")
        continue

    with open(path, encoding="utf-8") as f:
        raw = f.read()
    source_sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    d = json.loads(raw)
    budget = d.get("budget", 2000)
    commit = d.get("commit", "")

    enriched = dict(d)
    enriched["source_result"] = fname
    enriched["source_sha256"] = source_sha256
    enriched["enrichment_skill_sha256"] = skill_sha256
    enriched["accuracy_recomputed"] = False

    for method_name, res in enriched["results"].items():
        per_item = res.get("per_item", [])
        corrected_rules = []
        corrected_tokens = []
        budget_violations = 0
        api_failures = 0

        for p in per_item:
            sel_idx = p.get("selected_indices", [])
            n_rules = len(sel_idx)
            corrected_rules.append(n_rules)
            sel_tokens = sum(rule_token_costs[i] for i in sel_idx if i < len(rule_token_costs))
            corrected_tokens.append(sel_tokens)
            p["n_rules"] = n_rules
            p["selected_tokens"] = int(sel_tokens)
            p["budget_violated"] = sel_tokens > budget
            if p.get("predicted", "") == "":
                api_failures += 1
            if p["budget_violated"]:
                budget_violations += 1

        arr = np.array(corrected_rules)
        tok_arr = np.array(corrected_tokens)
        build_ms = np.array([p.get("build_ms", 0) for p in per_item])

        res["avg_rules"] = float(np.mean(arr))
        res["avg_selected_tokens"] = float(np.mean(tok_arr)) if len(tok_arr) > 0 else 0
        res["selected_tokens_median"] = float(np.median(tok_arr)) if len(tok_arr) > 0 else 0
        res["build_ms_median"] = float(np.median(build_ms))
        res["build_ms_p95"] = float(np.percentile(build_ms, 95))
        res["build_ms_p99"] = float(np.percentile(build_ms, 99))
        res["build_ms_max"] = float(np.max(build_ms))
        res["api_failures"] = api_failures
        res["budget_violations"] = budget_violations

        acc = float(np.mean([p["hard"] for p in per_item]))
        print(f"  {method_name}: acc={acc:.4f} avg_rules={res['avg_rules']:.1f} "
              f"sel_tokens={res['avg_selected_tokens']:.0f} budget_viol={budget_violations}")

    out_path = path.replace(".json", "_enriched.json")
    def _serial(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, dict): return {k: _serial(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)): return [_serial(x) for x in obj]
        return obj

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(_serial(enriched), f, ensure_ascii=False, indent=2)
    print(f"Saved: {os.path.basename(out_path)}\n")
