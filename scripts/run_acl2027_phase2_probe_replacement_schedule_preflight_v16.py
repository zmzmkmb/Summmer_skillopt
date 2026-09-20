#!/usr/bin/env python3
"""Zero-network v16 replacement selection and condition-identifiability gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_acl2027_phase2_payload_and_freeze_v2 import make_payload, obj_hash, prior_exclusions
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase2_probe_replacement_schedule_preflight_v16.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
V14_LEDGER = ROOT / "artifacts/acl2027_phase2_probe_only_live_v14/ledger.json"
CANDIDATE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/combined_candidates_v13.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_replacement_schedule_preflight_v16"
PARTITIONS = ("calibration", "development_acquisition", "formal_history", "probe", "held_out")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def replacement_key(task_id: str) -> str:
    return hashlib.sha256(f"phase2-v16:probe-replacement:fact_retrieval:{task_id}".encode()).hexdigest()


def select_replacement() -> dict[str, Any]:
    used = {str(row["task_id"]) for part in PARTITIONS for row in load(ROOT / f"data/searchqa_phase2_verified/{part}.json")}
    excluded = prior_exclusions()["SearchQA"] | used
    candidates = []
    for split in ("train", "val", "test"):
        valid_ids = {str(row["id"]) for row in load(ROOT / f"data/searchqa_id_split/{split}/items.json")}
        for row in load(ROOT / f"data/searchqa_split/{split}/items.json"):
            task_id = str(row["id"])
            if task_id in valid_ids and task_id not in excluded and row.get("question") and row.get("context") and row.get("answers"):
                payload = make_payload(row, "SearchQA", "fact_retrieval", split)
                candidates.append((replacement_key(task_id), task_id, payload))
    if not candidates:
        raise RuntimeError("no unused fact-retrieval replacement")
    key, task_id, payload = min(candidates)
    return {"selector": "min SHA256(phase2-v16:probe-replacement:fact_retrieval:<task_id>)", "candidate_pool_size": len(candidates), "replacement_task_id": task_id, "replacement_selector_hash": key, "replacement_payload_hash": obj_hash(payload), "replacement_source_split": payload["source_split"], "replacement_not_in_any_phase2_partition": task_id not in used, "payload": payload}


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(cfg["execution"].get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise RuntimeError("v16 execution switches must remain closed")
    rows = [row for row in load(SCHEDULE)["schedule"] if row.get("partition") == "probe"]
    spent = load(V14_LEDGER)[0]
    spent_task = spent["task_id"]
    spent_grid = [row for row in rows if row["task_id"] == spent_task]
    if len(rows) != 160 or len(spent_grid) != 4 or len({row["condition"] for row in spent_grid}) != 4:
        raise RuntimeError("spent task grid binding drift")
    candidate = load(CANDIDATE)
    if sha256_file(SCHEDULE) != cfg["bindings"]["v14_schedule_sha256"] or sha256_file(V14_LEDGER) != cfg["bindings"]["v14_ledger_sha256"] or sha256_file(CANDIDATE) != cfg["bindings"]["v13_candidate_sha256"]:
        raise RuntimeError("v16 source binding drift")
    null_candidate_rows = sum(row.get("candidate_id") is None and row["canonical_request_body"].get("candidate_id") is None for row in rows)
    pending_rows = sum(row.get("candidate_version") == "phase2-v2-pending" for row in rows)
    prior_payload_rows = sum(any(key in row["canonical_request_body"] for key in ("prior_payload", "skill_prior", "verified_history", "candidate_supports")) for row in rows)
    replacement = select_replacement()
    blocked = null_candidate_rows == 160 and pending_rows == 160 and prior_payload_rows == 0
    if not blocked or candidate.get("passed") is not True:
        raise RuntimeError("condition-identifiability diagnostic drift")
    result = {"schema_version": 16, "status": "blocked-condition-semantics", "planned_probe_calls": 160, "spent_task_grid_rows_removed": 4, "replacement_task_grid_rows_planned": 4, "resulting_task_grid": "40 tasks x 4 conditions", "spent_task_id": spent_task, "null_candidate_id_rows": null_candidate_rows, "pending_candidate_version_rows": pending_rows, "model_visible_prior_payload_rows": prior_payload_rows, "replacement_selection": {k: v for k, v in replacement.items() if k != "payload"}, "schedule_written": False, "authorization_request_status": "blocked_not_submittable", "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0, "held_out_authorized": False, "formal_scaling_authorized": False}
    result["aggregate_fingerprint"] = stable(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        ARTIFACT.mkdir(parents=True, exist_ok=False)
        (ARTIFACT / "run_manifest.json").write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        selection = select_replacement()
        (ARTIFACT / "replacement_selection_audit.json").write_text(json.dumps(selection, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
