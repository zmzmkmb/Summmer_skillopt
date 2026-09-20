#!/usr/bin/env python3
"""Non-gating boolean-mapping diagnostic for the spent Phase 3F grid."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, sha256_file, stable
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import alias_tolerant_correct

VERSION = 2
PREFLIGHT = ROOT / "artifacts/acl2027_phase3f_contract_control_redesign_v1"
GOLD = PREFLIGHT / "specificity_private_gold.json"
SCHEDULE = PREFLIGHT / "specificity_schedule.json"
PLAN = PREFLIGHT / "analysis_plan.json"
LIVE = ROOT / "artifacts/acl2027_phase3f_live_v2"
LEDGER = LIVE / "ledger.json"
RUN_AUDIT = LIVE / "run_audit.json"
AUDIT = LIVE / "mapping_shape_diagnostic_v1.json"
REPORT = ROOT / "paper/acl2027/results/phase3f_mapping_shape_diagnostic_v1.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_contract(raw: Any, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc}"
    if not isinstance(value, dict) or set(value) != {"skill_assessments", "selected_skill_id", "intermediate_operation", "final_answer"}:
        return None, "top_level_contract"
    order = row["candidate_order"]
    assessments = value["skill_assessments"]
    if not isinstance(assessments, dict) or set(assessments) != set(order):
        return None, "assessment_identity"
    for expected_id in order:
        item = assessments[expected_id]
        if isinstance(item, bool):
            continue
        if not isinstance(item, dict) or set(item) != {"applicable"} or not isinstance(item["applicable"], bool):
            return None, "assessment_shape"
    allowed = row["canonical_request_body"]["available_skill_ids"]
    if not isinstance(value["selected_skill_id"], str) or value["selected_skill_id"] not in allowed:
        return None, "selected_skill_id"
    for key in ("intermediate_operation", "final_answer"):
        if not isinstance(value[key], str) or not value[key].strip():
            return None, key
    return value, None


def paired(values: dict[str, dict[str, bool]], left: str, right: str) -> dict[str, Any]:
    left_only = sum(rows[left] and not rows[right] for rows in values.values())
    right_only = sum(rows[right] and not rows[left] for rows in values.values())
    both = sum(rows[left] and rows[right] for rows in values.values())
    neither = len(values) - left_only - right_only - both
    return {"left_only": left_only, "right_only": right_only, "both": both, "neither": neither, "net_wins": left_only - right_only}


def analyze() -> dict[str, Any]:
    gold, schedule, plan, ledger, run = load(GOLD), load(SCHEDULE)["schedule"], load(PLAN), load(LEDGER), load(RUN_AUDIT)
    if run.get("status") != "completed" or run.get("authorization_closed") is not True or len(ledger) != 240:
        raise RuntimeError("complete closed Phase 3F v2 execution required")
    by_gold = {str(task["task_id"]): task for task in gold}
    by_plan = {row["logical_call_id"]: row for row in schedule}
    if len(by_gold) != 40 or len(by_plan) != 240:
        raise RuntimeError("Phase 3F source grid drift")
    grids: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    outcomes: list[dict[str, Any]] = []
    contract_valid = 0
    for record in ledger:
        planned = by_plan.get(record["logical_call_id"])
        task = by_gold.get(str(record["task_id"]))
        if planned is None or task is None or record["request_hash"] != planned["request_hash"]:
            raise RuntimeError("Phase 3F ledger binding drift")
        parsed, error = parse_contract(record["raw_response"], planned)
        contract_valid += parsed is not None
        answer = parsed["final_answer"] if parsed else ""
        expected = task["answer"] if isinstance(task["answer"], list) else [task["answer"]]
        strict_correct = parsed is not None and normalize_answer(answer) in {normalize_answer(str(value)) for value in expected}
        alias_correct = parsed is not None and alias_tolerant_correct(answer, expected)
        row = {
            "task_id": str(task["task_id"]), "skill_family": task["skill_family"], "condition": planned["condition"],
            "candidate_order": planned["candidate_order"], "expected_specificity_selection": planned["expected_specificity_selection"],
            "contract_valid": parsed is not None, "contract_error": error,
            "skill_assessments": parsed["skill_assessments"] if parsed else None,
            "selected_skill_id": parsed["selected_skill_id"] if parsed else None,
            "intermediate_operation": parsed["intermediate_operation"] if parsed else None,
            "final_answer": answer, "strict_correct": strict_correct, "alias_tolerant_correct": alias_correct,
            "logical_call_id": record["logical_call_id"], "request_hash": record["request_hash"], "response_sha256": record["raw_response_sha256"],
        }
        grids[row["task_id"]][row["condition"]] = row
        outcomes.append(row)
    if len(grids) != 40 or any(set(rows) != {"cold", "global_only", "contextual_single", "irrelevant_single", "dual_contextual_first", "dual_irrelevant_first"} for rows in grids.values()):
        raise RuntimeError("Phase 3F completed grid is incomplete")

    contextual_correct = sum(rows["contextual_single"]["selected_skill_id"] == rows["contextual_single"]["expected_specificity_selection"] for rows in grids.values())
    irrelevant_rejected = sum(rows["irrelevant_single"]["selected_skill_id"] == "none" for rows in grids.values())
    dual_rows = [rows[c] for rows in grids.values() for c in ("dual_contextual_first", "dual_irrelevant_first")]
    dual_correct = sum(row["selected_skill_id"] == row["expected_specificity_selection"] for row in dual_rows)
    dual_wrong = sum(row["selected_skill_id"] not in (None, "none", row["expected_specificity_selection"]) for row in dual_rows)
    left_rate = sum(rows["dual_contextual_first"]["selected_skill_id"] == rows["dual_contextual_first"]["expected_specificity_selection"] for rows in grids.values()) / 40
    right_rate = sum(rows["dual_irrelevant_first"]["selected_skill_id"] == rows["dual_irrelevant_first"]["expected_specificity_selection"] for rows in grids.values()) / 40
    family_rejection = {family: sum(rows["irrelevant_single"]["selected_skill_id"] == "none" for rows in grids.values() if rows["irrelevant_single"]["skill_family"] == family) / sum(rows["irrelevant_single"]["skill_family"] == family for rows in grids.values()) for family in sorted({task["skill_family"] for task in gold})}
    operation_changes = sum((rows["contextual_single"]["intermediate_operation"] or "").strip().lower() != (rows["irrelevant_single"]["intermediate_operation"] or "").strip().lower() for rows in grids.values())
    answer_changes = sum(normalize_answer(rows["contextual_single"]["final_answer"]) != normalize_answer(rows["irrelevant_single"]["final_answer"]) for rows in grids.values())
    alias = {task_id: {condition: rows[condition]["alias_tolerant_correct"] for condition in rows} for task_id, rows in grids.items()}
    alias_irrelevant = paired(alias, "contextual_single", "irrelevant_single")
    alias_cold = paired(alias, "contextual_single", "cold")
    metrics = {
        "contextual_single_correct_selection_count": contextual_correct,
        "contextual_single_correct_selection_rate": contextual_correct / 40,
        "irrelevant_single_rejection_count": irrelevant_rejected,
        "irrelevant_single_rejection_rate": irrelevant_rejected / 40,
        "family_irrelevant_single_rejection_rates": family_rejection,
        "dual_correct_selection_count": dual_correct,
        "dual_correct_selection_rate": dual_correct / 80,
        "dual_wrong_selection_count": dual_wrong,
        "dual_wrong_selection_rate": dual_wrong / 80,
        "dual_contextual_first_correct_rate": left_rate,
        "dual_irrelevant_first_correct_rate": right_rate,
        "dual_order_effect_absolute_difference": abs(left_rate - right_rate),
        "contextual_vs_irrelevant_operation_change_count": operation_changes,
        "contextual_vs_irrelevant_operation_change_rate": operation_changes / 40,
        "contextual_vs_irrelevant_normalized_answer_change_count": answer_changes,
        "contextual_vs_irrelevant_normalized_answer_change_rate": answer_changes / 40,
        "contextual_alias_net_wins_over_irrelevant": alias_irrelevant["net_wins"],
        "contextual_alias_net_loss_vs_cold": max(0, -alias_cold["net_wins"]),
        "alias_contextual_vs_irrelevant": alias_irrelevant,
        "alias_contextual_vs_cold": alias_cold,
    }
    pg, ng = plan["positive_gate"], plan["negative_gate"]
    positive = contract_valid == 240 and metrics["contextual_single_correct_selection_rate"] >= pg["contextual_single_correct_selection_rate_at_least"] and metrics["irrelevant_single_rejection_rate"] >= pg["irrelevant_single_rejection_rate_at_least"] and min(family_rejection.values()) >= pg["each_family_irrelevant_single_rejection_rate_at_least"] and metrics["dual_correct_selection_rate"] >= pg["dual_correct_selection_rate_at_least"] and metrics["dual_wrong_selection_rate"] <= pg["dual_wrong_selection_rate_at_most"] and metrics["dual_order_effect_absolute_difference"] <= pg["dual_order_effect_absolute_difference_at_most"] and metrics["contextual_vs_irrelevant_operation_change_rate"] >= pg["contextual_vs_irrelevant_operation_change_rate_at_least"] and metrics["contextual_vs_irrelevant_normalized_answer_change_rate"] >= pg["contextual_vs_irrelevant_normalized_answer_change_rate_at_least"] and metrics["contextual_alias_net_wins_over_irrelevant"] >= pg["contextual_alias_net_wins_over_irrelevant_at_least"] and metrics["contextual_alias_net_loss_vs_cold"] <= pg["contextual_alias_net_loss_vs_cold_at_most"]
    negative = metrics["contextual_single_correct_selection_rate"] < ng["contextual_single_correct_selection_rate_below"] or metrics["irrelevant_single_rejection_rate"] < ng["or_irrelevant_single_rejection_rate_below"] or (ng["or_dual_wrong_selection_rate_at_least_dual_correct_selection_rate"] and metrics["dual_wrong_selection_rate"] >= metrics["dual_correct_selection_rate"])
    gate = "positive" if positive else "negative" if negative else "inconclusive"
    result = {"schema_version": VERSION, "status": "complete_non_gating", "diagnostic_only": True, "strict_gate_preserved": "inconclusive", "tasks": 40, "rows": 240, "completed_calls": 240, "contract_valid_rows": contract_valid, "contract_invalid_rows": 240 - contract_valid, "metrics": metrics, "descriptive_gate_if_normalization_preregistered": gate, "decision_gate": "non_gating", "cross_domain_scaling_allowed": False, "analysis_plan": plan, "provider_attempts": run["provider_attempts"], "exact_stage_cost_cny": run["exact_stage_cost_cny"], "known_cumulative_cost_lower_bound_cny": run["known_cumulative_cost_lower_bound_cny"], "later_stage_calls": 0, "cross_domain_scaling_calls": 0, "formal_scaling_calls": 0, "bindings": {"gold_sha256": sha256_file(GOLD), "schedule_sha256": sha256_file(SCHEDULE), "analysis_plan_sha256": sha256_file(PLAN), "ledger_sha256": sha256_file(LEDGER), "run_audit_sha256": sha256_file(RUN_AUDIT)}, "outcomes": outcomes}
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any]) -> str:
    m = result["metrics"]
    return f"""# ACL 2027 Phase 3F boolean-mapping diagnostic v1

