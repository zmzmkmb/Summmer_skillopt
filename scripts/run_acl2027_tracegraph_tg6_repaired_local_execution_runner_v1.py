#!/usr/bin/env python3
"""Run a future exactly authorized TG6 execution from derived PDDL files only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.run_acl2027_tracegraph_tg6_local_execution_runner_v1 import (
    ALLOWED_INPUTS,
    FORBIDDEN_INPUTS,
    SkillIndex,
    aggregate_trace,
    build_transition,
    file_sha256,
    load_alfworld_builder,
    load_skill_index,
    read_json,
)

ROOT = Path(__file__).resolve().parent.parent
PREFLIGHT_CONFIG = ROOT / "configs" / "acl2027" / "tracegraph_tg6_repaired_local_execution_preflight_v1.json"
AUTHORIZED_CONFIG = ROOT / "configs" / "acl2027" / "tracegraph_tg6_repaired_local_execution_runner_v1.json"


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def validate_authorized_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected_parent = str(PREFLIGHT_CONFIG.relative_to(ROOT)).replace("\\", "/")
    if config.get("phase_id") != "TG6-tracegraph-repaired-local-execution-runner-v1":
        errors.append("wrong repaired runner phase")
    if config.get("parent_scope_config") != expected_parent:
        errors.append("wrong repaired preflight binding")
    if not PREFLIGHT_CONFIG.is_file() or config.get("parent_scope_config_sha256") != file_sha256(PREFLIGHT_CONFIG):
        errors.append("repaired preflight fingerprint mismatch")
    if config.get("experiment_line") != "tracegraph-observable-state-skill-composition":
        errors.append("wrong TraceGraph research line")
    if config.get("episode_count") != 40 or config.get("max_retries") != 0:
        errors.append("exact repaired TG6 episode scope mismatch")
    if config.get("max_steps_per_episode") != 50:
        errors.append("max steps mismatch")
    if config.get("stop_rule") != "stop on first hard invariant violation":
        errors.append("stop rule mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
    for key in (
        "official_source_fallback_allowed",
        "terminal_tg6_retry_or_resume_allowed",
        "network_calls_allowed",
        "provider_calls_allowed",
        "model_calls_allowed",
        "api_calls_allowed",
        "paid_api_calls_allowed",
        "authorization_receipts_allowed",
        "phase6_execution_allowed",
        "phase0_to_phase6_reuse_allowed",
        "other_models_allowed",
        "other_datasets_allowed",
        "expanded_batch_allowed",
        "tuning_allowed",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    if config.get("execution_authorized") is not True:
        errors.append("fresh exact repaired-execution authorization is not bound")
    if config.get("derived_gamefile_manifest_enforced") is not True:
        errors.append("derived gamefile manifest must be enforced")
    if config.get("webshop_status") != "blocked_pending_preregistered_alfworld_mechanism_gate":
        errors.append("WebShop gate relaxed")
    for path_key, hash_key in (
        ("heldout_schedule", "heldout_schedule_sha256"),
        ("runtime_runner_dryrun", "runtime_runner_dryrun_sha256"),
        ("skillbank", "skillbank_sha256"),
        ("pddl_repair_manifest", "pddl_repair_manifest_sha256"),
        ("pddl_repair_preflight", "pddl_repair_preflight_sha256"),
        ("pddl_repair_completion_manifest", "pddl_repair_completion_manifest_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif file_sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    expected_root = (root / "artifacts" / "acl2027_tracegraph_tg6_pddl_derived_repair_v1" / "derived").resolve()
    configured_root = (root / str(config.get("derived_gamefile_root", ""))).resolve()
    if not configured_root.is_dir() or configured_root != expected_root:
        errors.append("derived gamefile root mismatch")
    return errors


def load_derived_gamefiles(
    config: dict[str, Any], tasks: list[dict[str, Any]], root: Path = ROOT
) -> dict[str, Path]:
    derived_root = root / str(config["derived_gamefile_root"])
    manifest = read_json(root / str(config["pddl_repair_manifest"]))
    rows = list(manifest.get("rows_detail") or [])
    if [task.get("task_identity") for task in tasks] != [row.get("task_identity") for row in rows]:
        raise ValueError("repair manifest order does not match frozen schedule")
    gamefiles: dict[str, Path] = {}
    for row in rows:
        task_identity = str(row["task_identity"])
        gamefile = root / str(row["derived_gamefile"]).replace("\\", "/")
        if not gamefile.is_file() or not _within(gamefile, derived_root):
            raise ValueError(f"invalid derived gamefile for {task_identity}")
        if file_sha256(gamefile) != row.get("derived_sha256"):
            raise ValueError(f"derived gamefile fingerprint mismatch for {task_identity}")
        gamefiles[task_identity] = gamefile
    if len(gamefiles) != 40:
        raise ValueError("derived gamefile manifest must bind exactly 40 unique tasks")
    return gamefiles


def run_episode(
    build_env: Any,
    index: SkillIndex,
    gamefile: Path,
    task: dict[str, Any],
    seed: int,
    max_steps: int,
) -> dict[str, Any]:
    split = str(task["split"])
    eval_dataset = "eval_in_distribution" if split == "valid_seen" else "eval_out_of_distribution"
    env = build_env(
        str(ROOT / "skillopt" / "envs" / "alfworld" / "vendor" / "config_tw.yaml"),
        seed=seed,
        env_num=1,
        group_n=1,
        resources_per_worker=None,
        is_train=False,
        env_kwargs={"eval_dataset": eval_dataset},
        gamefiles=[str(gamefile)],
    )
    transitions: list[dict[str, Any]] = []
    historical_actions: list[str] = []
    success = False
    stop_reason = "max_steps"
    try:
        observations, _images, _infos = env.reset()
        for step in range(max_steps):
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            transition = build_transition(index, observations[0], historical_actions, admissible)
            transition["step"] = step
            transitions.append(transition)
            action = transition["terminal_action_decision"]
            historical_actions.append(action)
            observations, _images, _rewards, dones, infos = env.step([action])
            success = bool(infos[0].get("won", False))
            if bool(dones[0]):
                stop_reason = "success" if success else "environment_done"
                break
        return {
            "task_identity": task["task_identity"],
            "split": split,
            "task_relative_path": task["task_relative_path"],
            "derived_gamefile": str(gamefile.relative_to(ROOT)).replace("\\", "/"),
            "derived_gamefile_sha256": file_sha256(gamefile),
            "success": success,
            "steps": len(transitions),
            "stop_reason": stop_reason,
            "hard_invariant_violation": None,
            "trace": aggregate_trace(transitions),
            "transitions": transitions,
        }
    finally:
        env.close()


def run(config: dict[str, Any], output: Path, config_path: Path) -> dict[str, Any]:
    errors = validate_authorized_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    if output.exists():
        raise FileExistsError(f"refusing to overwrite repaired TG6 output: {output}")
    schedule = read_json(ROOT / config["heldout_schedule"])
    tasks = list(schedule.get("tasks") or [])
    if len(tasks) != 40:
        raise ValueError("frozen schedule must contain exactly 40 tasks")
    gamefiles = load_derived_gamefiles(config, tasks)
    index = load_skill_index(ROOT / config["skillbank"])
    build_env = load_alfworld_builder()
    rows: list[dict[str, Any]] = []
    hard_violation: dict[str, Any] | None = None
    for ordinal, task in enumerate(tasks):
        try:
            rows.append(run_episode(build_env, index, gamefiles[str(task["task_identity"])], task, 42 + ordinal, int(config["max_steps_per_episode"])))
        except Exception as exc:  # noqa: BLE001
            hard_violation = {"task_identity": task.get("task_identity"), "ordinal": ordinal, "type": type(exc).__name__, "message": str(exc)}
            rows.append({"task_identity": task.get("task_identity"), "split": task.get("split"), "task_relative_path": task.get("task_relative_path"), "success": False, "steps": 0, "stop_reason": "hard_invariant_violation", "hard_invariant_violation": hard_violation})
            break
    result = {
        "experiment_line": config["experiment_line"],
        "phase_id": config["phase_id"],
        "config_sha256": file_sha256(config_path),
        "task_count": len(tasks),
        "episodes_started": len(rows),
        "episodes_completed": sum(row.get("hard_invariant_violation") is None for row in rows),
        "successes": sum(row.get("success") is True for row in rows),
        "hard_invariant_violation": hard_violation,
        "stop_rule": config["stop_rule"],
        "max_retries": config["max_retries"],
        "runtime_allowed_inputs": config["runtime_allowed_inputs"],
        "derived_gamefile_root": config["derived_gamefile_root"],
        "official_source_fallback_used": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=AUTHORIZED_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.config.is_file():
        print("ERROR: no authorized repaired-runner config exists; exact user authorization is required", file=sys.stderr)
        return 2
    try:
        result = run(read_json(args.config), args.output, args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"TG6 repaired local runner: started {result['episodes_started']}/{result['task_count']} episodes; "
        f"completed={result['episodes_completed']}; successes={result['successes']}; "
        "official_fallback=false; network/provider/model/API=0/0/0/0"
    )
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
