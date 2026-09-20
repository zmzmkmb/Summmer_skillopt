#!/usr/bin/env python3
"""Frozen analysis for the completed Phase 3B activation pilot."""
from __future__ import annotations

import json, sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, sha256_file, stable
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import alias_tolerant_correct

CONFIG = ROOT / "configs/acl2027/phase3b_activation_preflight_v1.json"
PREFLIGHT, LIVE = ROOT / "artifacts/acl2027_phase3b_activation_preflight_v1", ROOT / "artifacts/acl2027_phase3b_activation_live_v2"
GOLD, SCHEDULE, PLAN = PREFLIGHT / "activation_private_gold.json", PREFLIGHT / "activation_schedule.json", PREFLIGHT / "analysis_plan.json"
LEDGER, RUN_AUDIT = LIVE / "ledger.json", LIVE / "run_audit.json"
AUDIT, REPORT = LIVE / "activation_analysis.json", ROOT / "paper/acl2027/results/phase3b_activation_live_v2.md"
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior", "shuffled_typed_prior")
RESPONSE_KEYS = {"declared_skill_applicability", "selected_skill_id", "intermediate_operation", "final_answer"}


def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_activation(raw: Any, allowed: list[str]) -> dict[str, Any]:
    if not isinstance(raw, str): raise ValueError("raw response must be text")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != RESPONSE_KEYS: raise ValueError("activation response keys invalid")
    if not isinstance(value["declared_skill_applicability"], bool): raise ValueError("applicability must be boolean")
    if not isinstance(value["selected_skill_id"], str) or value["selected_skill_id"] not in allowed: raise ValueError("selected skill ID invalid")
    for key in ("intermediate_operation", "final_answer"):
        if not isinstance(value[key], str) or not value[key].strip(): raise ValueError(f"{key} must be non-empty")
    return value


def pair(values: dict[str, dict[str, bool]], left: str, right: str) -> dict[str, Any]:
    left_only = sum(row[left] and not row[right] for row in values.values()); right_only = sum(row[right] and not row[left] for row in values.values())
    both = sum(row[left] and row[right] for row in values.values()); neither = len(values)-left_only-right_only-both
    return {"left": left, "right": right, "left_only": left_only, "right_only": right_only, "both": both, "neither": neither, "net_wins": left_only-right_only, "rate_difference": (left_only-right_only)/len(values)}


