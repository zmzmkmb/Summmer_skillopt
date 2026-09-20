#!/usr/bin/env python3
"""Non-gating shape-tolerant diagnostic for the completed Phase 3D v3 ledger."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, sha256_file, stable
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import alias_tolerant_correct

import scripts.analyze_acl2027_phase3d_specificity_abstention_live_v3 as strict

VERSION = "3.1"
SCRIPT = ROOT / "scripts/analyze_acl2027_phase3d_specificity_abstention_contract_diagnostic_v3_1.py"
TEST = ROOT / "tests/test_acl2027_phase3d_specificity_abstention_contract_diagnostic_v3_1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_v3"
AUDIT = ARTIFACT / "contract_shape_diagnostic_v3_1.json"
REPORT = ROOT / "paper/acl2027/results/phase3d_specificity_abstention_contract_diagnostic_v3_1.md"


def tolerant_parse(raw: Any, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc}"
    if not isinstance(value, dict) or set(value) != {"skill_assessments", "selected_skill_id", "intermediate_operation", "final_answer"}:
        return None, "top_level_contract"
    assessments = value["skill_assessments"]
    order = row["candidate_order"]
    if isinstance(assessments, dict):
        if set(assessments) != set(order):
            return None, "assessment_mapping_keys"
        assessments = [assessments[candidate_id] for candidate_id in order]
    elif not isinstance(assessments, list):
        return None, "assessment_not_array_or_mapping"
    normalized = {**value, "skill_assessments": assessments}
    return strict.parse_contract(normalized, row)


def paired(values: dict[str, dict[str, bool]], left: str, right: str) -> dict[str, int]:
    left_only = sum(rows[left] and not rows[right] for rows in values.values())
    right_only = sum(rows[right] and not rows[left] for rows in values.values())
    return {"left_only": left_only, "right_only": right_only, "both": sum(rows[left] and rows[right] for rows in values.values()), "neither": len(values) - left_only - right_only - sum(rows[left] and rows[right] for rows in values.values()), "net_wins": left_only - right_only}


def diagnostic() -> dict[str, Any]:
    strict_result = strict.load(strict.AUDIT)
    ledger = strict.load(strict.LEDGER)
    schedule = {row["logical_call_id"]: row for row in strict.load(strict.SCHEDULE)["schedule"]}
    gold = {str(row["task_id"]): row for row in strict.load(strict.GOLD)}
    if strict_result.get("decision_gate") != "negative" or strict_result.get("contract_valid_rows") != 0 or len(ledger) != 240:
        raise RuntimeError("strict Phase 3D v3 contract-failure result required")
    grids: dict[str, dict[str, dict[str, Any]]] = {}
    errors: Counter[str] = Counter()
    strict_errors: Counter[str] = Counter()
    valid = 0
    for record in ledger:
        row = schedule[record["logical_call_id"]]
        _, strict_error = strict.parse_contract(record["raw_response"], row)
        strict_errors[strict_error or "valid"] += 1
        parsed, error = tolerant_parse(record["raw_response"], row)
        errors[error or "valid"] += 1
        valid += parsed is not None
        task_id = str(record["task_id"])
        task = gold[task_id]
        answer = parsed["final_answer"] if parsed else ""
        expected = task["answer"] if isinstance(task["answer"], list) else [task["answer"]]
        grids.setdefault(task_id, {})[row["condition"]] = {"parsed": parsed, "alias_correct": parsed is not None and alias_tolerant_correct(answer, expected), "answer": answer}
    if valid != 240 or len(grids) != 40 or any(len(grid) != 6 for grid in grids.values()):
        raise RuntimeError("shape-tolerant diagnostic coverage drift")
    contextual = sum(grid["contextual_single"]["parsed"]["selected_skill_id"] == grid["contextual_single"]["parsed"]["selected_skill_id"] and grid["contextual_single"]["parsed"]["selected_skill_id"] != "none" for grid in grids.values())
    contextual_expected = sum(grid["contextual_single"]["parsed"]["selected_skill_id"] == schedule[next(record["logical_call_id"] for record in ledger if str(record["task_id"]) == task_id and record["condition"] == "contextual_single")]["expected_specificity_selection"] for task_id, grid in grids.items())
    irrelevant = sum(grid["irrelevant_single"]["parsed"]["selected_skill_id"] == "none" for grid in grids.values())
    dual = [grid[condition]["parsed"] for grid in grids.values() for condition in ("dual_contextual_first", "dual_irrelevant_first")]
    dual_correct = 0; dual_wrong = 0; first_correct = 0; second_correct = 0
    for task_id, grid in grids.items():
        for condition in ("dual_contextual_first", "dual_irrelevant_first"):
            planned = schedule[next(record["logical_call_id"] for record in ledger if str(record["task_id"]) == task_id and record["condition"] == condition)]
            selected = grid[condition]["parsed"]["selected_skill_id"]
            dual_correct += selected == planned["expected_specificity_selection"]
            dual_wrong += selected not in ("none", planned["expected_specificity_selection"])
            if condition == "dual_contextual_first": first_correct += selected == planned["expected_specificity_selection"]
            else: second_correct += selected == planned["expected_specificity_selection"]
    operations = sum(grid["contextual_single"]["parsed"]["intermediate_operation"].strip().lower() != grid["irrelevant_single"]["parsed"]["intermediate_operation"].strip().lower() for grid in grids.values())
    answers = sum(normalize_answer(grid["contextual_single"]["answer"]) != normalize_answer(grid["irrelevant_single"]["answer"]) for grid in grids.values())
    values = {task_id: {condition: row["alias_correct"] for condition, row in grid.items()} for task_id, grid in grids.items()}
    ir = paired(values, "contextual_single", "irrelevant_single"); cold = paired(values, "contextual_single", "cold")
    result = {"schema_version": VERSION, "status": "complete_non_gating_diagnostic", "strict_result_preserved": {"decision_gate": strict_result["decision_gate"], "contract_valid_rows": strict_result["contract_valid_rows"], "aggregate_fingerprint": strict_result["aggregate_fingerprint"]}, "diagnostic_contract": "Accepts the observed candidate-ID-keyed assessment mapping only after reconstructing the frozen candidate order; this does not satisfy the frozen array contract and cannot alter the strict gate.", "tolerant_contract_valid_rows": valid, "strict_contract_error_counts": dict(strict_errors), "shape_tolerant_parse_error_counts": dict(errors), "metrics": {"contextual_single_selected_non_none_rate": contextual / 40, "contextual_single_correct_selection_rate": contextual_expected / 40, "irrelevant_single_rejection_rate": irrelevant / 40, "dual_correct_selection_rate": dual_correct / 80, "dual_wrong_selection_rate": dual_wrong / 80, "dual_order_effect_absolute_difference": abs(first_correct / 40 - second_correct / 40), "contextual_vs_irrelevant_operation_change_rate": operations / 40, "contextual_vs_irrelevant_normalized_answer_change_rate": answers / 40, "contextual_alias_net_wins_over_irrelevant": ir["net_wins"], "contextual_alias_net_loss_vs_cold": max(0, -cold["net_wins"]), "alias_contextual_vs_irrelevant": ir, "alias_contextual_vs_cold": cold}, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "formal_scaling_calls": 0, "bindings": {"strict_analysis_sha256": sha256_file(strict.AUDIT), "ledger_sha256": sha256_file(strict.LEDGER), "schedule_sha256": sha256_file(strict.SCHEDULE), "gold_sha256": sha256_file(strict.GOLD), "script_sha256": sha256_file(SCRIPT), "test_sha256": sha256_file(TEST)}}
    result["aggregate_fingerprint"] = stable(result)
    return result


def main() -> int:
    result = diagnostic()
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(f"# Phase 3D v3.1 contract-shape diagnostic\n\nThe strict v3 gate remains **negative** because 240/240 responses used a candidate-ID-keyed assessment object instead of the frozen ordered assessment array. The non-gating diagnostic reconstructs that order only to describe the already spent responses; it cannot reverse the strict result.\n\nTolerant parse: `{result['tolerant_contract_valid_rows']}/240`. Metrics: `{json.dumps(result['metrics'], sort_keys=True)}`.\n\nFingerprint: `{result['aggregate_fingerprint']}`.\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
