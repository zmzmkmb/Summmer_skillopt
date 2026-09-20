#!/usr/bin/env python3
"""Build the zero-network Phase 3B v4 recovery schedule after terminal v3."""
from __future__ import annotations

import hashlib, json, os, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import source_candidates
from scripts.run_acl2027_phase3b_activation_preflight_v1 import CONDITIONS, build_schedule, phase2_identity_universe

VERSION = 4
CONFIG = ROOT / "configs/acl2027/phase3b_activation_recovery_preflight_v4.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3b_activation_recovery_preflight_v4.py"
TEST = ROOT / "tests/test_acl2027_phase3b_activation_recovery_preflight_v4.py"
V1 = ROOT / "artifacts/acl2027_phase3b_activation_preflight_v1"
V3 = ROOT / "artifacts/acl2027_phase3b_activation_live_v3"
V1_MANIFEST, V1_SCHEDULE, V1_GOLD, V1_PLAN = V1 / "run_manifest.json", V1 / "activation_schedule.json", V1 / "activation_private_gold.json", V1 / "analysis_plan.json"
V3_LEDGER, V3_AUDIT, V3_CLOSURE = V3 / "ledger.json", V3 / "run_audit.json", V3 / "authorization_closure.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase3b_activation_recovery_preflight_v4"
REPORT = ROOT / "paper/acl2027/results/phase3b_activation_recovery_preflight_v4.md"


def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=True, sort_keys=True, indent=2); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()


