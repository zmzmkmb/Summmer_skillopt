#!/usr/bin/env python3
"""Deterministically materialize trusted Phase 2 candidates from the history ledger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.acl2027_phase2_response_verifier_v3 import (
    ROOT, VerificationError, load_gold, sha256_file, stable, verify_response,
)

FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")


class MaterializationError(RuntimeError):
    pass


def _history(records: list[dict[str, Any]], schedule: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actual = [row for row in records if row.get("partition") == "formal_history"]
    expected = [row for row in schedule if row.get("partition") == "formal_history"]
    if len(actual) != 160 or len(expected) != 160:
        raise MaterializationError("complete 160-row formal-history ledger required")
    return actual, expected


def build_candidate_artifact(
    records: list[dict[str, Any]], schedule: list[dict[str, Any]], config: dict[str, Any],
    *, root: Path = ROOT,
) -> dict[str, Any]:
    actual, expected = _history(records, schedule)
    gold, gold_path = load_gold("formal_history", root=root)
    bindings = config["trusted_evaluation"]
    verifier_path = ROOT / "scripts/acl2027_phase2_response_verifier_v3.py"
    materializer_path = ROOT / "scripts/materialize_acl2027_phase2_candidates_v3.py"
    schema_path = ROOT / config["coverage_gate"]["schema_path"]
    if sha256_file(verifier_path) != bindings["verifier_source_sha256"] or sha256_file(materializer_path) != bindings["materializer_source_sha256"]:
        raise MaterializationError("verifier/materializer source hash drift")
    if sha256_file(schema_path) != bindings["verifier_config_sha256"]:
        raise MaterializationError("verifier config hash drift")
    if sha256_file(gold_path) != bindings["formal_history_gold_sha256"]:
        raise MaterializationError("formal-history gold manifest hash drift")
    by_task = {row["task_id"]: row for row in expected}
    if len(by_task) != 160 or set(by_task) != set(gold):
        raise MaterializationError("history schedule/private-gold identity drift")
    trajectories: list[dict[str, Any]] = []
    all_response_hashes: set[str] = set()
    for record, planned in zip(actual, expected):
        keys = ("logical_call_id", "request_hash", "task_id", "skill_family", "payload_hash")
        if any(record.get(key) != planned.get(key) for key in keys):
            raise MaterializationError("history ledger/schedule binding drift")
        if record.get("terminal") or record.get("raw_response_sha256") != stable(record.get("raw_response")):
            raise MaterializationError("history response binding or terminal state invalid")
        if record["raw_response_sha256"] in all_response_hashes:
            raise MaterializationError("duplicate identity: response_sha256")
        all_response_hashes.add(record["raw_response_sha256"])
        private = gold[planned["task_id"]]
        if private.get("skill_family") != planned["skill_family"] or private.get("_frozen_payload_sha256") != planned["payload_hash"]:
            raise MaterializationError("history family or payload binding drift")
        try:
            verdict = verify_response(record["raw_response"], private)
        except VerificationError as exc:
            raise MaterializationError(str(exc)) from exc
        if not verdict["verifier_confirmed_success"]:
            continue
        identity = stable({"logical_call_id": planned["logical_call_id"], "response_sha256": record["raw_response_sha256"]})
        trajectories.append({
            "trajectory_id": f"trajectory:{identity}",
            "support_id": f"support:{identity}",
            "candidate_id": f"candidate:{planned['skill_family']}:v3",
            "task_id": planned["task_id"],
            "logical_call_id": planned["logical_call_id"],
            "request_hash": planned["request_hash"],
            "response_sha256": record["raw_response_sha256"],
            "family": planned["skill_family"],
            "verifier_confirmed_success": True,
            "parsed_response_sha256": stable(verdict["parsed_response"]),
            "provenance": {"partition": "formal_history", "staged_execution_index": planned["staged_execution_index"]},
        })
    seen: dict[str, set[str]] = {key: set() for key in ("trajectory_id", "support_id", "task_id", "logical_call_id", "request_hash")}
    counts = {family: 0 for family in FAMILIES}
    for item in trajectories:
        if item["family"] not in counts:
            raise MaterializationError("unknown family")
        for key, values in seen.items():
            if item[key] in values:
                raise MaterializationError(f"duplicate identity: {key}")
            values.add(item[key])
        counts[item["family"]] += 1
    passed = all(counts[family] >= config["coverage_gate"]["minimum_per_family"] for family in FAMILIES)
    return {
        "schema_version": 3,
        "artifact_type": "acl2027_phase2_candidate_materialization_v3",
        "generator": "deterministic_replay_not_caller_verdict",
        "history_response_ledger_sha256": stable(actual),
        "history_rows": 160,
        "formal_history_gold_manifest_path": str(gold_path.relative_to(root)).replace("\\", "/"),
        "formal_history_gold_manifest_sha256": sha256_file(gold_path),
        "verifier_source_sha256": bindings["verifier_source_sha256"],
        "verifier_config_sha256": bindings["verifier_config_sha256"],
        "materializer_source_sha256": bindings["materializer_source_sha256"],
        "coverage_status": "coverage-passed" if passed else "coverage-incomplete",
        "passed": passed,
        "method_failure": False,
        "independent_verified_supports": counts,
        "evaluation_leakage_audit": {
            "passed": True,
            "accessed_partitions": ["formal_history"],
            "probe_gold_accessed": False,
            "held_out_gold_accessed": False,
        },
        "trajectories": trajectories,
    }


def write_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.write_text(json.dumps(artifact, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
