#!/usr/bin/env python3
"""Build and validate the zero-network Phase 2 v22 held-out recovery preflight."""
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

from scripts.acl2027_phase2_integrity_v4 import verify_integrity
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.prepare_acl2027_phase2_payload_and_freeze_v2 import make_payload, prior_exclusions

VERSION = 22
RECOVERY_CALLS = 88
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")
SYSTEM = ('Answer the question from the supplied context and optional prior bundle. Return exactly one JSON object and no other text, markdown, or explanation. The object must contain exactly one key named answer whose value is a non-empty short string. Required shape: {"answer":"<short answer>"}.')

CONFIG = ROOT / "configs/acl2027/phase2_heldout_recovery_preflight_v22.json"
AUTH_REQUEST = ROOT / "configs/acl2027/phase2_heldout_recovery_authorization_request_v22.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
V17_MANIFEST = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/run_manifest.json"
V17_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/probe_schedule.json"
V17_PRIORS = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/prior_bundles.json"
V17_GOLD = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/replacement_probe_gold.json"
V19_MANIFEST = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/run_manifest.json"
V19_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/probe_recovery_schedule.json"
V19_GOLD = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/recovery_probe_gold.json"
V20_PROBE_AUDIT = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/probe_audit.json"
V21_CONFIG = ROOT / "configs/acl2027/phase2_heldout_activation_preflight_v21.json"
V21_MANIFEST = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21/run_manifest.json"
V21_SCHEDULE = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21/held_out_schedule.json"
V21_PRIORS = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21/prior_bundles.json"
PHASE2_CALIBRATION_GOLD = ROOT / "data/searchqa_phase2_verified/calibration.json"
PHASE2_DEVELOPMENT_GOLD = ROOT / "data/searchqa_phase2_verified/development_acquisition.json"
PHASE2_FORMAL_HISTORY_GOLD = ROOT / "data/searchqa_phase2_verified/formal_history.json"
PHASE2_PROBE_GOLD = ROOT / "data/searchqa_phase2_verified/probe.json"
V21_GOLD = ROOT / "data/searchqa_phase2_verified/held_out.json"
V21_OPEN = ROOT / "configs/acl2027/phase2_heldout_live_authorization_v21.json"
V21_CLOSED = ROOT / "configs/acl2027/phase2_heldout_live_authorization_closed_v21.json"
V21_LIVE = ROOT / "artifacts/acl2027_phase2_heldout_live_v21"
V21_LEDGER = V21_LIVE / "ledger.json"
V21_STARTS = V21_LIVE / "request_start_ledger.json"
V21_RUN_AUDIT = V21_LIVE / "run_audit.json"
V21_CLOSURE = V21_LIVE / "authorization_closure.json"
V21_PARTIAL = V21_LIVE / "held_out_partial_audit.json"
SOURCE_DEV = ROOT / "data/2wikimultihopqa_verified/source/dev.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22"
REPORT = ROOT / "paper/acl2027/results/phase2_heldout_recovery_preflight_v22.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def source_paths() -> dict[str, Path]:
    return {
        "v4_config_sha256": V4_CONFIG, "v4_manifest_sha256": V4_MANIFEST,
        "v17_manifest_sha256": V17_MANIFEST, "v17_schedule_sha256": V17_SCHEDULE,
        "v17_prior_bundles_sha256": V17_PRIORS, "v19_manifest_sha256": V19_MANIFEST,
        "v19_schedule_sha256": V19_SCHEDULE, "v20_probe_audit_sha256": V20_PROBE_AUDIT,
        "v21_config_sha256": V21_CONFIG, "v21_manifest_sha256": V21_MANIFEST,
        "v21_schedule_sha256": V21_SCHEDULE, "v21_prior_bundles_sha256": V21_PRIORS,
        "phase2_calibration_gold_sha256": PHASE2_CALIBRATION_GOLD,
        "phase2_development_gold_sha256": PHASE2_DEVELOPMENT_GOLD,
        "phase2_formal_history_gold_sha256": PHASE2_FORMAL_HISTORY_GOLD,
        "phase2_probe_gold_sha256": PHASE2_PROBE_GOLD,
        "v21_gold_sha256": V21_GOLD, "v21_open_authorization_sha256": V21_OPEN,
        "v21_closed_authorization_sha256": V21_CLOSED, "v21_ledger_sha256": V21_LEDGER,
        "v21_request_start_ledger_sha256": V21_STARTS, "v21_run_audit_sha256": V21_RUN_AUDIT,
        "v21_closure_sha256": V21_CLOSURE, "v21_partial_audit_sha256": V21_PARTIAL,
        "replacement_source_dev_sha256": SOURCE_DEV,
    }


