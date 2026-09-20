#!/usr/bin/env python3
"""Frozen deterministic Phase 2 probe analyzer."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.acl2027_phase2_response_verifier_v3 import (
    ROOT, VerificationError, load_gold, sha256_file, stable, verify_response,
)


class ProbeAnalysisError(RuntimeError):
    pass


def build_probe_audit(
    records: list[dict[str, Any]], schedule: list[dict[str, Any]], coverage_artifact: dict[str, Any],
    coverage_sha256: str, config: dict[str, Any], *, root: Path = ROOT,
) -> dict[str, Any]:
    probe = [row for row in records if row.get("partition") == "probe"]
    expected = [row for row in schedule if row.get("partition") == "probe"]
    if len(probe) != 160 or len(expected) != 160:
        raise ProbeAnalysisError("complete 160-row probe ledger required")
    if coverage_artifact.get("passed") is not True:
        raise ProbeAnalysisError("trusted coverage binding drift")
    gold, gold_path = load_gold("probe", root=root)
    bindings = config["trusted_evaluation"]
    analyzer_path = ROOT / "scripts/analyze_acl2027_phase2_probe_v3.py"
    schema_path = ROOT / config["probe_gate"]["schema_path"]
    if sha256_file(analyzer_path) != bindings["probe_analyzer_source_sha256"]:
        raise ProbeAnalysisError("probe analyzer source hash drift")
    if sha256_file(schema_path) != bindings["probe_analyzer_config_sha256"]:
        raise ProbeAnalysisError("probe analyzer config hash drift")
    if sha256_file(gold_path) != bindings["probe_gold_sha256"]:
        raise ProbeAnalysisError("probe gold manifest hash drift")
    expected_conditions = tuple(config["probe_gate"]["conditions"])
    outcomes: list[dict[str, Any]] = []
    condition_totals = {condition: 0 for condition in expected_conditions}
    condition_successes = {condition: 0 for condition in expected_conditions}
    task_conditions: dict[str, set[str]] = {}
    for record, planned in zip(probe, expected):
        keys = ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "payload_hash")
        if any(record.get(key) != planned.get(key) for key in keys):
            raise ProbeAnalysisError("probe ledger/schedule binding drift")
        if record.get("terminal") or record.get("raw_response_sha256") != stable(record.get("raw_response")):
            raise ProbeAnalysisError("probe response binding or terminal state invalid")
        private = gold.get(planned["task_id"])
        if private is None or private.get("skill_family") != planned["skill_family"] or private.get("_frozen_payload_sha256") != planned["payload_hash"]:
            raise ProbeAnalysisError("probe family or payload binding drift")
        condition = planned["condition"]
        if condition not in condition_totals:
            raise ProbeAnalysisError("probe condition drift")
        try:
            verdict = verify_response(record["raw_response"], private)
        except VerificationError as exc:
            raise ProbeAnalysisError(str(exc)) from exc
        condition_totals[condition] += 1
        condition_successes[condition] += int(verdict["verifier_confirmed_success"])
        task_conditions.setdefault(planned["task_id"], set()).add(condition)
        outcomes.append({
            "logical_call_id": planned["logical_call_id"], "task_id": planned["task_id"],
            "request_hash": planned["request_hash"], "response_sha256": record["raw_response_sha256"],
            "family": planned["skill_family"], "condition": condition,
            "verifier_confirmed_success": verdict["verifier_confirmed_success"],
        })
    if len(task_conditions) != 40 or any(values != set(expected_conditions) for values in task_conditions.values()):
        raise ProbeAnalysisError("probe condition grid incomplete")
    rates = {key: condition_successes[key] / condition_totals[key] for key in expected_conditions}
    passed = rates["contextual_typed_prior"] >= rates["global_only"]
    return {
        "schema_version": 3,
        "artifact_type": "acl2027_phase2_probe_audit_v3",
        "generator": "deterministic_probe_replay_not_caller_verdict",
        "passed": passed,
        "decision_rule": "contextual_typed_prior_accuracy_gte_global_only_accuracy",
        "coverage_artifact_sha256": coverage_sha256,
        "probe_ledger_sha256": stable(probe),
        "probe_rows": 160,
        "probe_gold_manifest_sha256": sha256_file(gold_path),
        "analyzer_source_sha256": bindings["probe_analyzer_source_sha256"],
        "analyzer_config_sha256": bindings["probe_analyzer_config_sha256"],
        "condition_counts": condition_totals,
        "condition_successes": condition_successes,
        "condition_accuracy": rates,
        "gold_access_audit": {
            "passed": True, "accessed_partitions": ["probe"],
            "candidate_mutated": False, "coverage_mutated": False,
            "held_out_gold_accessed": False,
        },
        "outcomes": outcomes,
    }
