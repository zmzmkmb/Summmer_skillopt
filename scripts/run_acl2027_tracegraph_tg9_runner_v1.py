#!/usr/bin/env python3
"""Authorization-gated local TG9 factorial runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as env_base
from scripts import run_acl2027_tracegraph_tg9_selector_v1 as selector


CONFIG = ROOT / "configs/acl2027/tracegraph_tg9_runner_candidate_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def authorization_binding(config: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in config.items()
        if key not in {"authorization_receipt", "authorization_receipt_sha256"}
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_config(config: dict[str, Any]) -> list[str]:
    errors = []
    expected = {
        "planned_rows": 180,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_on_first_hard_invariant_violation": True,
        "runtime_allowed_inputs": selector.ALLOWED_INPUTS,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    for key in (
        "network_calls_allowed",
        "provider_calls_allowed",
        "model_calls_allowed",
        "api_calls_allowed",
        "paid_api_calls_allowed",
        "phase0_to_phase6_reuse_allowed",
        "webshop_execution_allowed",
        "other_models_allowed",
        "other_datasets_allowed",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    for key in ("schedule", "selector", "base_skillbank", "interaction_skillbank", "readiness"):
        path = ROOT / str(config.get(key, ""))
        if not path.is_file() or sha256(path) != config.get(f"{key}_sha256"):
            errors.append(f"{key} missing or hash mismatch")
    if config.get("execution_authorized") is not True:
        errors.append("execution_authorized must be true")
    receipt_path = ROOT / str(config.get("authorization_receipt", ""))
    if not receipt_path.is_file() or sha256(receipt_path) != config.get("authorization_receipt_sha256"):
        errors.append("fresh authorization receipt missing or changed")
    else:
        receipt = read_json(receipt_path)
        if receipt.get("status") != "authorized" or receipt.get("reusable") is not False:
            errors.append("authorization receipt is not a one-use authorization")
        if receipt.get("runner_config_binding_sha256") != authorization_binding(config):
            errors.append("authorization receipt binding mismatch")
    readiness_path = ROOT / str(config.get("readiness", ""))
    if readiness_path.is_file():
        readiness = read_json(readiness_path)
        if readiness.get("status") != "passed_for_step_50_blocked_for_step_75":
            errors.append("readiness status mismatch")
        if readiness.get("effective_environment_horizon") != 50:
            errors.append("runner horizon is not readiness-bound")
    return errors


def episode_metrics(transitions: list[dict[str, Any]], success: bool) -> dict[str, Any]:
    snapshots = [row["observable_snapshot_fingerprint"] for row in transitions]
    return {
        "completion_by_step_50": int(success and len(transitions) <= 50),
        "first_object_completion_rate": int(any("put_1" in row["completed_subgoal_ids"] for row in transitions)),
        "second_subgoal_reentry_rate": int(any(row["pending_subgoal_id"] == "search_source_2" for row in transitions)),
        "distinct_source_instance_rate": int(any(row.get("second_source_is_distinct") is True for row in transitions)),
        "second_source_same_as_first_destination": int(any(row.get("second_source_same_as_first_destination") for row in transitions)),
        "ledger_complete_but_env_fail": int(bool(transitions) and not transitions[-1]["subgoal_ledger"]["unresolved_subgoal_ids"] and not success),
        "closed_container_stall": int(any(row["eligibility_rejections"] and any(item["action"].startswith("open ") for item in row["eligibility_rejections"]) for row in transitions)),
        "open_action_eligibility_rejection_rate": sum(any(item["action"].startswith("open ") for item in row["eligibility_rejections"]) for row in transitions) / max(1, len(transitions)),
        "candidate_gap_rate": sum(row["abstained"] for row in transitions) / max(1, len(transitions)),
        "false_progress_rate": sum(row["false_progress_event"] for row in transitions) / max(1, len(transitions)),
        "first_effective_progress_step": next((index + 1 for index, row in enumerate(transitions) if row["progress_event"]), None),
        "episode_two_cycle_incidence": int(any(row["cycle_triggered"] for row in transitions)),
        "unique_snapshot_count": len(set(snapshots)),
        "repeated_snapshot_rate": 1 - len(set(snapshots)) / max(1, len(snapshots)),
    }


def run_episode(builder: Any, base_index: Any, interaction_index: Any, data_root: Path, row: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    gamefile = env_base.resolve_gamefile(data_root, task)
    dataset = "eval_in_distribution" if row["split"] == "valid_seen" else "eval_out_of_distribution"
    env = builder(
        str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"),
        seed=int(row["seed"]), env_num=1, group_n=1, resources_per_worker=None,
        is_train=False, env_kwargs={"eval_dataset": dataset}, gamefiles=[str(gamefile)],
    )
    transitions = []
    historical: list[str] = []
    snapshots: list[str] = []
    ledger = None
    success = False
    try:
        observations, _images, _infos = env.reset()
        for step in range(50):
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            runtime = {"observation": str(observations[0]), "historical_actions": list(historical), "admissible_actions": admissible}
            transition = selector.select_condition(
                base_index, row["condition"], runtime, previous_ledger=ledger,
                previous_snapshots=snapshots, interaction_index=interaction_index,
            )
            transition["step"] = step
            transitions.append(transition)
            snapshots.append(transition["observable_snapshot_fingerprint"])
            ledger = transition["subgoal_ledger"]
            action = transition["terminal_action_decision"]
            historical.append(action)
            observations, _images, _rewards, dones, infos = env.step([action])
            success = bool(infos[0].get("won", False))
            transition["success_after_step"] = success
            if bool(dones[0]):
                break
    finally:
        env.close()
    return {**{key: row[key] for key in ("run_id", "task_identity", "split", "template_key", "replicate_index", "condition", "seed")}, "success": success, "steps": len(transitions), "hard_invariant_violation": None, "metrics": episode_metrics(transitions, success), "transitions": transitions}


def run(config: dict[str, Any], data_root: Path, output: Path) -> dict[str, Any]:
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    schedule = read_json(ROOT / config["schedule"])
    rows = list(schedule["rows"])
    tasks = {row["task_identity"]: row for row in schedule["tasks"]}
    if len(rows) != 180:
        raise ValueError("schedule must contain 180 rows")
    os.environ["ALFWORLD_DATA"] = str(data_root)
    base_index = env_base.load_skill_index(ROOT / config["base_skillbank"])
    interaction_index = env_base.load_skill_index(ROOT / config["interaction_skillbank"])
    builder = env_base.load_alfworld_builder()
    results = []
    violation = None
    for ordinal, row in enumerate(rows):
        try:
            results.append(run_episode(builder, base_index, interaction_index, data_root, row, tasks[row["task_identity"]]))
        except Exception as exc:  # noqa: BLE001
            violation = {"ordinal": ordinal, "run_id": row.get("run_id"), "type": type(exc).__name__, "message": str(exc)}
            break
    payload = {
        "schema_version": "tg9-factorial-result-v1",
        "rows": results,
        "planned_rows": 180,
        "episodes_completed": len(results),
        "hard_invariant_violation": violation,
        "primary_endpoint": "completion_by_step_50",
        "step_75_endpoint_status": "unavailable",
        "max_retries": 0,
        "network_calls": 0, "provider_calls": 0, "model_calls": 0,
        "api_calls": 0, "paid_api_calls": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(read_json(args.config), args.data_root, args.output)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 180 else 1


if __name__ == "__main__":
    raise SystemExit(main())