def analyze() -> dict[str, Any]:
    plan = load(PLAN); tasks = {str(r["task_id"]): r for r in load(GOLD)}; schedule = load(SCHEDULE)["schedule"]
    planned = {r["logical_call_id"]: r for r in schedule}; records, run_audit = load(LEDGER), load(RUN_AUDIT)
    if len(tasks) != 60 or len(schedule) != 300 or len(records) != 300 or run_audit.get("status") != "completed" or run_audit.get("authorization_closed") is not True: raise RuntimeError("complete closed Phase 3B grid required")
    if len({(r["task_id"],r["condition"]) for r in records}) != 300: raise RuntimeError("Phase 3B condition grid drift")
    uptake: dict[str,dict[str,bool]] = defaultdict(dict); strict: dict[str,dict[str,bool]] = defaultdict(dict); alias: dict[str,dict[str,bool]] = defaultdict(dict)
    outcomes: list[dict[str,Any]] = []; valid = 0
    for record in records:
        plan_row, task = planned.get(record["logical_call_id"]), tasks.get(str(record["task_id"]))
        if plan_row is None or task is None or record["request_hash"] != plan_row["request_hash"]: raise RuntimeError("ledger schedule or gold binding drift")
        condition, task_id, body = str(record["condition"]), str(record["task_id"]), plan_row["canonical_request_body"]
        parsed = None; error = None
        try: parsed = parse_activation(record["raw_response"], body["available_skill_ids"]); valid += 1
        except Exception as exc: error = f"{type(exc).__name__}: {exc}"
        answer = parsed["final_answer"] if parsed else ""; expected = [str(v) for v in (task.get("answers") or [task.get("answer")]) if v is not None]
        strict_correct = parsed is not None and normalize_answer(answer) in {normalize_answer(v) for v in expected}; alias_correct = parsed is not None and alias_tolerant_correct(answer, expected)
        candidate = str(plan_row["candidate_id"]); used = parsed is not None and candidate != "none" and parsed["declared_skill_applicability"] is True and parsed["selected_skill_id"] == candidate
        uptake[task_id][condition], strict[task_id][condition], alias[task_id][condition] = used, strict_correct, alias_correct
        outcomes.append({"task_id": task_id, "skill_family": task["skill_family"], "condition": condition, "logical_call_id": record["logical_call_id"], "request_hash": record["request_hash"], "response_sha256": record["raw_response_sha256"], "contract_valid": parsed is not None, "contract_error": error, "declared_skill_applicability": parsed["declared_skill_applicability"] if parsed else None, "selected_skill_id": parsed["selected_skill_id"] if parsed else None, "intermediate_operation": parsed["intermediate_operation"] if parsed else None, "final_answer": answer, "primary_uptake": used, "strict_correct": strict_correct, "alias_tolerant_correct": alias_correct})
    if any(set(row) != set(CONDITIONS) for row in uptake.values()): raise RuntimeError("Phase 3B task grid incomplete")
    uptake_counts = {c: sum(r[c] for r in uptake.values()) for c in CONDITIONS}; uptake_rates = {c: uptake_counts[c]/60 for c in CONDITIONS}; uptake_pair = pair(uptake,"contextual_typed_prior","shuffled_typed_prior")
    strict_counts = {c: sum(r[c] for r in strict.values()) for c in CONDITIONS}; alias_counts = {c: sum(r[c] for r in alias.values()) for c in CONDITIONS}
    strict_pair, alias_pair, alias_cold = pair(strict,"contextual_typed_prior","shuffled_typed_prior"), pair(alias,"contextual_typed_prior","shuffled_typed_prior"), pair(alias,"contextual_typed_prior","cold")
    families = sorted({str(t["skill_family"]) for t in tasks.values()}); family_uptake = {}
    for family in families:
        ids = {i for i,t in tasks.items() if t["skill_family"] == family}; contextual = sum(uptake[i]["contextual_typed_prior"] for i in ids); shuffled = sum(uptake[i]["shuffled_typed_prior"] for i in ids)
        family_uptake[family] = {"tasks": len(ids), "contextual": contextual, "shuffled": shuffled, "difference": (contextual-shuffled)/len(ids)}
    positive_families = sum(r["difference"] > 0 for r in family_uptake.values()); rules = plan["positive_gate"]
    positive = uptake_rates["contextual_typed_prior"] >= rules["contextual_uptake_rate_at_least"] and uptake_pair["rate_difference"] >= rules["contextual_minus_shuffled_uptake_rate_at_least"] and positive_families >= rules["families_with_positive_contextual_minus_shuffled_uptake_at_least"] and alias_pair["net_wins"] >= rules["contextual_alias_net_wins_over_shuffled_at_least"] and (-alias_cold["net_wins"]) <= rules["contextual_alias_net_loss_vs_cold_at_most"]
    nr = plan["negative_gate"]; negative = (uptake_rates["contextual_typed_prior"] < nr["contextual_uptake_rate_below"] or uptake_pair["rate_difference"] <= nr["or_contextual_minus_shuffled_uptake_rate_at_most"]) and alias_pair["net_wins"] <= nr["and_contextual_alias_net_wins_over_shuffled_at_most"]
    gate = "positive" if positive else "negative" if negative else "inconclusive"; stop = uptake_rates["contextual_typed_prior"] < .15 or uptake_pair["rate_difference"] < .05
    result = {"schema_version": 2, "status": "complete", "tasks": 60, "rows": 300, "completed_calls": 300, "contract_valid_rows": valid, "contract_invalid_rows": 300-valid, "uptake_counts": uptake_counts, "uptake_rates": uptake_rates, "contextual_vs_shuffled_uptake": uptake_pair, "family_uptake": family_uptake, "families_with_positive_contextual_minus_shuffled_uptake": positive_families, "strict_correct_counts": strict_counts, "alias_tolerant_correct_counts": alias_counts, "strict_contextual_vs_shuffled": strict_pair, "alias_contextual_vs_shuffled": alias_pair, "alias_contextual_vs_cold": alias_cold, "decision_gate": gate, "stop_rule_fired": stop, "scale_up_allowed": gate == "positive" and not stop, "analysis_plan": plan, "phase2_gate_preserved": "inconclusive", "provider_attempts": run_audit["provider_attempts"], "exact_stage_cost_cny": run_audit["exact_stage_cost_cny"], "later_stage_calls": 0, "formal_scaling_calls": 0, "bindings": {"gold_sha256": sha256_file(GOLD), "schedule_sha256": sha256_file(SCHEDULE), "analysis_plan_sha256": sha256_file(PLAN), "ledger_sha256": sha256_file(LEDGER), "run_audit_sha256": sha256_file(RUN_AUDIT)}, "outcomes": outcomes}
    result["aggregate_fingerprint"] = stable(result); return result


def report_text(result: dict[str,Any]) -> str:
    u,p,a = result["uptake_rates"], result["contextual_vs_shuffled_uptake"], result["alias_contextual_vs_shuffled"]
    return "# ACL 2027 Phase 3B activation live v2\n\n" + f"The exact 60-task, 300-call grid completed with `{result['contract_valid_rows']}/300` contract-valid responses. Contextual typed uptake was `{u['contextual_typed_prior']:.4f}` and shuffled typed uptake was `{u['shuffled_typed_prior']:.4f}`, a paired difference of `{p['rate_difference']:+.4f}`.\n\n" + f"Alias-tolerant contextual-versus-shuffled net wins were `{a['net_wins']}`. Frozen decision gate: **{result['decision_gate']}**. Stop rule fired: `{result['stop_rule_fired']}`. Scale-up allowed: `{result['scale_up_allowed']}`.\n\n" + f"Exact stage cost was CNY `{result['exact_stage_cost_cny']}`. Phase 2 remains inconclusive and no later stage or formal scaling is authorized.\n\nAggregate fingerprint: `{result['aggregate_fingerprint']}`.\n"


if __name__ == "__main__":
    result = analyze(); AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2)+"\n", encoding="utf-8", newline="\n"); REPORT.write_text(report_text(result), encoding="utf-8", newline="\n"); print(json.dumps(result, indent=2, sort_keys=True))
