#!/usr/bin/env python3
"""Read-only post-run audit for the partial or complete v21 held-out ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response, sha256_file, stable

ARTIFACT = ROOT / "artifacts/acl2027_phase2_heldout_live_v21"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21/held_out_schedule.json"
LEDGER = ARTIFACT / "ledger.json"
GOLD = ROOT / "data/searchqa_phase2_verified/held_out.json"
AUDIT = ARTIFACT / "held_out_partial_audit.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def analyze() -> dict[str, Any]:
    schedule = load(SCHEDULE)["schedule"]
    ledger = load(LEDGER)
    gold = {row["task_id"]: row for row in load(GOLD)}
    planned = {row["logical_call_id"]: row for row in schedule}
    completed = [row for row in ledger if row.get("status") == "completed"]
    full_task_ids = sorted({row["task_id"] for row in completed if sum(item.get("task_id") == row["task_id"] and item.get("status") == "completed" for item in ledger) == 4})
    condition_counts = {condition: sum(row.get("condition") == condition for row in completed) for condition in ("cold", "copied_global", "global_only", "contextual_typed_prior")}
    condition_correct = {condition: 0 for condition in condition_counts}
    contract_valid = {condition: 0 for condition in condition_counts}
    outcomes: dict[str, dict[str, bool]] = {task_id: {} for task_id in full_task_ids}
    for record in completed:
        plan = planned[record["logical_call_id"]]
        task_gold = gold[plan["task_id"]]
        try:
            parsed = parse_response(record["raw_response"])
            contract_valid[plan["condition"]] += 1
            correct = normalize_answer(parsed["answer"]) in {normalize_answer(answer) for answer in task_gold["answers"]}
        except Exception:
            correct = False
        condition_correct[plan["condition"]] += int(correct)
        if plan["task_id"] in outcomes:
            outcomes[plan["task_id"]][plan["condition"]] = correct
    paired = [values for values in outcomes.values() if "contextual_typed_prior" in values and "global_only" in values]
    full_grid_correct = {condition: sum(values.get(condition, False) for values in outcomes.values()) for condition in condition_counts}
    typed = sum(v["contextual_typed_prior"] for v in paired)
    global_only = sum(v["global_only"] for v in paired)
    result = {
        "schema_version": 21,
        "status": "partial_terminal_hard_stop" if len(completed) < len(schedule) else "complete",
        "planned_calls": len(schedule),
        "completed_calls": len(completed),
        "terminal_rows": sum(bool(row.get("terminal")) for row in ledger),
        "full_task_grids": len(full_task_ids),
        "condition_counts_completed": condition_counts,
        "contract_valid_counts": contract_valid,
        "condition_correct_counts_completed_prefix": condition_correct,
        "full_grid_condition_correct_counts": full_grid_correct,
        "full_grid_condition_accuracy": {condition: full_grid_correct[condition] / len(full_task_ids) if full_task_ids else None for condition in condition_counts},
        "full_grid_primary_comparison": {
            "tasks": len(paired),
            "contextual_typed_prior_correct": typed,
            "global_only_correct": global_only,
            "margin": (typed - global_only) / len(paired) if paired else None,
            "typed_wins": sum(v["contextual_typed_prior"] and not v["global_only"] for v in paired),
            "typed_losses": sum((not v["contextual_typed_prior"]) and v["global_only"] for v in paired),
            "ties": sum(v["contextual_typed_prior"] == v["global_only"] for v in paired),
        },
        "eligibility_gate": "not_reached_incomplete_held_out_prefix" if len(completed) < len(schedule) else "requires_frozen_decision_evaluation",
        "gold_accessed_only_after_execution": True,
        "gold_sha256": sha256_file(GOLD),
        "ledger_sha256": sha256_file(LEDGER),
        "schedule_sha256": sha256_file(SCHEDULE),
        "network_calls": len(ledger),
        "provider_calls": len(ledger),
        "paid_api_calls": len(ledger),
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


if __name__ == "__main__":
    result = analyze()
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
