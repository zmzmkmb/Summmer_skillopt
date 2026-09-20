#!/usr/bin/env python3
"""Read-only combined held-out audit for the v21/v23 recovery execution."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response, sha256_file, stable

V22 = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22"
V21_LIVE = ROOT / "artifacts/acl2027_phase2_heldout_live_v21"
V23_LIVE = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23"
PLAN = V22 / "combined_analysis_plan.json"
GOLD = V22 / "combined_held_out_gold.json"
V21_LEDGER = V21_LIVE / "ledger.json"
V23_LEDGER = V23_LIVE / "ledger.json"
AUDIT = V23_LIVE / "combined_held_out_audit.json"
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def gold_answers(row: dict[str, Any]) -> set[str]:
    values = row.get("answers")
    if values is None:
        values = [row["answer"]]
    return {normalize_answer(value) for value in values}


def analyze() -> dict[str, Any]:
    plan = load(PLAN)["rows"]
    gold = {row["task_id"]: row for row in load(GOLD)}
    v21 = load(V21_LEDGER)
    v23 = load(V23_LEDGER)
    if len(plan) != 320 or len(gold) != 80 or len(v23) != 88:
        raise RuntimeError("complete v21/v23 combined held-out inputs required")
    records = {row["logical_call_id"]: row for row in v21 + v23 if row.get("status") == "completed"}
    if len(records) < 320:
        raise RuntimeError("combined held-out ledger is incomplete")
    totals = {condition: 0 for condition in CONDITIONS}
    correct = {condition: 0 for condition in CONDITIONS}
    contract_valid = {condition: 0 for condition in CONDITIONS}
    outcomes: dict[str, dict[str, bool]] = {}
    row_audit: list[dict[str, Any]] = []
    for planned in plan:
        record = records.get(planned["logical_call_id"])
        if record is None or record.get("request_hash") != planned["request_hash"] or record.get("task_id") != planned["task_id"] or record.get("condition") != planned["condition"]:
            raise RuntimeError("combined ledger/plan binding drift")
        condition = planned["condition"]
        totals[condition] += 1
        valid = False
        passed = False
        try:
            parsed = parse_response(record["raw_response"])
            valid = True
            passed = normalize_answer(parsed["answer"]) in gold_answers(gold[planned["task_id"]])
        except Exception:
            pass
        contract_valid[condition] += int(valid)
        correct[condition] += int(passed)
        outcomes.setdefault(planned["task_id"], {})[condition] = passed
        row_audit.append({"task_id": planned["task_id"], "condition": condition, "logical_call_id": planned["logical_call_id"], "request_hash": planned["request_hash"], "response_sha256": record["raw_response_sha256"], "source": planned["source"], "contract_valid": valid, "answer_correct": passed})
    if len(outcomes) != 80 or any(set(values) != set(CONDITIONS) for values in outcomes.values()):
        raise RuntimeError("combined 80x4 task grid incomplete")
    typed_wins = sum(values["contextual_typed_prior"] and not values["global_only"] for values in outcomes.values())
    typed_losses = sum(not values["contextual_typed_prior"] and values["global_only"] for values in outcomes.values())
    ties = 80 - typed_wins - typed_losses
    accuracy = {condition: correct[condition] / totals[condition] for condition in CONDITIONS}
    margin = accuracy["contextual_typed_prior"] - accuracy["global_only"]
    if margin >= 0.125 and typed_wins >= 3 and typed_losses == 0:
        gate = "positive"
    elif margin <= -0.125 or typed_losses >= 2:
        gate = "negative"
    else:
        gate = "inconclusive"
    result = {
        "schema_version": 23, "status": "complete", "combined_rows": 320, "combined_tasks": 80,
        "v21_preserved_rows": 232, "v23_recovery_rows": 88,
        "condition_counts": totals, "contract_valid_counts": contract_valid,
        "condition_correct_counts": correct, "condition_accuracy": accuracy,
        "primary_paired_comparison": {"contextual_typed_prior_minus_global_only_accuracy": margin, "typed_wins": typed_wins, "typed_losses": typed_losses, "ties": ties},
        "eligibility_gate": gate,
        "decision_rule": {"positive": "margin >= 0.125 and typed_wins >= 3 and typed_losses == 0", "negative": "margin <= -0.125 or typed_losses >= 2", "otherwise": "inconclusive"},
        "gold_accessed_only_after_execution": True, "plan_sha256": sha256_file(PLAN), "gold_sha256": sha256_file(GOLD),
        "v21_ledger_sha256": sha256_file(V21_LEDGER), "v23_ledger_sha256": sha256_file(V23_LEDGER),
        "network_calls": 88, "provider_calls": 88, "paid_api_calls": 88,
        "calibration_calls": 0, "development_calls": 0, "formal_history_calls": 0, "probe_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0,
        "outcomes": row_audit,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


if __name__ == "__main__":
    result = analyze()
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
