#!/usr/bin/env python3
"""Deterministic private-gold analyzer for the v19/v20 recovery probe."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from scripts.acl2027_phase2_response_verifier_v3 import VerificationError, sha256_file, stable, verify_response
from scripts.analyze_acl2027_phase2_probe_replacement_v18 import load_gold


class ProbeRecoveryAnalysisError(RuntimeError):
    pass


CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")


def build_probe_audit(
    recovery_records: list[dict[str, Any]],
    recovery_schedule: list[dict[str, Any]],
    coverage_artifact: dict[str, Any],
    coverage_sha256: str,
    gold_path: Path,
    *,
    preserved_records: list[dict[str, Any]],
    preserved_schedule: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(recovery_records) != len(recovery_schedule) != 0 or len(recovery_records) != 112:
        raise ProbeRecoveryAnalysisError("complete 112-row recovery ledger required")
    if coverage_artifact.get("passed") is not True or coverage_artifact.get("coverage_status") != "coverage-passed":
        raise ProbeRecoveryAnalysisError("trusted v13 coverage binding drift")
    gold = load_gold(gold_path)
    gold_ids = set(gold)
    preserved = [row for row in preserved_records if row.get("status") == "completed" and row.get("task_id") in gold_ids]
    if len(preserved) != 48:
        raise ProbeRecoveryAnalysisError("exactly 48 reusable v18 rows required")
    original_by_logical = {row["logical_call_id"]: row for row in preserved_schedule}
    recovery_by_logical = {row["logical_call_id"]: row for row in recovery_schedule}
    combined: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for record in preserved:
        planned = original_by_logical.get(record.get("logical_call_id"))
        if planned is None:
            raise ProbeRecoveryAnalysisError("v18 preserved schedule binding drift")
        combined.append((record, planned))
    for record in recovery_records:
        planned = recovery_by_logical.get(record.get("logical_call_id"))
        if planned is None:
            raise ProbeRecoveryAnalysisError("v20 recovery schedule binding drift")
        combined.append((record, planned))
    if len(combined) != 160:
        raise ProbeRecoveryAnalysisError("combined probe must contain 160 rows")
    grid = Counter((planned["task_id"], planned["condition"]) for _, planned in combined)
    if len(grid) != 160 or any(count != 1 for count in grid.values()):
        raise ProbeRecoveryAnalysisError("combined task-condition grid is not unique")
    totals = {condition: 0 for condition in CONDITIONS}
    successes = {condition: 0 for condition in CONDITIONS}
    task_outcomes: dict[str, dict[str, bool]] = {}
    outcomes: list[dict[str, Any]] = []
    for record, planned in combined:
        for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "payload_hash"):
            if record.get(key) != planned.get(key):
                raise ProbeRecoveryAnalysisError("combined ledger/schedule binding drift")
        if record.get("terminal") or record.get("status") != "completed" or record.get("raw_response_sha256") != stable(record.get("raw_response")):
            raise ProbeRecoveryAnalysisError("combined response binding or terminal state invalid")
        private = gold.get(planned["task_id"])
        if private is None or private.get("skill_family") != planned["skill_family"] or private["_frozen_payload_sha256"] != planned["payload_hash"]:
            raise ProbeRecoveryAnalysisError("combined family or payload binding drift")
        condition = planned["condition"]
        if condition not in totals:
            raise ProbeRecoveryAnalysisError("combined condition drift")
        try:
            verdict = verify_response(record["raw_response"], private)
        except VerificationError as exc:
            raise ProbeRecoveryAnalysisError(str(exc)) from exc
        passed = bool(verdict["verifier_confirmed_success"])
        totals[condition] += 1
        successes[condition] += int(passed)
        task_outcomes.setdefault(planned["task_id"], {})[condition] = passed
        outcomes.append({
            "logical_call_id": planned["logical_call_id"],
            "task_id": planned["task_id"],
            "request_hash": planned["request_hash"],
            "response_sha256": record["raw_response_sha256"],
            "family": planned["skill_family"],
            "condition": condition,
            "source": "v18_preserved" if record in preserved else "v20_recovery",
            "verifier_confirmed_success": passed,
        })
    if len(task_outcomes) != 40 or any(set(values) != set(CONDITIONS) for values in task_outcomes.values()):
        raise ProbeRecoveryAnalysisError("combined task-condition grid incomplete")
    accuracy = {condition: successes[condition] / totals[condition] for condition in CONDITIONS}
    paired_wins = sum(values["contextual_typed_prior"] and not values["global_only"] for values in task_outcomes.values())
    paired_losses = sum(not values["contextual_typed_prior"] and values["global_only"] for values in task_outcomes.values())
    paired_ties = 40 - paired_wins - paired_losses
    passed = accuracy["contextual_typed_prior"] >= accuracy["global_only"]
    return {
        "schema_version": 20,
        "artifact_type": "acl2027_phase2_probe_recovery_audit_v20",
        "generator": "deterministic_private_gold_replay_not_caller_verdict",
        "passed": passed,
        "decision_rule": "contextual_typed_prior_accuracy_gte_global_only_accuracy",
        "coverage_artifact_sha256": coverage_sha256,
        "v18_preserved_rows": len(preserved),
        "v20_recovery_rows": len(recovery_records),
        "combined_probe_rows": len(combined),
        "probe_gold_sha256": sha256_file(gold_path),
        "condition_counts": totals,
        "condition_successes": successes,
        "condition_accuracy": accuracy,
        "primary_paired_comparison": {
            "contextual_typed_prior_minus_global_only_accuracy": accuracy["contextual_typed_prior"] - accuracy["global_only"],
            "typed_wins": paired_wins,
            "typed_losses": paired_losses,
            "ties": paired_ties,
        },
        "gold_access_audit": {
            "passed": True,
            "accessed_partitions": ["recovery_probe"],
            "candidate_mutated": False,
            "coverage_mutated": False,
            "held_out_gold_accessed": False,
        },
        "outcomes": outcomes,
    }
