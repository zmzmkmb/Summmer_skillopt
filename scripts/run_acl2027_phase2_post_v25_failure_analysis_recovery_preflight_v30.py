#!/usr/bin/env python3
"""Freeze a second zero-network recovery after terminal v29 execution."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import CONDITIONS, SYSTEM, public_task, source_candidates
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import V17_PRIORS, condition_prior, occupied_tasks

VERSION = 30
RECOVERY_CALLS = 220
CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_recovery_preflight_v30.json"
V27 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27"
V28 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v28"
V29 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_live_v29"
V27_LEDGER = V27 / "ledger.json"
V27_CORRECTED = V27 / "run_audit_v27_1.json"
V28_SCHEDULE = V28 / "failure_analysis_recovery_schedule.json"
V28_GOLD = V28 / "combined_private_gold.json"
V29_LEDGER = V29 / "ledger.json"
V29_STARTS = V29 / "request_start_ledger.json"
V29_AUDIT = V29 / "run_audit.json"
V29_CLOSURE = V29 / "authorization_closure.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v30"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v25_failure_analysis_recovery_preflight_v30.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(value), encoding="utf-8", newline="\n")


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase2-v30:second-recovery:{family}:{task_id}".encode()).hexdigest()


def select_replacement(family: str, excluded: set[str]) -> dict[str, Any]:
    candidates = [row for row in source_candidates()[family] if str(row["task_id"]) not in excluded]
    if not candidates:
        raise RuntimeError("no unused v30 replacement task")
    return copy.deepcopy(min(candidates, key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"]))))


def build_row(task: dict[str, Any], condition: str, sequence: int, source: str) -> dict[str, Any]:
    bundles = load(V17_PRIORS)
    family = str(task["skill_family"])
    candidate_id, prior = condition_prior(condition, family, bundles)
    public = public_task(task)
    body = {"model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "phase": "2", "stage": "post_v25_failure_analysis_second_recovery", "partition": "independent_failure_analysis_held_out_second_recovery", "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family, "task_id": task["task_id"], "public_payload_sha256": stable(public), "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v30-recovery", "typed_scope": family, "prompt_template_version": "phase2-post-v25-failure-analysis-json-v30", "prior_payload_sha256": stable(prior), "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Prior bundle:\n" + json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)}]}
    return {"schema_version": VERSION, "sequence": sequence, "staged_execution_index": sequence, "logical_call_id": f"phase2-v30:post_v25_failure_analysis_second_recovery:{family}:{task['task_id']}:{condition}", "request_hash": stable(body), "provider_response_id": None, "partition": body["partition"], "stage": body["stage"], "task_id": task["task_id"], "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family, "condition": condition, "candidate_id": candidate_id, "prior_payload_sha256": body["prior_payload_sha256"], "public_payload_sha256": body["public_payload_sha256"], "canonical_request_body": body, "provenance": {"recovery_source": source, "gold_is_not_request": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}, "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True}}


def complete_task_ids(records: list[dict[str, Any]]) -> set[str]:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_task.setdefault(str(record["task_id"]), []).append(record)
    return {task_id for task_id, rows in by_task.items() if len(rows) == 4 and all(row.get("status") == "completed" for row in rows)}


def build_plan() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    v27, v29 = load(V27_LEDGER), load(V29_LEDGER)
    planned, gold = load(V28_SCHEDULE)["schedule"], load(V28_GOLD)
    terminal = v29[-1]
    reusable_v27 = complete_task_ids(v27)
    reusable_v29 = complete_task_ids(v29)
    if len(reusable_v27) != 268 or len(reusable_v29) != 77:
        raise RuntimeError("v30 reusable task-grid partition drift")
    terminal_task = str(terminal["task_id"])
    if terminal_task in reusable_v29:
        raise RuntimeError("v29 terminal task must be excluded")
    task_map = {str(task["task_id"]): task for task in gold}
    untouched_ids: list[str] = []
    for row in planned:
        task_id = str(row["task_id"])
        if row["staged_execution_index"] > 312 and task_id != terminal_task and task_id not in untouched_ids:
            untouched_ids.append(task_id)
    if len(untouched_ids) != 54:
        raise RuntimeError("v30 untouched task partition drift")
    excluded = occupied_tasks() | set(task_map)
    replacement = select_replacement(str(terminal["skill_family"]), excluded)
    recovery_tasks = [task_map[task_id] for task_id in untouched_ids] + [replacement]
    rows: list[dict[str, Any]] = []
    for task in recovery_tasks:
        source = "v28_never_attempted_complete_task" if str(task["task_id"]) in task_map else "v30_deterministic_replacement"
        for condition in CONDITIONS:
            rows.append(build_row(task, condition, len(rows) + 1, source))
    combined_gold = [task for task in gold if str(task["task_id"]) != terminal_task] + [replacement]
    provenance = {"v27_attempted_rows": len(v27), "v27_reusable_completed_tasks": len(reusable_v27), "v27_reusable_completed_rows": len(reusable_v27) * 4, "v29_attempted_rows": len(v29), "v29_completed_rows": sum(row.get("status") == "completed" for row in v29), "v29_terminal_rows": sum(bool(row.get("terminal")) for row in v29), "v29_reusable_completed_tasks": len(reusable_v29), "v29_reusable_completed_rows": len(reusable_v29) * 4, "v29_orphan_completed_rows_excluded": 1, "excluded_terminal_task_id": terminal_task, "excluded_terminal_logical_call_id": terminal["logical_call_id"], "unattempted_complete_tasks_carried": len(untouched_ids), "replacement_task_id": replacement["task_id"], "replacement_skill_family": replacement["skill_family"], "replacement_selector_hash": selector_hash(str(replacement["skill_family"]), str(replacement["task_id"]))}
    return rows, combined_gold, provenance


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("v30 execution switches must remain closed")
    v29_audit, v29_closure = load(V29_AUDIT), load(V29_CLOSURE)
    if v29_audit.get("status") != "terminal_hard_stop" or v29_audit.get("authorization_closed") is not True or v29_closure.get("status") != "closed":
        raise RuntimeError("v29 terminal closure drift")
    rows, gold, provenance = build_plan()
    spent = load(V27_LEDGER) + load(V29_LEDGER)
    if len(rows) != RECOVERY_CALLS or len({row["logical_call_id"] for row in rows}) != RECOVERY_CALLS or len({row["request_hash"] for row in rows}) != RECOVERY_CALLS:
        raise RuntimeError("v30 recovery identity drift")
    if {row["logical_call_id"] for row in rows} & {row["logical_call_id"] for row in spent} or {row["request_hash"] for row in rows} & {row["request_hash"] for row in spent}:
        raise RuntimeError("v30 retries a spent request")
    if len(gold) != 400 or len({str(task["task_id"]) for task in gold}) != 400:
        raise RuntimeError("v30 combined gold drift")
    complete_v27 = [row for row in load(V27_LEDGER) if row.get("status") == "completed"]
    reusable_v29_ids = complete_task_ids(load(V29_LEDGER))
    complete_v29 = [row for row in load(V29_LEDGER) if row.get("status") == "completed" and str(row["task_id"]) in reusable_v29_ids]
    combined = complete_v27 + complete_v29 + rows
    if len(combined) != 1600 or len({(row["task_id"], row["condition"]) for row in combined}) != 1600:
        raise RuntimeError("v30 combined 400x4 grid drift")
    counts = {condition: sum(row["condition"] == condition for row in combined) for condition in CONDITIONS}
    if any(value != 400 for value in counts.values()):
        raise RuntimeError("v30 combined condition balance drift")
    proposed = cfg["proposed_authorization"]
    if proposed["requested_calls"] != RECOVERY_CALLS or proposed["status"] != "fresh_explicit_user_authorization_required":
        raise RuntimeError("v30 authorization proposal drift")
    result = {"schema_version": VERSION, "experiment": cfg["experiment"], "status": "preflight-passed-recovery-plan-closed", "authorization_request_status": "fresh_explicit_user_authorization_required", "execution": cfg["execution"], "provenance": provenance, "recovery_calls": len(rows), "recovery_tasks": len({row["task_id"] for row in rows}), "combined_analysis_rows": len(combined), "combined_task_count": len(gold), "combined_condition_counts": counts, "spent_v27_v29_requests_excluded": len(spent), "all_recovery_logical_ids_new": True, "all_recovery_request_hashes_new": True, "analysis_gate_reached": False, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0, "proposed_authorization": proposed, "bindings": {"v27_ledger_sha256": sha256_file(V27_LEDGER), "v27_corrected_audit_sha256": sha256_file(V27_CORRECTED), "v28_schedule_sha256": sha256_file(V28_SCHEDULE), "v28_gold_sha256": sha256_file(V28_GOLD), "v29_ledger_sha256": sha256_file(V29_LEDGER), "v29_request_start_ledger_sha256": sha256_file(V29_STARTS), "v29_run_audit_sha256": sha256_file(V29_AUDIT), "v29_closure_sha256": sha256_file(V29_CLOSURE), "recovery_schedule_canonical_sha256": stable(rows), "combined_gold_canonical_sha256": stable(gold)}}
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    rows, gold, provenance = build_plan()
    ARTIFACT.mkdir(parents=True, exist_ok=False)
    write(ARTIFACT / "v27_v29_provenance_audit.json", provenance)
    write(ARTIFACT / "second_recovery_schedule.json", {"schema_version": VERSION, "schedule": rows})
    write(ARTIFACT / "combined_private_gold.json", gold)
    write(ARTIFACT / "run_manifest.json", result)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# ACL 2027 Phase 2 v30 second recovery preflight\n\nThis zero-network preflight preserves 1,380 completed rows from 345 complete task grids, excludes all 1,383 spent v27/v29 requests, replaces the incomplete v29 terminal task, and freezes 220 new requests. No authorization was opened.\n\n" + render(result), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        write_artifact(result)
    print(render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