This diagnostic accepts direct boolean mapping values in addition to the frozen nested-object values. It is descriptive only and cannot change the strict Phase 3F gate.

The explicitly authorized execution completed `{result['completed_calls']}/240` calls with `{result['contract_valid_rows']}/240` contract-valid responses.

Contextual-single correct selection was `{m['contextual_single_correct_selection_count']}/40` (`{m['contextual_single_correct_selection_rate']:.4f}`); irrelevant-single rejection was `{m['irrelevant_single_rejection_count']}/40` (`{m['irrelevant_single_rejection_rate']:.4f}`). Dual correct selection was `{m['dual_correct_selection_count']}/80` (`{m['dual_correct_selection_rate']:.4f}`), dual wrong selection was `{m['dual_wrong_selection_count']}/80` (`{m['dual_wrong_selection_rate']:.4f}`), and the absolute order effect was `{m['dual_order_effect_absolute_difference']:.4f}`.

Contextual-versus-irrelevant operation changes were `{m['contextual_vs_irrelevant_operation_change_count']}/40`; normalized-answer changes were `{m['contextual_vs_irrelevant_normalized_answer_change_count']}/40`. Alias-tolerant contextual net wins over irrelevant were `{m['contextual_alias_net_wins_over_irrelevant']}`, with contextual net loss versus cold `{m['contextual_alias_net_loss_vs_cold']}`.

Frozen decision gate: **{result['decision_gate']}**. Cross-domain scaling allowed: `{result['cross_domain_scaling_allowed']}`.

Exact stage cost: CNY `{result['exact_stage_cost_cny']}`. Known cumulative cost lower bound: CNY `{result['known_cumulative_cost_lower_bound_cny']}`. Authorization is closed; later stages and formal scaling remain unauthorized.

Aggregate fingerprint: `{result['aggregate_fingerprint']}`.
"""


def main() -> int:
    result = analyze()
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in result.items() if key != "outcomes"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
