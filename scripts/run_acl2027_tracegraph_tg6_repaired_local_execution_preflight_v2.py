#!/usr/bin/env python3
"""Validate the closed TG6 repaired-local-execution scope for repair-v2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v2.json"
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = {
    "task_description",
    "raw_trajectory",
    "planner_state",
    "pddl_params",
    "scene_state",
    "expert_future_actions",
    "evaluation_label",
    "phase0_to_phase6_artifact",
}
FALSE_GATES = (
    "official_source_fallback_allowed",
    "terminal_tg6_retry_or_resume_allowed",
    "network_calls_allowed",
    "provider_calls_allowed",
    "model_calls_allowed",
    "api_calls_allowed",
    "paid_api_calls_allowed",
    "authorization_receipts_allowed",
    "execution_authorized",
    "phase6_execution_allowed",
    "phase0_to_phase6_reuse_allowed",
    "other_models_allowed",
    "other_datasets_allowed",
    "expanded_batch_allowed",
    "tuning_allowed",
)
HASH_BINDINGS = (
    ("heldout_schedule", "heldout_schedule_sha256"),
    ("runtime_runner_dryrun", "runtime_runner_dryrun_sha256"),
    ("skillbank", "skillbank_sha256"),
    ("pddl_repair_manifest", "pddl_repair_manifest_sha256"),
    ("pddl_repair_preflight", "pddl_repair_preflight_sha256"),
    ("zero_step_evidence", "zero_step_evidence_sha256"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG6-tracegraph-repaired-local-execution-preflight-v2",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_repaired_local_execution_scope_only",
        "episode_count": 40,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_rule": "stop on first hard invariant violation",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
    for key in FALSE_GATES:
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    if config.get("fresh_exact_user_authorization_required") is not True:
        errors.append("fresh exact user authorization gate is not closed")
    if config.get("derived_gamefile_manifest_enforced") is not True:
        errors.append("derived gamefile manifest must be enforced")
    if config.get("webshop_status") != "blocked_pending_preregistered_alfworld_mechanism_gate":
        errors.append("WebShop gate relaxed")

    for path_key, hash_key in HASH_BINDINGS:
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")

    repair_manifest_path = root / str(config.get("pddl_repair_manifest", ""))
    repair_preflight_path = root / str(config.get("pddl_repair_preflight", ""))
    evidence_path = root / str(config.get("zero_step_evidence", ""))
    if repair_manifest_path.is_file():
        manifest = read_json(repair_manifest_path)
        if manifest.get("status") != "completed_zero_network_textworld_reset_preflight":
            errors.append("repair-v2 manifest is not finalized")
        if manifest.get("task_count") != 40 or manifest.get("repaired_task_count") != 10:
            errors.append("repair-v2 manifest scope mismatch")
        if manifest.get("zero_step_evidence") != config.get("zero_step_evidence"):
            errors.append("repair-v2 manifest evidence binding mismatch")
    if repair_preflight_path.is_file():
        preflight = read_json(repair_preflight_path)
        if preflight.get("status") != "completed" or preflight.get("task_count") != 40:
            errors.append("repair-v2 preflight is not completed for 40 tasks")
        if preflight.get("repaired_task_count") != 10 or preflight.get("zero_step_passed_task_count") != 40:
            errors.append("repair-v2 preflight result mismatch")
        if preflight.get("episodes_run") != 0 or preflight.get("network_calls") != 0:
            errors.append("repair-v2 preflight has non-zero execution activity")
    if evidence_path.is_file():
        evidence = read_json(evidence_path)
        result = evidence.get("result") or {}
        if evidence.get("evidence_type") != "promoted_exact_zero_step_textworld_result":
            errors.append("zero-step evidence type mismatch")
        if result.get("status") != "passed" or result.get("passed_task_count") != 40:
            errors.append("zero-step evidence is not passed 40/40")
        if result.get("failed_task_count") != 0 or result.get("actions_taken") != 0:
            errors.append("zero-step evidence activity mismatch")

    derived_root = (root / str(config.get("derived_gamefile_root", ""))).resolve()
    expected_root = (root / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/derived").resolve()
    if not derived_root.is_dir() or derived_root != expected_root:
        errors.append("derived gamefile root mismatch")
    return errors


def main() -> int:
    errors = validate(read_json(CONFIG))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"TraceGraph TG6 repaired-v2 preflight valid: config_sha256={sha256(CONFIG)}; "
        "tasks=40; retries=0; execution_authorized=false; "
        "network/provider/model/API=0/0/0/0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
