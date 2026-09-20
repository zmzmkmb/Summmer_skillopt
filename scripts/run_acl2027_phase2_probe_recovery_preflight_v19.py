#!/usr/bin/env python3
"""Zero-network recovery preflight for the terminal Phase 2 v18 probe run."""
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

from scripts.prepare_acl2027_phase2_payload_and_freeze_v2 import make_payload, prior_exclusions
from scripts.run_acl2027_phase2_probe_identifiable_schedule_preflight_v17 import (
    CONDITIONS,
    FAMILIES,
    SYSTEM,
    build_prior_bundles,
    condition_prior,
    load as load_json,
)
from scripts.acl2027_phase2_integrity_v4 import verify_integrity

CONFIG = ROOT / "configs/acl2027/phase2_probe_recovery_preflight_v19.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
V17_CONFIG = ROOT / "configs/acl2027/phase2_probe_identifiable_schedule_preflight_v17.json"
V17_ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17"
V17_MANIFEST = V17_ARTIFACT / "run_manifest.json"
V17_SCHEDULE = V17_ARTIFACT / "probe_schedule.json"
V17_PRIORS = V17_ARTIFACT / "prior_bundles.json"
V17_GOLD = V17_ARTIFACT / "replacement_probe_gold.json"
V18_CONFIG = ROOT / "configs/acl2027/phase2_probe_only_live_authorization_v18.json"
V18_CLOSED = ROOT / "configs/acl2027/phase2_probe_only_live_authorization_closed_v18.json"
V18_ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_only_live_v18"
V18_LEDGER = V18_ARTIFACT / "ledger.json"
V18_STARTS = V18_ARTIFACT / "request_start_ledger.json"
V18_AUDIT = V18_ARTIFACT / "run_audit.json"
V18_CLOSURE = V18_ARTIFACT / "authorization_closure.json"
V18_SCHEDULE = V17_SCHEDULE
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19"
REPORT = ROOT / "paper/acl2027/results/phase2_probe_recovery_preflight_v19.md"

VERSION = 19
RECOVERY_CALLS = 112
RECOVERY_TASKS = 28
RECOVERY_AUTH_PROPOSAL = {
    "scope": "probe_only",
    "requested_calls": RECOVERY_CALLS,
    "max_provider_attempts": RECOVERY_CALLS,
    "model_id": "qwen3.7-plus",
    "temperature": 0,
    "retries": 0,
    "max_tokens_present": False,
    "response_format": {"type": "json_object"},
    "stage_cost_ceiling_cny": 7.50,
    "cumulative_cost_ceiling_cny": 7.50,
    "held_out_authorized": False,
    "later_stages_authorized": False,
    "formal_scaling_authorized": False,
    "status": "fresh_explicit_authorization_required",
}


def stable(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(value), encoding="utf-8", newline="\n")


def select_replacement(v17_gold: list[dict[str, Any]]) -> dict[str, Any]:
    """Select one unused 2Wiki comparison task, excluding every v17 probe task."""
    excluded = set(prior_exclusions()["2WikiMultiHopQA"])
    excluded.update(str(row["task_id"]) for row in v17_gold)
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for row in load(ROOT / "data/2wikimultihopqa_verified/source/dev.json"):
        task_id = str(row.get("_id", ""))
        if (
            task_id in excluded
            or row.get("type") != "comparison"
            or not row.get("question")
            or not row.get("context")
            or row.get("answer") is None
            or not row.get("supporting_facts")
        ):
            continue
        payload = make_payload(row, "2WikiMultiHopQA", "attribute_comparison", "dev")
        key = hashlib.sha256(f"phase2-v19:probe-recovery-replacement:attribute_comparison:{task_id}".encode()).hexdigest()
        candidates.append((key, task_id, payload))
    if not candidates:
        raise RuntimeError("no unused attribute-comparison recovery task")
    key, task_id, payload = min(candidates)
    return {
        "selector": "min SHA256(phase2-v19:probe-recovery-replacement:attribute_comparison:<task_id>)",
        "candidate_pool_size": len(candidates),
        "replacement_task_id": task_id,
        "replacement_selector_hash": key,
        "replacement_payload_hash": stable(payload),
        "replacement_source_split": payload["source_split"],
        "replacement_not_in_any_prior_or_v17_probe": task_id not in excluded,
        "payload": payload,
    }


