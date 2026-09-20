#!/usr/bin/env python3
"""Analyze completed Phase 4C rows without making provider calls."""
from __future__ import annotations
import json, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts/acl2027_phase4c_repaired_heldout_live_v2"
DESIGN = ROOT / "artifacts/acl2027_phase4c_repaired_zero_network_design_preflight_v1/repaired_heldout_schedule.json"
GOLD = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1/private_gold.json"
OUT = RUN / "phase4c_analysis_v2.json"
REPORT = ROOT / "paper/acl2027/results/phase4c_repaired_heldout_live_v2.md"
CONDITIONS = ("cold", "global_only", "contextual_typed", "shuffled_typed", "incompatible_control")
KEYS = ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")

def load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8-sig"))

def norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip().lower())

def main() -> int:
    rows = load(DESIGN)["rows"]
    records = load(RUN / "ledger.json")
    gold = {str(x["task_id"]): x for x in load(GOLD) if x.get("split") == "heldout"}
    by_key = {(str(r["task_id"]), str(r["condition"])): r for r in rows}
    completed = [r for r in records if r.get("status") == "completed" and isinstance(r.get("raw_response"), str)]
    stats = {c: {"scheduled": 80, "completed": 0, "contract_valid": 0, "evidence_ids_resolve": 0, "answer_scored": 0, "answer_correct": 0} for c in CONDITIONS}
    task_conditions = defaultdict(dict)
    for record in completed:
        c = str(record["condition"]); stats[c]["completed"] += 1
        try: obj = json.loads(record["raw_response"])
        except Exception: obj = None
        canonical = by_key.get((str(record["task_id"]), c), {}).get("canonical_request_body", {})
        user = json.loads(canonical.get("messages", [{}, {"content": "{}"}])[1]["content"])
        ids = {str(s.get("id")) for b in user.get("context", []) for s in b.get("sentences", [])}
        valid = isinstance(obj, dict) and set(obj) == set(KEYS) and all(obj.get(k) not in (None, "", []) for k in KEYS)
        resolves = valid and isinstance(obj.get("evidence_sentence_ids"), list) and bool(obj["evidence_sentence_ids"]) and all(str(x) in ids for x in obj["evidence_sentence_ids"])
        if valid: stats[c]["contract_valid"] += 1
        if resolves: stats[c]["evidence_ids_resolve"] += 1
        answer = gold.get(str(record["task_id"]), {}).get("target_answer")
        if answer and valid:
            stats[c]["answer_scored"] += 1
            if norm(obj.get("final_answer")) == norm(answer): stats[c]["answer_correct"] += 1
        task_conditions[str(record["task_id"])][c] = {"contract_valid": bool(valid), "evidence_ids_resolve": bool(resolves), "answer_correct": bool(answer and valid and norm(obj.get("final_answer")) == norm(answer))}
    for c, s in stats.items():
        denom = s["completed"] or 1
        s["contract_valid_rate"] = round(s["contract_valid"] / denom, 6)
        s["evidence_resolve_rate"] = round(s["evidence_ids_resolve"] / denom, 6)
        s["answer_accuracy_over_scored"] = round(s["answer_correct"] / (s["answer_scored"] or 1), 6)
    result = {"schema_version": 2, "status": "coverage_incomplete", "scheduled_rows": 400, "completed_rows": len(completed), "missing_rows": 400-len(completed), "gold_tasks": len(gold), "conditions": stats, "task_grids_observed": len(task_conditions), "provider_calls": 0, "new_calls_made": 0, "interpretation": "Descriptive analysis only; the 400-row frozen gate is not evaluable because five rows are missing and cumulative-cost accounting requires review."}
    OUT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text("# Phase 4C repaired held-out live v2 analysis\n\nThis analysis is descriptive and coverage-incomplete. The run has 395 completed responses out of 400 scheduled rows; five rows are missing because the CNY 3.00 stage ceiling triggered a terminal hard stop. No new provider calls were made.\n\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