def condition_prior(condition: str, family: str, bundles: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if condition == "cold":
        return "candidate:none:v22", {"slot": "none", "source_scope": "none", "examples": []}
    if condition == "global_only":
        return bundles["global"]["candidate_id"], {"slot": "global", "source_scope": "global", "examples": bundles["global"]["examples"]}
    if condition == "copied_global":
        return f"candidate:copied-global:{family}:v22", {"slot": f"family:{family}", "source_scope": "global_copied", "examples": bundles["global"]["examples"]}
    typed = bundles["typed"][family]
    return typed["candidate_id"], {"slot": f"family:{family}", "source_scope": typed["source_scope"], "examples": typed["examples"]}


def validate_v21_provenance() -> dict[str, Any]:
    cfg = load(CONFIG)
    ledger, starts = load(V21_LEDGER), load(V21_STARTS)
    planned = load(V21_SCHEDULE)["schedule"]
    audit, closure, closed, partial = load(V21_RUN_AUDIT), load(V21_CLOSURE), load(V21_CLOSED), load(V21_PARTIAL)
    if any(cfg["execution"].get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise RuntimeError("v22 execution switches must remain closed")
    actual = {name: sha256_file(path) for name, path in source_paths().items()}
    if actual != cfg["bindings"]["source_files"]:
        raise RuntimeError("v22 source binding drift")
    verify_integrity(V4_CONFIG, V4_MANIFEST, root=ROOT)
    if load(V4_MANIFEST).get("aggregate_fingerprint") != cfg["bindings"]["v4_aggregate_fingerprint"]:
        raise RuntimeError("v4 aggregate fingerprint drift")
    if load(V21_MANIFEST).get("aggregate_fingerprint") != cfg["bindings"]["v21_aggregate_fingerprint"]:
        raise RuntimeError("v21 aggregate fingerprint drift")
    if partial.get("aggregate_fingerprint") != cfg["bindings"]["v21_partial_audit_fingerprint"]:
        raise RuntimeError("v21 partial audit fingerprint drift")
    if len(ledger) != 234 or len(starts) != 234 or audit.get("status") != "terminal_hard_stop":
        raise RuntimeError("v21 terminal prefix drift")
    if audit.get("completed_calls") != 233 or audit.get("provider_attempts") != 234 or audit.get("retries") != 0:
        raise RuntimeError("v21 attempt accounting drift")
    if closure.get("status") != "closed" or closed.get("status") != "closed" or closed.get("qwen_authorization_open") is not False:
        raise RuntimeError("v21 authorization closure drift")
    planned_by_id = {row["logical_call_id"]: row for row in planned}
    for index, (record, start) in enumerate(zip(ledger, starts), 1):
        plan = planned_by_id.get(record.get("logical_call_id"))
        if plan is None or record.get("request_hash") != plan.get("request_hash") or start.get("request_hash") != plan.get("request_hash"):
            raise RuntimeError("v21 ledger/schedule binding drift")
        if record.get("provider_attempt_index") != index or record.get("staged_execution_index") != index or start.get("sequence") != index:
            raise RuntimeError("v21 exact-prefix drift")
        if record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}):
            raise RuntimeError("v21 response ledger hash drift")
        if start.get("start_entry_sha256") != stable({k: v for k, v in start.items() if k != "start_entry_sha256"}):
            raise RuntimeError("v21 request-start ledger hash drift")
    completed = [row for row in ledger if row.get("status") == "completed"]
    by_task: dict[str, list[dict[str, Any]]] = {}
    for row in ledger:
        by_task.setdefault(row["task_id"], []).append(row)
    reusable_tasks = sorted(task_id for task_id, rows in by_task.items() if len(rows) == 4 and all(row.get("status") == "completed" for row in rows))
    excluded_tasks = sorted(task_id for task_id in by_task if task_id not in reusable_tasks)
    attempted_ids = {row["logical_call_id"] for row in ledger}
    unattempted = [row for row in planned if row["logical_call_id"] not in attempted_ids]
    carry = [row for row in unattempted if row["task_id"] not in excluded_tasks]
    if len(reusable_tasks) != 58 or len(excluded_tasks) != 1 or len(carry) != 84:
        raise RuntimeError("v21 reusable/carry-forward partition drift")
    if excluded_tasks != [cfg["recovery_contract"]["incomplete_v21_task_id"]]:
        raise RuntimeError("v21 incomplete task identity drift")
    return {
        "planned_rows": len(planned), "spent_rows": len(ledger), "completed_rows": len(completed),
        "terminal_rows": 1, "reusable_completed_rows": sum(row["task_id"] in reusable_tasks for row in completed),
        "orphan_completed_rows": sum(row["task_id"] in excluded_tasks for row in completed),
        "unattempted_rows": len(unattempted), "carry_forward_rows": len(carry),
        "reusable_task_ids": reusable_tasks, "excluded_task_ids": excluded_tasks,
        "terminal_logical_call_id": ledger[-1]["logical_call_id"], "terminal_request_hash": ledger[-1]["request_hash"],
        "ledger_hash_chain_valid": audit.get("ledger_hash_chain_valid"),
        "request_start_hash_chain_valid": audit.get("request_start_hash_chain_valid"),
        "exact_prefix_resume_valid": audit.get("exact_prefix_resume_valid"),
        "authorization_closed": audit.get("authorization_closed"),
    }


