#!/usr/bin/env python3
"""Freeze a zero-network recovery plan after terminal v27 execution."""
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
from scripts.audit_acl2027_phase2_post_v25_failure_analysis_v27_1 import build as corrected_audit
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import CONDITIONS, SYSTEM, public_task, source_candidates
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import V17_PRIORS, condition_prior

VERSION = 28
CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_recovery_preflight_v28.json"
V26_ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_design_preflight_v26"
V26_MANIFEST = V26_ARTIFACT / "run_manifest.json"
V26_SCHEDULE = V26_ARTIFACT / "future_schedule.json"
V26_GOLD = V26_ARTIFACT / "future_private_gold.json"
V27_ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27"
V27_LEDGER = V27_ARTIFACT / "ledger.json"
V27_STARTS = V27_ARTIFACT / "request_start_ledger.json"
V27_CLOSURE = V27_ARTIFACT / "authorization_closure.json"
V27_CORRECTED = V27_ARTIFACT / "run_audit_v27_1.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v28"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v25_failure_analysis_recovery_preflight_v28.md"
RECOVERY_CALLS = 528


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(value), encoding="utf-8", newline="\n")


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase2-v28:failure-analysis-recovery:{family}:{task_id}".encode()).hexdigest()


def select_replacement(family: str, excluded: set[str]) -> dict[str, Any]:
    candidates = [row for row in source_candidates()[family] if str(row["task_id"]) not in excluded]
    if not candidates:
        raise RuntimeError("no unused v28 replacement task")
    selected = min(candidates, key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])))
    return copy.deepcopy(selected)


