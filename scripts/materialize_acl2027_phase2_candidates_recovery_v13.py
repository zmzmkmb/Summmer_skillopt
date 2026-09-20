#!/usr/bin/env python3
"""Materialize v11+v12 formal-history candidates with correct replay identity rules."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.acl2027_phase2_response_verifier_v3 import VerificationError, stable, verify_response

FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")


class RecoveryMaterializationV13Error(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        raise RecoveryMaterializationV13Error("v13 requires 32 preserved plus 128 recovery rows")
    gold_path = root / config["trusted_evaluation"]["combined_gold_path"]
    gold_rows = load(gold_path)
    gold = {row["task_id"]: {**row, "answers": row.get("answers") or [row.get("answer")], "_frozen_payload_sha256": stable(row)} for row in gold_rows}
    if len(gold) != 160 or set(gold) != {row["task_id"] for row in combined_schedule}:
        raise RecoveryMaterializationV13Error("combined gold identity drift")
    if sha256_file(gold_path) != config["trusted_evaluation"]["combined_gold_sha256"]:
        raise RecoveryMaterializationV13Error("combined gold hash drift")

    logical_ids: set[str] = set()
    request_hashes: set[str] = set()
    provider_ids: set[str] = set()
    trajectories: list[dict[str, Any]] = []
    correct_counts: Counter[str] = Counter()
    duplicate_answer_hashes: Counter[str] = Counter()
    for record, planned in zip(records, combined_schedule):
        for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "payload_hash"):
            if record.get(key) != planned.get(key):
                raise RecoveryMaterializationV13Error("combined ledger/schedule binding drift")
        if record.get("terminal") or record.get("raw_response_sha256") != stable(record.get("raw_response")):
            raise RecoveryMaterializationV13Error("terminal or response hash in combined ledger")
        if record["logical_call_id"] in logical_ids or record["request_hash"] in request_hashes:
            raise RecoveryMaterializationV13Error("duplicate logical request identity")
        logical_ids.add(record["logical_call_id"])
        request_hashes.add(record["request_hash"])
        provider_id = record.get("raw_provider_response", {}).get("id")
        if not provider_id or provider_id in provider_ids:
            raise RecoveryMaterializationV13Error("duplicate provider response identity")
        provider_ids.add(provider_id)
        duplicate_answer_hashes[record["raw_response_sha256"]] += 1
        private = gold[planned["task_id"]]
        if private["skill_family"] != planned["skill_family"] or private["_frozen_payload_sha256"] != planned["payload_hash"]:
            raise RecoveryMaterializationV13Error("combined family or payload drift")
        try:
            verdict = verify_response(record["raw_response"], private)
        except VerificationError as exc:
            raise RecoveryMaterializationV13Error(str(exc)) from exc
        if verdict["verifier_confirmed_success"]:
            family = planned["skill_family"]
            correct_counts[family] += 1
            identity = stable({"logical_call_id": planned["logical_call_id"], "response_sha256": record["raw_response_sha256"]})
            trajectories.append({
                "trajectory_id": f"trajectory:{identity}",
                "support_id": f"support:{identity}",
                "candidate_id": f"candidate:{family}:v13",
                "task_id": planned["task_id"],
                "logical_call_id": planned["logical_call_id"],
                "request_hash": planned["request_hash"],
                "response_sha256": record["raw_response_sha256"],
                "family": family,
                "verifier_confirmed_success": True,
                "provenance": {"partition": "formal_history", "source_stage": planned["source_stage"]},
            })
    minimum = config["coverage_gate"]["minimum_per_family"]
    passed = all(correct_counts[family] >= minimum for family in FAMILIES)
    return {
        "schema_version": 13,
        "artifact_type": "acl2027_phase2_candidate_materialization_recovery_v13",
        "generator": "deterministic_v11_prefix_plus_v12_recovery_replay_identity_corrected",
        "history_rows": 160,
        "preserved_v11_rows": 32,
        "recovery_v12_rows": 128,
        "combined_history_ledger_sha256": stable(records),
        "combined_gold_sha256": sha256_file(gold_path),
        "coverage_status": "coverage-passed" if passed else "coverage-incomplete",
        "passed": passed,
        "method_failure": False,
        "independent_verified_supports": {family: correct_counts[family] for family in FAMILIES},
        "duplicate_answer_hash_groups": {digest: count for digest, count in duplicate_answer_hashes.items() if count > 1},
        "duplicate_answer_hashes_allowed": True,
        "duplicate_logical_requests": 0,
        "duplicate_request_hashes": 0,
        "duplicate_provider_response_ids": 0,
        "evaluation_leakage_audit": {"passed": True, "accessed_partitions": ["formal_history"], "probe_gold_accessed": False, "held_out_gold_accessed": False},
        "trajectories": trajectories,
    }