def replacement_exclusions() -> set[str]:
    excluded = set(prior_exclusions()["2WikiMultiHopQA"])
    for path in (
        V17_GOLD, V19_GOLD, PHASE2_CALIBRATION_GOLD, PHASE2_DEVELOPMENT_GOLD,
        PHASE2_FORMAL_HISTORY_GOLD, PHASE2_PROBE_GOLD, V21_GOLD,
    ):
        excluded.update(str(row["task_id"]) for row in load(path))
    bundles = load(V17_PRIORS)
    excluded.update(str(row["task_id"]) for row in bundles["global"]["examples"])
    for bundle in bundles["typed"].values():
        excluded.update(str(row["task_id"]) for row in bundle["examples"])
    return excluded


def select_replacement() -> dict[str, Any]:
    excluded = replacement_exclusions()
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for row in load(SOURCE_DEV):
        task_id = str(row.get("_id", ""))
        if task_id in excluded or row.get("type") != "compositional" or not row.get("question") or not row.get("context") or row.get("answer") is None or not row.get("supporting_facts"):
            continue
        payload = make_payload(row, "2WikiMultiHopQA", "entity_bridge", "dev")
        selector_hash = hashlib.sha256(f"phase2-v22:heldout-recovery-replacement:entity_bridge:{task_id}".encode()).hexdigest()
        candidates.append((selector_hash, task_id, payload))
    if not candidates:
        raise RuntimeError("no unused entity-bridge held-out recovery task")
    selector_hash, task_id, payload = min(candidates)
    return {
        "selector": "min SHA256(phase2-v22:heldout-recovery-replacement:entity_bridge:<task_id>)",
        "candidate_pool_size": len(candidates), "replacement_task_id": task_id,
        "replacement_selector_hash": selector_hash, "replacement_payload_hash": stable(payload),
        "replacement_not_in_prior_or_prior_partitions_or_v17_v19_v21": task_id not in excluded,
        "payload": payload,
    }