def replacement_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase3b-v4:recovery:{family}:{task_id}".encode()).hexdigest()


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    cfg, manifest = load(CONFIG), load(V1_MANIFEST)
    original_schedule, original_gold = load(V1_SCHEDULE)["schedule"], load(V1_GOLD)
    records, audit, closure = load(V3_LEDGER), load(V3_AUDIT), load(V3_CLOSURE)
    if cfg["status"] != "design_only_not_authorized" or any(cfg[k] for k in ("data_egress_authorized", "provider_calls_authorized", "paid_api_authorized", "later_stages_authorized", "formal_scaling_authorized")): raise RuntimeError("v4 must remain execution-closed")
    if manifest.get("aggregate_fingerprint") != "fe1bb5316f57e4aa4dba14e19a173a44c60575263bd54018b8b33e6d256de7b8": raise RuntimeError("v1 fingerprint drift")
    if len(records) != 127 or audit.get("status") != "terminal_hard_stop" or audit.get("completed_calls") != 126 or audit.get("provider_attempts") != 127 or closure.get("status") != "closed": raise RuntimeError("v3 terminal boundary drift")
    if not records[-1].get("terminal") or "getaddrinfo failed" not in str(records[-1].get("error")): raise RuntimeError("v3 terminal identity drift")

    completed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if row.get("status") == "completed": completed[str(row["task_id"])].append(row)
    complete_ids = {task_id for task_id, rows in completed.items() if len(rows) == 5}
    partial_ids = {task_id for task_id, rows in completed.items() if len(rows) != 5}
    if len(complete_ids) != 25 or len(partial_ids) != 1: raise RuntimeError("v3 complete-prefix task structure drift")
    partial_id = next(iter(partial_ids)); original_by_id = {str(row["task_id"]): row for row in original_gold}
    partial_task = original_by_id[partial_id]; family = str(partial_task["skill_family"])

    occupied = set(phase2_identity_universe()["task_ids"]) | set(original_by_id)
    available = [row for row in source_candidates()[family] if str(row["task_id"]) not in occupied]
    ordered = sorted(available, key=lambda row: (replacement_hash(family, str(row["task_id"])), str(row["task_id"])))
    if not ordered: raise RuntimeError("no unused recovery replacement task")
    replacement = ordered[0]
    recovery_tasks = [replacement if str(row["task_id"]) == partial_id else row for row in original_gold if str(row["task_id"]) not in complete_ids]
    if len(recovery_tasks) != 35 or len({str(row["task_id"]) for row in recovery_tasks}) != 35: raise RuntimeError("recovery task count drift")
    schedule, private_gold = build_schedule(recovery_tasks)
    for index, row in enumerate(schedule, 1):
        row["schema_version"] = VERSION; row["sequence"] = index; row["staged_execution_index"] = index
        row["logical_call_id"] = f"phase3b-v4:recovery:{row['skill_family']}:{row['task_id']}:{row['condition']}"
        row["provenance"]["recovery_version"] = VERSION
    spent_hashes = {str(row["request_hash"]) for row in records}; spent_logical = {str(row["logical_call_id"]) for row in records}
    if len(schedule) != 175 or len({row["logical_call_id"] for row in schedule}) != 175 or len({row["request_hash"] for row in schedule}) != 175: raise RuntimeError("recovery request identity drift")
    if {row["request_hash"] for row in schedule} & spent_hashes or {row["logical_call_id"] for row in schedule} & spent_logical: raise RuntimeError("recovery overlaps a spent v3 identity")
    if Counter(row["condition"] for row in schedule) != Counter({condition: 35 for condition in CONDITIONS}): raise RuntimeError("recovery condition balance drift")
    reusable = [row for row in records if row.get("status") == "completed" and str(row["task_id"]) in complete_ids]
    if len(reusable) != 125: raise RuntimeError("reusable v3 prefix drift")
    combined_tasks = complete_ids | {str(row["task_id"]) for row in recovery_tasks}
    if len(combined_tasks) != 60: raise RuntimeError("combined task count drift")

    documents = {
        "recovery_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "recovery_private_gold.json": private_gold,
        "reusable_v3_prefix.json": reusable,
        "analysis_plan.json": load(V1_PLAN),
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "recovery-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "v3_provider_attempts": 127,
        "v3_completed_calls": 126,
        "v3_reusable_complete_grid_rows": 125,
        "v3_reusable_complete_tasks": 25,
        "excluded_partial_completed_rows": 1,
        "excluded_terminal_rows": 1,
        "excluded_partial_task_id": partial_id,
        "replacement_task_id": str(replacement["task_id"]),
        "replacement_skill_family": family,
        "recovery_tasks": 35,
        "recovery_calls": 175,
        "combined_tasks": 60,
        "combined_rows": 300,
        "spent_request_hash_overlap": 0,
        "spent_logical_call_overlap": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "bindings": {
            "config_sha256": sha256_file(CONFIG), "script_sha256": sha256_file(SCRIPT), "test_sha256": sha256_file(TEST),
            "v1_manifest_sha256": sha256_file(V1_MANIFEST), "v1_schedule_sha256": sha256_file(V1_SCHEDULE), "v1_gold_sha256": sha256_file(V1_GOLD), "v1_analysis_plan_sha256": sha256_file(V1_PLAN),
            "v3_ledger_sha256": sha256_file(V3_LEDGER), "v3_audit_sha256": sha256_file(V3_AUDIT), "v3_closure_sha256": sha256_file(V3_CLOSURE),
        },
        "documents": {name: stable(value) for name, value in documents.items()},
    }
    result["aggregate_fingerprint"] = stable(result)
    return result, documents


def report_text(result: dict[str, Any]) -> str:
    return f"""# ACL 2027 Phase 3B activation recovery preflight v4

The terminal v3 run spent 127 requests and completed 126. Exactly 125 completed rows from 25 full task grids are reusable. The one-row partial task and its terminal row are excluded as a whole.

The closed recovery freezes 35 task grids and 175 new requests: 34 untouched original tasks plus one deterministic same-family replacement task `{result['replacement_task_id']}`. Combined with the reusable prefix, this yields 60 tasks and 300 analyzable rows. Spent logical-call and request-hash overlap are both zero.

No network, provider, model, or paid call was made. Execution is not authorized. Aggregate fingerprint: `{result['aggregate_fingerprint']}`.
"""


def main() -> int:
    result, documents = build()
    for name, value in documents.items(): write(ARTIFACT / name, value)
    write(ARTIFACT / "run_manifest.json", result)
    REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