def build_row(task: dict[str, Any], condition: str, sequence: int, source: str) -> dict[str, Any]:
    bundles = load(V17_PRIORS)
    family = str(task["skill_family"])
    candidate_id, prior = condition_prior(condition, family, bundles)
    public = public_task(task)
    body = {
        "model_id": "qwen3.7-plus",
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "phase": "2",
        "stage": "post_v25_failure_analysis_recovery",
        "partition": "independent_failure_analysis_held_out_recovery",
        "task_family": task["task_family"],
        "task_type": task["task_type"],
        "skill_family": family,
        "task_id": task["task_id"],
        "public_payload_sha256": stable(public),
        "condition": condition,
        "candidate_id": candidate_id,
        "candidate_version": "phase2-v28-recovery",
        "typed_scope": family,
        "prompt_template_version": "phase2-post-v25-failure-analysis-json-v28",
        "prior_payload_sha256": stable(prior),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Prior bundle:\n" + json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)},
        ],
    }
    return {
        "schema_version": VERSION,
        "sequence": sequence,
        "staged_execution_index": sequence,
        "logical_call_id": f"phase2-v28:post_v25_failure_analysis_recovery:{family}:{task['task_id']}:{condition}",
        "request_hash": stable(body),
        "provider_response_id": None,
        "partition": body["partition"],
        "stage": body["stage"],
        "task_id": task["task_id"],
        "task_family": task["task_family"],
        "task_type": task["task_type"],
        "skill_family": family,
        "condition": condition,
        "candidate_id": candidate_id,
        "prior_payload_sha256": body["prior_payload_sha256"],
        "public_payload_sha256": body["public_payload_sha256"],
        "canonical_request_body": body,
        "provenance": {"recovery_source": source, "gold_is_not_request": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
        "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
    }


def build_plan() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    schedule, gold, ledger = load(V26_SCHEDULE)["schedule"], load(V26_GOLD), load(V27_LEDGER)
    terminal = ledger[-1]
    terminal_task = terminal["task_id"]
    by_task: dict[str, list[dict[str, Any]]] = {}
    for record in ledger:
        by_task.setdefault(record["task_id"], []).append(record)
    reusable = {task_id for task_id, rows in by_task.items() if len(rows) == 4 and all(row.get("status") == "completed" for row in rows)}
    if len(reusable) != 268 or terminal_task in reusable:
        raise RuntimeError("v27 reusable task-grid partition drift")
    task_map = {str(task["task_id"]): task for task in gold}
    untouched_ids = []
    for row in schedule:
        task_id = str(row["task_id"])
        if row["staged_execution_index"] > 1073 and task_id != terminal_task and task_id not in untouched_ids:
            untouched_ids.append(task_id)
    if len(untouched_ids) != 131:
        raise RuntimeError("v28 untouched task partition drift")
    excluded = set(task_map)
    replacement = select_replacement(str(terminal["skill_family"]), excluded)
    recovery_tasks = [task_map[task_id] for task_id in untouched_ids] + [replacement]
    rows: list[dict[str, Any]] = []
    for task in recovery_tasks:
        source = "v26_unattempted_complete_task" if str(task["task_id"]) in task_map else "v28_deterministic_replacement"
        for condition in CONDITIONS:
            rows.append(build_row(task, condition, len(rows) + 1, source))
    combined_gold = [task for task in gold if str(task["task_id"]) != terminal_task] + [replacement]
    provenance = {
        "v27_attempted_rows": len(ledger),
        "v27_completed_rows": sum(row.get("status") == "completed" for row in ledger),
        "v27_terminal_rows": sum(bool(row.get("terminal")) for row in ledger),
        "reusable_completed_tasks": len(reusable),
        "reusable_completed_rows": len(reusable) * 4,
        "excluded_terminal_task_id": terminal_task,
        "excluded_terminal_logical_call_id": terminal["logical_call_id"],
        "unattempted_complete_tasks_carried": len(untouched_ids),
        "replacement_task_id": replacement["task_id"],
        "replacement_skill_family": replacement["skill_family"],
        "replacement_selector_hash": selector_hash(str(replacement["skill_family"]), str(replacement["task_id"])),
    }
    return rows, combined_gold, provenance


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("v28 execution switches must remain closed")
    correction = corrected_audit()
    if correction["analysis_gate_reached"] is not False or correction["authorization_closed"] is not True:
        raise RuntimeError("v27 corrected terminal boundary drift")
    rows, gold, provenance = build_plan()
    spent = load(V27_LEDGER)
    spent_logical = {row["logical_call_id"] for row in spent}
    spent_hashes = {row["request_hash"] for row in spent}
    if len(rows) != RECOVERY_CALLS or len({row["logical_call_id"] for row in rows}) != RECOVERY_CALLS or len({row["request_hash"] for row in rows}) != RECOVERY_CALLS:
        raise RuntimeError("v28 recovery identity drift")
    if spent_logical & {row["logical_call_id"] for row in rows} or spent_hashes & {row["request_hash"] for row in rows}:
        raise RuntimeError("v28 retries a spent v27 request")
    if len(gold) != 400 or len({str(task["task_id"]) for task in gold}) != 400:
        raise RuntimeError("v28 combined task set drift")
    completed = [row for row in spent if row.get("status") == "completed" and row["task_id"] != provenance["excluded_terminal_task_id"]]
    combined = completed + rows
    if len(combined) != 1600 or len({(row["task_id"], row["condition"]) for row in combined}) != 1600:
        raise RuntimeError("v28 combined 400x4 grid drift")
    condition_counts = {condition: sum(row["condition"] == condition for row in combined) for condition in CONDITIONS}
    if any(value != 400 for value in condition_counts.values()):
        raise RuntimeError("v28 combined condition balance drift")
    proposed = cfg["proposed_authorization"]
    if proposed["requested_calls"] != RECOVERY_CALLS or proposed["status"] != "fresh_explicit_user_authorization_required":
        raise RuntimeError("v28 authorization proposal drift")
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "preflight-passed-recovery-plan-closed",
        "authorization_request_status": "fresh_explicit_user_authorization_required",
        "execution": cfg["execution"],
        "provenance": provenance,
        "recovery_calls": len(rows),
        "recovery_tasks": len({row["task_id"] for row in rows}),
        "combined_analysis_rows": len(combined),
        "combined_task_count": len(gold),
        "combined_condition_counts": condition_counts,
        "spent_v27_requests_excluded": len(spent),
        "all_recovery_logical_ids_new": True,
        "all_recovery_request_hashes_new": True,
        "analysis_gate_reached": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "proposed_authorization": proposed,
        "bindings": {
            "v26_manifest_sha256": sha256_file(V26_MANIFEST),
            "v26_schedule_sha256": sha256_file(V26_SCHEDULE),
            "v26_gold_sha256": sha256_file(V26_GOLD),
            "v27_ledger_sha256": sha256_file(V27_LEDGER),
            "v27_request_start_ledger_sha256": sha256_file(V27_STARTS),
            "v27_closure_sha256": sha256_file(V27_CLOSURE),
            "v27_corrected_audit_sha256": sha256_file(V27_CORRECTED) if V27_CORRECTED.exists() else stable(correction),
            "recovery_schedule_canonical_sha256": stable(rows),
            "combined_gold_canonical_sha256": stable(gold),
        },
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    rows, gold, provenance = build_plan()
    ARTIFACT.mkdir(parents=True, exist_ok=False)
    write(ARTIFACT / "v27_provenance_audit.json", provenance)
    write(ARTIFACT / "failure_analysis_recovery_schedule.json", {"schema_version": VERSION, "schedule": rows})
    write(ARTIFACT / "combined_private_gold.json", gold)
    write(ARTIFACT / "run_manifest.json", result)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# ACL 2027 Phase 2 v28 failure-analysis recovery preflight\n\nThis zero-network preflight preserves 1072 completed v27 rows from 268 complete task grids, excludes all 1073 spent v27 requests, replaces the incomplete terminal task, and freezes 528 new requests. No authorization was opened.\n\n" + render(result), encoding="utf-8", newline="\n")


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
