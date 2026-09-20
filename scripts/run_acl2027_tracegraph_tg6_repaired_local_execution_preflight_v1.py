#!/usr/bin/env python3
"""Validate the closed TraceGraph TG6 repaired local-execution scope."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs" / "acl2027" / "tracegraph_tg6_repaired_local_execution_preflight_v1.json"
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = {
    "task_description", "raw_trajectory", "planner_state", "pddl_params",
    "scene_state", "expert_future_actions", "evaluation_label",
    "phase0_to_phase6_artifact",
}
FALSE_GATES = (
    "official_source_fallback_allowed", "terminal_tg6_retry_or_resume_allowed",
    "network_calls_allowed", "provider_calls_allowed", "model_calls_allowed",
    "api_calls_allowed", "paid_api_calls_allowed", "authorization_receipts_allowed",
    "execution_authorized", "phase6_execution_allowed",
    "phase0_to_phase6_reuse_allowed", "other_models_allowed",
    "other_datasets_allowed", "expanded_batch_allowed", "tuning_allowed",
)
HASH_BINDINGS = (
    ("heldout_schedule", "heldout_schedule_sha256"),
    ("runtime_runner_dryrun", "runtime_runner_dryrun_sha256"),
    ("skillbank", "skillbank_sha256"),
    ("pddl_repair_config", "pddl_repair_config_sha256"),
    ("pddl_repair_manifest", "pddl_repair_manifest_sha256"),
    ("pddl_repair_preflight", "pddl_repair_preflight_sha256"),
    ("pddl_repair_completion_manifest", "pddl_repair_completion_manifest_sha256"),
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if config.get("phase_id") != "TG6-tracegraph-repaired-local-execution-preflight-v1":
        errors.append("wrong repaired TG6 phase")
    if config.get("experiment_line") != "tracegraph-observable-state-skill-composition":
        errors.append("wrong TraceGraph research line")
    if config.get("mode") != "zero_network_repaired_local_execution_scope_only":
        errors.append("wrong repaired execution mode")
    if config.get("episode_count") != 40 or config.get("max_retries") != 0:
        errors.append("exact repaired local episode scope mismatch")
    if config.get("max_steps_per_episode") != 50:
        errors.append("max steps mismatch")
    if config.get("stop_rule") != "stop on first hard invariant violation":
        errors.append("stop rule mismatch")
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
        elif file_sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    derived_root = (root / str(config.get("derived_gamefile_root", ""))).resolve()
    expected_root = (
        root / "artifacts" / "acl2027_tracegraph_tg6_pddl_derived_repair_v1" / "derived"
    ).resolve()
    if not derived_root.is_dir() or derived_root != expected_root:
        errors.append("derived gamefile root mismatch")
    manifest_path = root / str(config.get("pddl_repair_manifest", ""))
    schedule_path = root / str(config.get("heldout_schedule", ""))
    if manifest_path.is_file() and schedule_path.is_file():
        manifest = read_json(manifest_path)
        schedule = read_json(schedule_path)
        tasks = list(schedule.get("tasks") or [])
        rows = list(manifest.get("rows_detail") or [])
        if len(tasks) != 40 or len(rows) != 40:
            errors.append("schedule or repair manifest does not contain exactly 40 tasks")
        if [t.get("task_identity") for t in tasks] != [r.get("task_identity") for r in rows]:
            errors.append("repair manifest order does not match frozen schedule")
        if manifest.get("schedule_sha256") != config.get("heldout_schedule_sha256"):
            errors.append("repair manifest schedule binding mismatch")
        if manifest.get("repaired_task_count") != 8:
            errors.append("repair manifest repaired-task count mismatch")
        for row in rows:
            gamefile = root / str(row.get("derived_gamefile", "")).replace("\\", "/")
            try:
                gamefile.resolve().relative_to(derived_root)
            except ValueError:
                errors.append(f"derived gamefile escapes repair root for {row.get('task_identity')}")
                continue
            if not gamefile.is_file() or file_sha256(gamefile) != row.get("derived_sha256"):
                errors.append(f"derived gamefile fingerprint mismatch for {row.get('task_identity')}")
    return errors


def main() -> int:
    errors = validate(read_json(CONFIG))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"TraceGraph TG6 repaired preflight valid: config_sha256={file_sha256(CONFIG)}; "
        "tasks=40; retries=0; execution_authorized=false; network/provider/model/API=0/0/0/0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