def validate_v18_provenance() -> dict[str, Any]:
    config = load(CONFIG)
    v18_open = load(V18_CONFIG)
    v18_closed = load(V18_CLOSED)
    audit = load(V18_AUDIT)
    closure = load(V18_CLOSURE)
    ledger = load(V18_LEDGER)
    starts = load(V18_STARTS)
    planned = load(V18_SCHEDULE)["schedule"]
    if any(config["execution"].get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise RuntimeError("v19 execution switches must remain closed")
    for name, path in config["bindings"].items():
        if name.endswith("_sha256") and sha256_file(_binding_path(name)) != path:
            raise RuntimeError(f"v19 source binding drift: {name}")
    if v18_open.get("status") != "open" or v18_closed.get("status") != "closed" or closure.get("status") != "closed":
        raise RuntimeError("v18 authorization closure drift")
    if any(v18_closed.get(key) is not False for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise RuntimeError("v18 closed authorization boundary drift")
    if len(ledger) != 50 or len(starts) != 50 or audit.get("status") != "terminal_hard_stop" or audit.get("authorization_closed") is not True:
        raise RuntimeError("v18 terminal ledger/audit drift")
    logical_to_plan = {row["logical_call_id"]: row for row in planned}
    for index, (record, start) in enumerate(zip(ledger, starts), 1):
        planned_row = logical_to_plan.get(record.get("logical_call_id"))
        if planned_row is None or record.get("request_hash") != planned_row.get("request_hash") or start.get("request_hash") != planned_row.get("request_hash"):
            raise RuntimeError("v18 ledger/schedule provenance drift")
        if record.get("provider_attempt_index") != index or record.get("retries") != 0 or record.get("staged_execution_index") != index:
            raise RuntimeError("v18 exact-prefix provenance drift")
        if record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}):
            raise RuntimeError("v18 ledger hash drift")
    if not ledger[-1].get("terminal") or sum(record.get("status") == "completed" for record in ledger) != 49:
        raise RuntimeError("v18 terminal/completed counts drift")
    completed = [record for record in ledger if record.get("status") == "completed"]
    by_task: dict[str, list[dict[str, Any]]] = {}
    for record in ledger:
        by_task.setdefault(record["task_id"], []).append(record)
    reusable_tasks = sorted(task_id for task_id, rows in by_task.items() if len([row for row in rows if row.get("status") == "completed"]) == 4 and not any(row.get("terminal") for row in rows))
    excluded_tasks = sorted(task_id for task_id, rows in by_task.items() if task_id not in reusable_tasks)
    unattempted = [row for row in planned if row["logical_call_id"] not in logical_to_plan or row["logical_call_id"] not in {record["logical_call_id"] for record in ledger}]
    carry = [row for row in unattempted if row["task_id"] not in excluded_tasks]
    if len(reusable_tasks) != 12 or len(excluded_tasks) != 1 or len(carry) != 108:
        raise RuntimeError("v18 reusable/carry-forward partition drift")
    return {
        "v18_rows": len(ledger),
        "v18_completed_rows": len(completed),
        "v18_terminal_rows": sum(bool(row.get("terminal")) for row in ledger),
        "v18_unattempted_rows": len(unattempted),
        "reusable_completed_rows": sum(1 for row in completed if row["task_id"] in reusable_tasks),
        "orphan_completed_rows": sum(1 for row in completed if row["task_id"] in excluded_tasks),
        "carry_forward_rows": len(carry),
        "reusable_task_ids": reusable_tasks,
        "excluded_task_ids": excluded_tasks,
        "terminal_logical_call_id": ledger[-1]["logical_call_id"],
        "terminal_request_hash": ledger[-1]["request_hash"],
        "v18_ledger_sha256": sha256_file(V18_LEDGER),
        "v18_request_start_ledger_sha256": sha256_file(V18_STARTS),
        "v18_run_audit_sha256": sha256_file(V18_AUDIT),
        "v18_closure_sha256": sha256_file(V18_CLOSURE),
    }


def _binding_path(name: str) -> Path:
    return {
        "v4_manifest_sha256": V4_MANIFEST,
        "v17_config_sha256": V17_CONFIG,
        "v17_manifest_sha256": V17_MANIFEST,
        "v17_schedule_sha256": V17_SCHEDULE,
        "v17_prior_bundles_sha256": V17_PRIORS,
        "v17_gold_sha256": V17_GOLD,
        "v18_open_authorization_sha256": V18_CONFIG,
        "v18_closed_authorization_sha256": V18_CLOSED,
        "v18_ledger_sha256": V18_LEDGER,
        "v18_request_start_ledger_sha256": V18_STARTS,
        "v18_run_audit_sha256": V18_AUDIT,
        "v18_closure_sha256": V18_CLOSURE,
    }[name]


