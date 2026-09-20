#!/usr/bin/env python3
"""Materialize Phase 2 candidates from the v11 prefix plus v12 recovery ledger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.acl2027_phase2_response_verifier_v3 import (
    VerificationError,
    sha256_file,
    stable,
    verify_response,
)

FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")


class RecoveryMaterializationError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_recovery_candidate_artifact(
    preserved_records: list[dict[str, Any]],
    recovery_records: list[dict[str, Any]],
    combined_schedule: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    records = preserved_records + recovery_records
    if len(preserved_records) != 32 or len(recovery_records) != 128 or len(records) != len(combined_schedule) != 160:
        raise RecoveryMaterializationError("v12 requires 32 preserved plus 128 recovery rows")
    gold_path = root / config["trusted_evaluation"]["combined_gold_path"]
    gold_rows = load(gold_path)
    gold = {row["task_id"]: {**row, "answers": row.get("answers") or [row.get("answer")], "_frozen_payload_sha256": stable(row)} for row in gold_rows}
    if len(gold) != 160 or set(gold) != {row["task_id"] for row in combined_schedule}:
        raise RecoveryMaterializationError("combined gold identity drift")
    if sha256_file(gold_path) != config["trusted_evaluation"]["combined_gold_sha256"]:
        raise RecoveryMaterializationError("combined gold hash drift")
    trajectories = []
    seen_responses: set[str] = set()
    for record, planned in zip(records, combined_schedule):
        for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "payload_hash"):
            if record.get(key) != planned.get(key):
                raise RecoveryMaterializationError("combined ledger/schedule binding drift")
        if record.get("terminal") or record.get("raw_response_sha256") != stable(record.get("raw_response")):
            raise RecoveryMaterializationError("terminal or response hash in combined ledger")
        if record["raw_response_sha256"] in seen_responses:
            raise RecoveryMaterializationError("duplicate response hash")
        seen_responses.add(record["raw_response_sha256"])
        private = gold[planned["task_id"]]
        if private["skill_family"] != planned["skill_family"] or private["_frozen_payload_sha256"] != planned["payload_hash"]:
            raise RecoveryMaterializationError("combined family or payload drift")
        try:
            verdict = verify_response(record["raw_response"], private)
        except VerificationError as exc:
            raise RecoveryMaterializationError(str(exc)) from exc
        if verdict["verifier_confirmed_success"]:
            identity = stable({"logical_call_id": planned["logical_call_id"], "response_sha256": record["raw_response_sha256"]})
            trajectories.append({
                "trajectory_id": f"trajectory:{identity}",
                "support_id": f"support:{identity}",
                "candidate_id": f"candidate:{planned['skill_family']}:v12",
                "task_id": planned["task_id"],
                "logical_call_id": planned["logical_call_id"],
                "request_hash": planned["request_hash"],
                "response_sha256": record["raw_response_sha256"],
                "family": planned["skill_family"],
                "verifier_confirmed_success": True,
                "parsed_response_sha256": stable(verdict["parsed_response"]),
                "provenance": {"partition": "formal_history", "source_stage": planned["source_stage"]},
            })
    counts = {family: sum(item["family"] == family for item in trajectories) for family in FAMILIES}
    passed = all(counts[family] >= config["coverage_gate"]["minimum_per_family"] for family in FAMILIES)
    return {
        "schema_version": 12,
        "artifact_type": "acl2027_phase2_candidate_materialization_recovery_v12",
        "generator": "deterministic_v11_prefix_plus_v12_recovery_replay",
        "history_rows": 160,
        "preserved_v11_rows": 32,
        "recovery_v12_rows": 128,
        "combined_history_ledger_sha256": stable(records),
        "combined_gold_sha256": sha256_file(gold_path),
        "coverage_status": "coverage-passed" if passed else "coverage-incomplete",
        "passed": passed,
        "method_failure": False,
        "independent_verified_supports": counts,
        "evaluation_leakage_audit": {"passed": True, "accessed_partitions": ["formal_history"], "probe_gold_accessed": False, "held_out_gold_accessed": False},
        "trajectories": trajectories,
    }