def build_schedule(provenance: dict[str, Any], replacement: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    planned = load(V21_SCHEDULE)["schedule"]
    spent_ids = {row["logical_call_id"] for row in load(V21_LEDGER)}
    excluded_task = provenance["excluded_task_ids"][0]
    carry = [row for row in planned if row["logical_call_id"] not in spent_ids and row["task_id"] != excluded_task]
    bundles = load(V21_PRIORS)
    rows: list[dict[str, Any]] = []

    def add_row(source: dict[str, Any], source_kind: str) -> None:
        index = len(rows) + 1
        body = copy.deepcopy(source["canonical_request_body"])
        body["candidate_version"] = "phase2-v22-heldout-recovery"
        body["prompt_template_version"] = "phase2-heldout-recovery-json-v22"
        row = copy.deepcopy(source)
        row.update({
            "schema_version": VERSION, "sequence": index, "staged_execution_index": index,
            "logical_call_id": f"phase2-v22:held_out_recovery:{source['skill_family']}:{source['task_id']}:{source['condition']}",
            "request_hash": stable(body), "candidate_version": body["candidate_version"],
            "prompt_template_version": body["prompt_template_version"], "canonical_request_body": body,
            "provenance": {**source["provenance"], "recovery_source": source_kind, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
        })
        rows.append(row)

    for source in carry:
        add_row(source, "v21_unattempted_complete_task_suffix")

    task = replacement["payload"]
    for condition in CONDITIONS:
        candidate_id, prior = condition_prior(condition, task["skill_family"], bundles)
        prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        body = {
            "model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False,
            "response_format": {"type": "json_object"}, "phase": "2", "stage": "Stage 6",
            "partition": "held_out", "task_family": task["task_family"], "task_type": task["task_type"],
            "skill_family": task["skill_family"], "task_id": task["task_id"], "payload_hash": stable(task),
            "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v22-heldout-recovery",
            "typed_scope": task["skill_family"], "prompt_template_version": "phase2-heldout-recovery-json-v22",
            "prior_payload_sha256": stable(prior),
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Prior bundle:\n" + prior_text + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)}],
        }
        source = {
            "schema_version": VERSION, "partition": "held_out", "stage": "Stage 6", "task_id": task["task_id"],
            "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": task["skill_family"],
            "typed_scope": task["skill_family"], "payload_hash": stable(task), "condition": condition,
            "candidate_id": candidate_id, "prior_payload_sha256": body["prior_payload_sha256"],
            "canonical_request_body": body,
            "provenance": {"source_dataset": "2WikiMultiHopQA", "source_record_id": task["task_id"], "payload_source": "dev", "gold_is_not_request": True, "held_out_gold_not_in_prior": True},
            "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
        }
        add_row(source, "v22_deterministic_entity_bridge_replacement")

    v21_gold = [copy.deepcopy(row) for row in load(V21_GOLD) if row["task_id"] != excluded_task]
    combined_gold = v21_gold + [copy.deepcopy(task)]
    completed = [row for row in load(V21_LEDGER) if row.get("status") == "completed" and row["task_id"] in provenance["reusable_task_ids"]]
    combined_plan = [{"analysis_index": index, "source": "v21_completed_provenance", "task_id": row["task_id"], "condition": row["condition"], "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "provider_attempt_index": row["provider_attempt_index"]} for index, row in enumerate(completed, 1)]
    combined_plan.extend({"analysis_index": len(combined_plan) + 1, "source": "v22_recovery_schedule", "task_id": row["task_id"], "condition": row["condition"], "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "recovery_sequence": row["sequence"]} for row in rows)
    return rows, combined_gold, combined_plan


def prior_identity_sets() -> tuple[set[str], set[str]]:
    logical: set[str] = set()
    hashes: set[str] = set()
    for path in (V17_SCHEDULE, V19_SCHEDULE, V21_SCHEDULE):
        for row in load(path).get("schedule", []):
            logical.add(row["logical_call_id"]); hashes.add(row["request_hash"])
    for path in (ROOT / "artifacts/acl2027_phase2_probe_only_live_v14/ledger.json", ROOT / "artifacts/acl2027_phase2_probe_only_live_v18/ledger.json", ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/ledger.json", V21_LEDGER):
        for row in load(path):
            logical.add(row["logical_call_id"]); hashes.add(row["request_hash"])
    return logical, hashes


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    provenance = validate_v21_provenance()
    replacement = select_replacement()
    rows, gold, combined = build_schedule(provenance, replacement)
    if len(rows) != RECOVERY_CALLS or len({row["logical_call_id"] for row in rows}) != RECOVERY_CALLS or len({row["request_hash"] for row in rows}) != RECOVERY_CALLS:
        raise RuntimeError("v22 recovery schedule identity drift")
    prior_logical, prior_hashes = prior_identity_sets()
    if prior_logical & {row["logical_call_id"] for row in rows} or prior_hashes & {row["request_hash"] for row in rows}:
        raise RuntimeError("v22 recovery schedule reuses a prior identity")
    spent = load(V21_LEDGER)
    if {row["logical_call_id"] for row in spent} & {row["logical_call_id"] for row in rows} or {row["request_hash"] for row in spent} & {row["request_hash"] for row in rows}:
        raise RuntimeError("v22 retries a spent v21 request")
    if [row["staged_execution_index"] for row in rows] != list(range(1, RECOVERY_CALLS + 1)):
        raise RuntimeError("v22 exact-prefix indices drift")
    if any("max_tokens" in row["canonical_request_body"] or row["canonical_request_body"].get("model_id") != "qwen3.7-plus" or row["canonical_request_body"].get("temperature") != 0 or row["canonical_request_body"].get("enable_thinking") is not False or row["canonical_request_body"].get("response_format") != {"type": "json_object"} for row in rows):
        raise RuntimeError("v22 route boundary drift")
    if any('"answers"' in json.dumps(row["canonical_request_body"], ensure_ascii=False) or '"answer"' in json.dumps(row["canonical_request_body"], ensure_ascii=False).replace(SYSTEM, "") for row in rows):
        raise RuntimeError("v22 gold leaked into request")
    if len(gold) != 80 or len({row["task_id"] for row in gold}) != 80 or len(combined) != 320:
        raise RuntimeError("v22 combined analysis size drift")
    combined_keys = {(row["task_id"], row["condition"]) for row in combined}
    if len(combined_keys) != 320 or any(sum(row["task_id"] == task["task_id"] for row in combined) != 4 for task in gold):
        raise RuntimeError("v22 combined 80x4 grid drift")
    if any(sum(row["condition"] == condition for row in combined) != 80 for condition in CONDITIONS):
        raise RuntimeError("v22 combined condition balance drift")
    result = {
        "schema_version": VERSION, "experiment": "acl2027_phase2_heldout_recovery_preflight_v22",
        "status": "preflight-passed-recovery-plan", "authorization_request_status": "fresh_explicit_authorization_required",
        "execution": cfg["execution"], "v21_provenance": provenance, "recovery_calls": len(rows),
        "recovery_condition_counts": {condition: sum(row["condition"] == condition for row in rows) for condition in CONDITIONS},
        "combined_analysis_rows": len(combined), "combined_task_count": len(gold),
        "combined_condition_counts": {condition: sum(row["condition"] == condition for row in combined) for condition in CONDITIONS},
        "replacement_selection": {key: value for key, value in replacement.items() if key != "payload"},
        "spent_v21_requests_excluded": len(spent), "all_recovery_logical_ids_new": True,
        "all_recovery_request_hashes_new": True, "orphan_completed_row_reused": False,
        "gold_in_request": False, "network_calls": 0, "provider_calls": 0, "model_calls": 0,
        "paid_api_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0,
        "authorization_opened": False, "proposed_authorization": cfg["authorization_request"],
        "bindings": {**cfg["bindings"], "recovery_schedule_canonical_sha256": stable(rows), "combined_gold_canonical_sha256": stable(gold), "combined_analysis_plan_canonical_sha256": stable(combined)},
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def authorization_request(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": VERSION, "authorization_id": "phase2-heldout-recovery-only-v22",
        "scope": "held_out_recovery_only", "status": "awaiting_fresh_explicit_user_authorization",
        "requested_calls": RECOVERY_CALLS, "max_provider_attempts": RECOVERY_CALLS,
        "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False,
        "enable_thinking": False, "response_format": {"type": "json_object"},
        "cost_ceilings": {"stage_cost_ceiling_cny": None, "cumulative_cost_ceiling_cny": None, "status": "fresh_explicit_values_required"},
        "execution": {"network_calls_allowed": False, "provider_calls_allowed": False, "paid_api_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False},
        "user_authorization": {"explicit_user_authorization_required": True, "held_out_recovery_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False, "does_not_inherit_v21_authorization": True},
        "bindings": {
            "preflight_aggregate_fingerprint": result["aggregate_fingerprint"], "preflight_config_sha256": sha256_file(CONFIG),
            "preflight_manifest_sha256": sha256_file(ARTIFACT / "run_manifest.json"),
            "recovery_schedule_sha256": sha256_file(ARTIFACT / "held_out_recovery_schedule.json"),
            "v21_provenance_audit_sha256": sha256_file(ARTIFACT / "v21_provenance_audit.json"),
            "combined_gold_sha256": sha256_file(ARTIFACT / "combined_held_out_gold.json"),
            "combined_analysis_plan_sha256": sha256_file(ARTIFACT / "combined_analysis_plan.json"),
            "prior_bundles_sha256": sha256_file(ARTIFACT / "prior_bundles.json"),
        },
        "forbidden": ["retry_or_resume_any_v21_spent_request", "calibration", "development_acquisition", "formal_history", "probe", "later_phase2_stages", "formal_scaling"],
    }


def write_artifact(result: dict[str, Any]) -> None:
    provenance = result["v21_provenance"]
    replacement = select_replacement()
    rows, gold, combined = build_schedule(provenance, replacement)
    ARTIFACT.mkdir(parents=True, exist_ok=False)
    documents = {
        "v21_provenance_audit.json": {"schema_version": VERSION, **provenance, "ledger_sha256": sha256_file(V21_LEDGER), "request_start_ledger_sha256": sha256_file(V21_STARTS)},
        "held_out_recovery_schedule.json": {"schema_version": VERSION, "schedule": rows},
        "replacement_held_out_gold.json": replacement["payload"],
        "combined_held_out_gold.json": gold,
        "combined_analysis_plan.json": {"schema_version": VERSION, "rows": combined},
        "prior_bundles.json": load(V21_PRIORS),
    }
    for name, value in documents.items():
        (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
    result["documents"] = {name: rendered_sha256(value) for name, value in documents.items()}
    result["aggregate_fingerprint"] = stable({key: value for key, value in result.items() if key != "aggregate_fingerprint"})
    (ARTIFACT / "run_manifest.json").write_text(render(result), encoding="utf-8", newline="\n")
    AUTH_REQUEST.write_text(render(authorization_request(result)), encoding="utf-8", newline="\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "# ACL 2027 Phase 2 v22 Held-out Recovery Preflight\n\n"
        "This is a zero-network recovery preflight. It excludes all 234 spent v21 requests and opens no provider authorization.\n\n"
        "It admits 232 completed rows from 58 complete v21 task grids, excludes the orphan cold row from the incomplete entity-bridge task, freezes 84 renamed unattempted rows, and adds a deterministic four-condition replacement grid. The combined analysis target is restored to 320 rows over 80 tasks.\n\n"
        f"Replacement task: `{replacement['replacement_task_id']}`. Recovery calls: 88. Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n\n"
        "A separate authorization request remains closed and has no cost ceilings. Fresh explicit authorization must provide both stage and cumulative CNY ceilings before any provider call. Later stages and formal scaling remain forbidden.\n",
        encoding="utf-8", newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        write_artifact(result)
        result = load(ARTIFACT / "run_manifest.json")
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