def build_schedule(v17_gold: list[dict[str, Any]], replacement: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    v17_rows = load(V17_SCHEDULE)["schedule"]
    spent_task = load(V18_LEDGER)[-1]["task_id"]
    carry = [row for row in v17_rows if row["task_id"] != spent_task and row["staged_execution_index"] > 50]
    if len(carry) != 108:
        raise RuntimeError("v19 carry-forward schedule must contain 108 unattempted rows")
    bundles = load(V17_PRIORS)
    gold = [copy.deepcopy(row) for row in v17_gold if row["task_id"] != spent_task]
    gold.append(copy.deepcopy(replacement["payload"]))
    if len(gold) != 40 or len({row["task_id"] for row in gold}) != 40:
        raise RuntimeError("v19 replacement gold must contain 40 unique tasks")
    rows: list[dict[str, Any]] = []

    def add_from_v17(source: dict[str, Any]) -> None:
        index = len(rows) + 1
        body = copy.deepcopy(source["canonical_request_body"])
        body["candidate_version"] = "phase2-v19-recovery"
        body["prompt_template_version"] = "phase2-probe-identifiable-json-v19"
        row = copy.deepcopy(source)
        row.update({
            "schema_version": VERSION,
            "sequence": index,
            "staged_execution_index": index,
            "logical_call_id": f"phase2-v19:probe:{source['skill_family']}:{source['task_id']}:{source['condition']}",
            "request_hash": stable(body),
            "candidate_version": "phase2-v19-recovery",
            "prompt_template_version": "phase2-probe-identifiable-json-v19",
            "canonical_request_body": body,
            "provenance": {**source["provenance"], "recovery_source": "v18_unattempted_suffix", "replacement_selected_by_v19": False, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
        })
        rows.append(row)

    for source in carry:
        add_from_v17(source)

    replacement_task = replacement["payload"]
    for condition in CONDITIONS:
        index = len(rows) + 1
        candidate_id, prior = condition_prior(condition, replacement_task["skill_family"], bundles)
        payload_hash = stable(replacement_task)
        prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        user = "Prior bundle:\n" + prior_text + "\n\nQuestion:\n" + replacement_task["question"] + "\n\nContext:\n" + json.dumps(replacement_task["context"], ensure_ascii=True)
        body = {
            "model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"},
            "phase": "2", "stage": "Stage 5", "partition": "probe", "task_family": replacement_task["task_family"],
            "task_type": replacement_task["task_type"], "skill_family": replacement_task["skill_family"], "task_id": replacement_task["task_id"],
            "payload_hash": payload_hash, "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v19-recovery",
            "typed_scope": replacement_task["skill_family"], "prompt_template_version": "phase2-probe-identifiable-json-v19",
            "prior_payload_sha256": stable(prior), "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        }
        rows.append({
            "schema_version": VERSION, "sequence": index, "staged_execution_index": index,
            "logical_call_id": f"phase2-v19:probe:{replacement_task['skill_family']}:{replacement_task['task_id']}:{condition}",
            "request_hash": stable(body), "partition": "probe", "stage": "Stage 5", "task_id": replacement_task["task_id"],
            "task_family": replacement_task["task_family"], "task_type": replacement_task["task_type"], "skill_family": replacement_task["skill_family"],
            "typed_scope": replacement_task["skill_family"], "payload_hash": payload_hash, "condition": condition, "candidate_id": candidate_id,
            "candidate_version": "phase2-v19-recovery", "prompt_template_version": "phase2-probe-identifiable-json-v19",
            "prior_payload_sha256": body["prior_payload_sha256"], "canonical_request_body": body,
            "provenance": {"source_dataset": "2WikiMultiHopQA", "source_record_id": replacement_task["task_id"], "payload_source": "dev", "gold_is_not_request": True, "replacement_selected_by_v19": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
            "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
        })
    return rows, gold


def validate() -> dict[str, Any]:
    config = load(CONFIG)
    v17_manifest = load(V17_MANIFEST)
    v4_manifest = load(V4_MANIFEST)
    v17_gold = load(V17_GOLD)
    provenance = validate_v18_provenance()
    verify_integrity(V4_CONFIG, V4_MANIFEST, root=ROOT)
    if v4_manifest.get("aggregate_fingerprint") != config["bindings"]["v4_aggregate_fingerprint"] or v17_manifest.get("aggregate_fingerprint") != config["bindings"]["v17_aggregate_fingerprint"]:
        raise RuntimeError("v4/v17 acceptance fingerprint drift")
    replacement = select_replacement(v17_gold)
    rows, gold = build_schedule(v17_gold, replacement)
    if len(rows) != RECOVERY_CALLS or len({row["logical_call_id"] for row in rows}) != RECOVERY_CALLS or len({row["request_hash"] for row in rows}) != RECOVERY_CALLS:
        raise RuntimeError("v19 recovery schedule identity drift")
    spent_records = load(V18_LEDGER)
    spent_logical = {row["logical_call_id"] for row in spent_records}
    spent_hashes = {row["request_hash"] for row in spent_records}
    v17_rows = load(V17_SCHEDULE)["schedule"]
    if spent_logical & {row["logical_call_id"] for row in rows} or spent_hashes & {row["request_hash"] for row in rows}:
        raise RuntimeError("v19 schedule retries a spent v18 request")
    if {row["logical_call_id"] for row in v17_rows} & {row["logical_call_id"] for row in rows} or {row["request_hash"] for row in v17_rows} & {row["request_hash"] for row in rows}:
        raise RuntimeError("v19 schedule reuses v17 request identity")
    if [row["staged_execution_index"] for row in rows] != list(range(1, RECOVERY_CALLS + 1)):
        raise RuntimeError("v19 stage prefix drift")
    if any("max_tokens" in row["canonical_request_body"] or row["canonical_request_body"].get("model_id") != "qwen3.7-plus" or row["canonical_request_body"].get("temperature") != 0 or row["canonical_request_body"].get("response_format") != {"type": "json_object"} or row["canonical_request_body"].get("enable_thinking") is not False for row in rows):
        raise RuntimeError("v19 route/model boundary drift")
    condition_counts = {condition: sum(row["condition"] == condition for row in rows) for condition in CONDITIONS}
    combined = [record for record in load(V18_LEDGER) if record.get("status") == "completed" and record["task_id"] in provenance["reusable_task_ids"]] + rows
    combined_keys = {(row["task_id"], row["condition"]) for row in combined}
    if len(combined) != 160 or len(combined_keys) != 160 or any(sum(row["task_id"] == task["task_id"] for row in combined) != 4 for task in gold):
        raise RuntimeError("v19 combined 40x4 grid drift")
    if any(sum(row["condition"] == condition for row in combined) != 40 for condition in CONDITIONS):
        raise RuntimeError("v19 combined condition balance drift")
    support_ids = {example["task_id"] for example in load(V17_PRIORS)["global"]["examples"]}
    for bundle in load(V17_PRIORS)["typed"].values():
        support_ids.update(example["task_id"] for example in bundle["examples"])
    if support_ids & {row["task_id"] for row in gold}:
        raise RuntimeError("v19 prior/probe overlap")
    result = {
        "schema_version": VERSION,
        "experiment": "acl2027_phase2_probe_recovery_preflight_v19",
        "status": "preflight-passed-recovery-plan",
        "authorization_request_status": "fresh_explicit_authorization_required",
        "execution": {"network_calls_allowed": False, "provider_calls_allowed": False, "paid_api_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False},
        "v18_provenance": provenance,
        "recovery_calls": RECOVERY_CALLS,
        "combined_analysis_rows": len(combined),
        "combined_task_count": len(gold),
        "combined_condition_counts": {condition: sum(row["condition"] == condition for row in combined) for condition in CONDITIONS},
        "recovery_condition_counts": condition_counts,
        "replacement_selection": {key: value for key, value in replacement.items() if key != "payload"},
        "spent_v18_requests_excluded": len(spent_records),
        "all_recovery_logical_ids_new": True,
        "all_recovery_request_hashes_new": True,
        "coverage_gate_preserved": True,
        "private_gold_used_for_priors": False,
        "held_out_gold_used_for_priors": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "held_out_calls": 0,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "proposed_authorization": RECOVERY_AUTH_PROPOSAL,
        "bindings": {**config["bindings"], "v4_aggregate_fingerprint": v4_manifest["aggregate_fingerprint"], "v17_aggregate_fingerprint": v17_manifest["aggregate_fingerprint"], "recovery_schedule_canonical_sha256": stable(rows), "recovery_gold_canonical_sha256": stable(gold), "prior_bundles_canonical_sha256": stable(load(V17_PRIORS))},
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    v17_gold = load(V17_GOLD)
    replacement = select_replacement(v17_gold)
    rows, gold = build_schedule(v17_gold, replacement)
    ARTIFACT.mkdir(parents=True, exist_ok=False)
    write(ARTIFACT / "v18_provenance_audit.json", {"manifest": result["v18_provenance"], "ledger_sha256": sha256_file(V18_LEDGER), "request_start_ledger_sha256": sha256_file(V18_STARTS)})
    write(ARTIFACT / "probe_recovery_schedule.json", {"schema_version": VERSION, "schedule": rows})
    write(ARTIFACT / "recovery_probe_gold.json", gold)
    write(ARTIFACT / "prior_bundles.json", load(V17_PRIORS))
    write(ARTIFACT / "run_manifest.json", result)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# ACL 2027 Phase 2 v19 probe recovery preflight\n\n" + "This was a zero-network recovery preflight. It preserves v18 provenance, excludes all 50 spent v18 requests, and freezes a 112-call replacement plan. No provider authorization was opened.\n\n" + json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        write_artifact(result)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
