#!/usr/bin/env python3
"""Frozen Phase 3H v5 answer-grounding analysis; reads no provider state."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_live_v5"
DESIGN = ROOT / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v3"
LEDGER, AUDIT, SCHEDULE, GOLD, PLAN = ARTIFACT / "ledger.json", ARTIFACT / "run_audit.json", DESIGN / "counterfactual_schedule.json", DESIGN / "counterfactual_private_gold.json", DESIGN / "analysis_plan.json"
OUT, REPORT = ARTIFACT / "answer_grounding_analysis.json", ROOT / "paper/acl2027/results/phase3h_counterfactual_answer_sensitivity_live_v5.md"


def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))
def norm(value: Any) -> str: return re.sub(r"\s+", " ", str(value).strip().casefold())
def rate(items: list[bool]) -> float | None: return round(sum(items) / len(items), 6) if items else None


def parse(row: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    scheduled = plan[row["logical_call_id"]]; body = scheduled["canonical_request_body"]
    try: value = json.loads(row["raw_response"])
    except (TypeError, json.JSONDecodeError): value = None
    exact = body["response_contract"]["exact_keys"]
    valid = isinstance(value, dict) and set(value) == set(exact) and isinstance(value.get("final_answer"), str) and bool(value["final_answer"].strip()) and isinstance(value.get("intermediate_operation"), str) and bool(value["intermediate_operation"].strip()) and isinstance(value.get("selected_skill_id"), str) and value["selected_skill_id"] in body["response_contract"]["selected_skill_id"]["allowed"] and isinstance(value.get("skill_assessments"), dict)
    expected = scheduled["expected_selected_skill_id"]
    return {"task_id": row["task_id"], "condition": row["condition"], "contract_valid": valid, "expected_execution": valid and value["selected_skill_id"] == expected, "selected_skill_id": value.get("selected_skill_id") if isinstance(value, dict) else None, "operation": norm(value.get("intermediate_operation")) if isinstance(value, dict) else "", "answer": norm(value.get("final_answer")) if isinstance(value, dict) else ""}


def analyze() -> dict[str, Any]:
    ledger, audit, schedule, gold, rules = load(LEDGER), load(AUDIT), load(SCHEDULE)["schedule"], load(GOLD), load(PLAN)
    if audit.get("status") != "completed" or audit.get("completed_calls") != 200 or len(ledger) != len(schedule) != 200: raise RuntimeError("v5 ledger is not complete")
    schedule_by_id = {row["logical_call_id"]: row for row in schedule}; gold_by_id = {row["task_id"]: row for row in gold}
    rows = [parse(row, schedule_by_id) for row in ledger]
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows: grouped.setdefault(row["task_id"], {})[row["condition"]] = row
    contextual, control, dual = [], [], []
    primary, grounding = [], []
    for task_id, condition_rows in grouped.items():
        g = gold_by_id[task_id]; ctx, ctl = condition_rows["contextual"], condition_rows["incompatible_control"]
        contextual.append(ctx["contract_valid"] and ctx["expected_execution"] and ctx["answer"] == norm(g["target_answer"]))
        control.append(ctl["contract_valid"] and ctl["expected_execution"] and ctl["answer"] == norm(g["counterfactual_answer"]))
        eligible = ctx["contract_valid"] and ctl["contract_valid"] and ctx["expected_execution"] and ctl["expected_execution"] and ctx["operation"] != ctl["operation"]
        if eligible:
            primary.append(task_id); grounding.append(ctx["answer"] == norm(g["target_answer"]) and ctl["answer"] == norm(g["counterfactual_answer"]))
        for condition in ("dual_contextual_first", "dual_control_first"):
            item = condition_rows[condition]; dual.append((condition, item["contract_valid"] and item["expected_execution"]))
    contract_rate = rate([row["contract_valid"] for row in rows]); ctx_exec = rate([row["expected_execution"] for row in rows if row["condition"] == "contextual"]); ctl_exec = rate([row["expected_execution"] for row in rows if row["condition"] == "incompatible_control"]); dual_a = rate([ok for c, ok in dual if c == "dual_contextual_first"]); dual_b = rate([ok for c, ok in dual if c == "dual_control_first"])
    metrics = {"contract_valid_rate": contract_rate, "contextual_target_execution_rate": ctx_exec, "incompatible_control_execution_rate": ctl_exec, "contextual_target_answer_rate": rate(contextual), "control_counterfactual_answer_rate": rate(control), "primary_population_tasks": len(primary), "paired_target_to_counterfactual_grounding_rate": rate(grounding), "dual_contextual_first_expected_selection_rate": dual_a, "dual_control_first_expected_selection_rate": dual_b, "dual_order_effect_absolute_difference": round(abs((dual_a or 0) - (dual_b or 0)), 6)}
    p, n = rules["positive_gate"], rules["negative_gate"]
    positive = len(primary) >= p["primary_population_tasks_at_least"] and all((metrics[k] is not None and metrics[k] >= v) for k, v in (("contract_valid_rate", p["contract_valid_rate_at_least"]), ("contextual_target_execution_rate", p["contextual_target_execution_rate_at_least"]), ("incompatible_control_execution_rate", p["incompatible_control_execution_rate_at_least"]), ("contextual_target_answer_rate", p["contextual_target_answer_rate_at_least"]), ("control_counterfactual_answer_rate", p["control_counterfactual_answer_rate_at_least"]), ("paired_target_to_counterfactual_grounding_rate", p["paired_target_to_counterfactual_grounding_rate_at_least"]), ("dual_contextual_first_expected_selection_rate", p["dual_target_selection_rate_at_least"]), ("dual_control_first_expected_selection_rate", p["dual_target_selection_rate_at_least"]))) and metrics["dual_order_effect_absolute_difference"] <= p["dual_order_effect_absolute_difference_at_most"]
    negative = len(primary) >= n["primary_population_tasks_at_least"] and metrics["paired_target_to_counterfactual_grounding_rate"] < n["and_paired_target_to_counterfactual_grounding_rate_below"]
    result = {"schema_version": 5, "status": "complete", "analysis_plan": rules, "audit": {k: audit[k] for k in ("completed_calls", "provider_attempts", "retries", "exact_stage_cost_cny", "total_tokens", "request_start_pacing_valid")}, "metrics": metrics, "decision_gate": "positive" if positive else "negative" if negative else "inconclusive", "cross_domain_scaling_authorized": False, "formal_scaling_authorized": False}
    OUT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text(f"# ACL 2027 Phase 3H v5 execution\n\nThe authorized 200-call run completed with zero retries, {audit['total_tokens']} exact tokens, and CNY {audit['exact_stage_cost_cny']:.6f} exact stage cost. The authorization closed automatically.\n\nFrozen answer-grounding decision: `{result['decision_gate']}`.\n\n```json\n{json.dumps(metrics, ensure_ascii=True, indent=2)}\n```\n\nCross-domain and formal scaling remain closed.\n", encoding="utf-8")
    return result


if __name__ == "__main__": print(json.dumps(analyze(), ensure_ascii=True, sort_keys=True, indent=2))
