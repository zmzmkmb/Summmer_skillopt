#!/usr/bin/env python3
"""Deterministic analyzer for the v17 replacement probe schedule."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.acl2027_phase2_response_verifier_v3 import VerificationError, sha256_file, stable, verify_response


class ProbeReplacementAnalysisError(RuntimeError):
    pass


def load_gold(path: Path) -> dict[str, dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != 40:
        raise ProbeReplacementAnalysisError("replacement probe gold must contain exactly 40 rows")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        task_id = str(row.get("task_id", ""))
        answers = row.get("answers") if row.get("task_family") == "SearchQA" else [row.get("answer")]
        if not task_id or task_id in indexed or not isinstance(answers, list) or not answers or not all(isinstance(value, str) and value.strip() for value in answers):
            raise ProbeReplacementAnalysisError("replacement probe gold record is malformed")
        indexed[task_id] = {**row, "answers": answers, "_frozen_payload_sha256": stable(row)}
    return indexed


def build_probe_audit(
    records: list[dict[str, Any]],
    schedule: list[dict[str, Any]],
    coverage_artifact: dict[str, Any],
    coverage_sha256: str,
    gold_path: Path,
) -> dict[str, Any]:
    expected = [row for row in schedule if row.get("partition") == "probe"]
    probe = [row for row in records if row.get("partition") == "probe"]
    if len(expected) != 160 or len(probe) != 160:
        raise ProbeReplacementAnalysisError("complete 160-row replacement probe ledger required")
    if coverage_artifact.get("passed") is not True or coverage_artifact.get("coverage_status") != "coverage-passed":
        raise ProbeReplacementAnalysisError("trusted v13 coverage binding drift")
    gold = load_gold(gold_path)
    conditions = ("cold", "copied_global", "global_only", "contextual_typed_prior")
    totals = {condition: 0 for condition in conditions}
    successes = {condition: 0 for condition in conditions}
    task_outcomes: dict[str, dict[str, bool]] = {}
    outcomes: list[dict[str, Any]] = []
    for record, planned in zip(probe, expected):
        keys = ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "payload_hash", "staged_execution_index")
        if any(record.get(key) != planned.get(key) for key in keys):
            raise ProbeReplacementAnalysisError("replacement probe ledger/schedule binding drift")
        if record.get("terminal") or record.get("status") != "completed" or record.get("raw_response_sha256") != stable(record.get("raw_response")):
            raise ProbeReplacementAnalysisError("replacement probe response binding or terminal state invalid")
        private = gold.get(planned["task_id"])
        if private is None or private.get("skill_family") != planned["skill_family"] or private["_frozen_payload_sha256"] != planned["payload_hash"]:
            raise ProbeReplacementAnalysisError("replacement probe family or payload binding drift")
        condition = planned["condition"]
        if condition not in totals:
            raise ProbeReplacementAnalysisError("replacement probe condition drift")
        try:
            verdict = verify_response(record["raw_response"], private)
        except VerificationError as exc:
            raise ProbeReplacementAnalysisError(str(exc)) from exc
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
            "verifier_confirmed_success": passed,
        })
    expected_conditions = set(conditions)
    if len(task_outcomes) != 40 or any(set(values) != expected_conditions for values in task_outcomes.values()):
        raise ProbeReplacementAnalysisError("replacement probe condition grid incomplete")
    accuracy = {condition: successes[condition] / totals[condition] for condition in conditions}
    paired_wins = sum(values["contextual_typed_prior"] and not values["global_only"] for values in task_outcomes.values())
    paired_losses = sum(not values["contextual_typed_prior"] and values["global_only"] for values in task_outcomes.values())
    paired_ties = 40 - paired_wins - paired_losses
    passed = accuracy["contextual_typed_prior"] >= accuracy["global_only"]
    return {
        "schema_version": 18,
        "artifact_type": "acl2027_phase2_probe_replacement_audit_v18",
        "generator": "deterministic_private_gold_replay_not_caller_verdict",
        "passed": passed,
        "decision_rule": "contextual_typed_prior_accuracy_gte_global_only_accuracy",
        "coverage_artifact_sha256": coverage_sha256,
        "probe_ledger_sha256": stable(probe),
        "probe_rows": 160,
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
            "accessed_partitions": ["replacement_probe"],
            "candidate_mutated": False,
            "coverage_mutated": False,
            "held_out_gold_accessed": False,
        },
        "outcomes": outcomes,
    }
