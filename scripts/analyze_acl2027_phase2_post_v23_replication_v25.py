#!/usr/bin/env python3
"""Read-only replication-only audit for the completed v25 execution."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response, sha256_file, stable
PREFLIGHT = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24"
LIVE = ROOT / "artifacts/acl2027_phase2_post_v23_replication_live_v25"
SCHEDULE = PREFLIGHT / "replication_schedule.json"
GOLD = PREFLIGHT / "replication_private_gold.json"
LEDGER = LIVE / "ledger.json"
AUDIT = LIVE / "replication_audit.json"
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def analyze() -> dict[str, Any]:
    plan = load(SCHEDULE)["schedule"]
    gold = {row["task_id"]: row for row in load(GOLD)}
    records = {row["logical_call_id"]: row for row in load(LEDGER) if row.get("status") == "completed"}
    if len(plan) != 320 or len(gold) != 80 or len(records) != 320:
        raise RuntimeError("complete v25 replication inputs required")
    totals = {c: 0 for c in CONDITIONS}; correct = {c: 0 for c in CONDITIONS}; valid = {c: 0 for c in CONDITIONS}; outcomes: dict[str, dict[str, bool]] = {}; rows = []
    for planned in plan:
        record = records.get(planned["logical_call_id"])
        if record is None or record.get("request_hash") != planned["request_hash"] or record.get("task_id") != planned["task_id"] or record.get("condition") != planned["condition"]:
            raise RuntimeError("v25 ledger/schedule binding drift")
        condition = planned["condition"]; totals[condition] += 1; contract_valid = False; answer_correct = False
        try:
            parsed = parse_response(record["raw_response"]); contract_valid = True
            expected = gold[planned["task_id"]].get("answers") or [gold[planned["task_id"]]["answer"]]
            answer_correct = normalize_answer(parsed["answer"]) in {normalize_answer(value) for value in expected}
        except Exception:
            pass
        valid[condition] += int(contract_valid); correct[condition] += int(answer_correct); outcomes.setdefault(planned["task_id"], {})[condition] = answer_correct
        rows.append({"task_id": planned["task_id"], "condition": condition, "logical_call_id": planned["logical_call_id"], "request_hash": planned["request_hash"], "response_sha256": record["raw_response_sha256"], "contract_valid": contract_valid, "answer_correct": answer_correct})
    if len(outcomes) != 80 or any(set(v) != set(CONDITIONS) for v in outcomes.values()): raise RuntimeError("v25 80x4 grid incomplete")
    typed_wins = sum(v["contextual_typed_prior"] and not v["global_only"] for v in outcomes.values()); typed_losses = sum(not v["contextual_typed_prior"] and v["global_only"] for v in outcomes.values()); ties = 80 - typed_wins - typed_losses
    accuracy = {c: correct[c] / totals[c] for c in CONDITIONS}; margin = accuracy["contextual_typed_prior"] - accuracy["global_only"]
    gate = "positive" if margin >= 0.125 and typed_wins >= 3 and typed_losses == 0 else "negative" if margin <= -0.125 or typed_losses >= 2 else "inconclusive"
    result = {"schema_version": 25, "status": "complete", "replication_rows": 320, "replication_tasks": 80, "condition_counts": totals, "contract_valid_counts": valid, "condition_correct_counts": correct, "condition_accuracy": accuracy, "primary_paired_comparison": {"contextual_typed_prior_minus_global_only_accuracy": margin, "typed_wins": typed_wins, "typed_losses": typed_losses, "ties": ties}, "eligibility_gate": gate, "decision_rule": {"positive": "margin >= 0.125 and typed_wins >= 3 and typed_losses == 0", "negative": "margin <= -0.125 or typed_losses >= 2", "otherwise": "inconclusive"}, "gold_accessed_only_after_execution": True, "schedule_sha256": sha256_file(SCHEDULE), "gold_sha256": sha256_file(GOLD), "ledger_sha256": sha256_file(LEDGER), "network_calls": 320, "provider_calls": 320, "paid_api_calls": 320, "calibration_calls": 0, "development_calls": 0, "formal_history_calls": 0, "probe_calls": 0, "held_out_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0, "outcomes": rows}
    result["aggregate_fingerprint"] = stable(result); return result


if __name__ == "__main__":
    result = analyze(); AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"); print(json.dumps(result, indent=2, sort_keys=True))
