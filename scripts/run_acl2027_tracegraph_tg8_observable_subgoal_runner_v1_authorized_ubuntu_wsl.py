#!/usr/bin/env python3
"""Execute the exact authorized TG8 v4 WSL factorial run."""
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

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as env_base  # noqa: E402
from scripts import run_acl2027_tracegraph_tg6_trajectory_failure_analysis_runner_v1 as trace_base  # noqa: E402
from scripts import run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3 as selector  # noqa: E402

CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_runner_v1_authorized_ubuntu_wsl.json"
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
PREFLIGHT_AGGREGATE = "098bee6f10b47fb8dbe656785c3732a949448047f72bb0454bb48545299ceffe"
PREFLIGHT_ARTIFACT_SHA256 = "7144406aea76ff0583b6dd04256306f65498eb04b53001184fe1c58f1c2a47e3"
SCHEDULE_SHA256 = "1115337803f8899e0637f69643f169d0de3bc67fe8e9f7e2f021e6b914695aa7"
SELECTOR_SHA256 = "6aae3a8539594bdb65bdeab92f9d82c2de9ac0e287f036af1e83157751636622"
SELECTOR_CONFIG_SHA256 = "36407699541289ea42a69362f1a6a3c2582648b1e1b7680781ed6725ee066582"
READINESS_SHA256 = "85627fd938abce62e254a68957893f81b1389cc0a7e6519976d338a15ed3904b"
READINESS_TASKS = 30
ROWS = 360
MAX_STEPS = 75


class EpisodeExecutionError(RuntimeError):
    def __init__(self, message: str, transitions: list[dict[str, Any]]):
        super().__init__(message)
        self.transitions = transitions


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _path(root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def _check_hash(errors: list[str], root: Path, path_value: str, expected: str, label: str) -> Path | None:
    path = _path(root, path_value)
    if not path.is_file():
        errors.append(f"{label} missing")
        return None
    if sha256(path) != expected:
        errors.append(f"{label} hash mismatch")
    return path


def validate_authorized_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG8-tracegraph-observable-subgoal-runner-v1-authorized-ubuntu-wsl",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "authorized_zero_network_runner",
        "development_task_count": 30,
        "condition_count": 4,
        "planned_episode_rows": ROWS,
        "max_steps_per_episode": MAX_STEPS,
        "max_retries": 0,
        "execution_authorized": True,
        "episode_execution_allowed": True,
        "readiness_only_allowed": False,
        "authorization_status": "authorized",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if config.get("stop_rule") != "stop on first hard invariant violation and invalidate the full factorial run":
        errors.append("stop rule mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime input boundary mismatch")
    if tuple(item.get("id") for item in config.get("conditions") or []) != selector.CONDITIONS:
        errors.append("condition order mismatch")
    for key in ("network_calls_allowed", "provider_calls_allowed", "model_calls_allowed", "api_calls_allowed", "paid_api_calls_allowed", "phase0_to_phase6_reuse_allowed", "phase6_execution_allowed", "webshop_execution_allowed", "other_models_allowed", "other_datasets_allowed", "tuning_on_parent_heldout_allowed", "official_source_fallback_allowed"):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")

    preflight = _check_hash(errors, root, str(config.get("preflight_artifact", "")), PREFLIGHT_ARTIFACT_SHA256, "preflight artifact")
    schedule = _check_hash(errors, root, str(config.get("development_schedule", "")), SCHEDULE_SHA256, "development schedule")
    selector_path = _check_hash(errors, root, str(config.get("selector", "")), SELECTOR_SHA256, "selector")
    selector_cfg = _check_hash(errors, root, str(config.get("selector_config", "")), SELECTOR_CONFIG_SHA256, "selector config")
    readiness = _check_hash(errors, root, str(config.get("readiness_artifact", "")), READINESS_SHA256, "readiness artifact")
    runner_path = _path(root, str(config.get("runner", "")))
    if not runner_path.is_file() or sha256(runner_path) != config.get("runner_sha256"):
        errors.append("authorized runner missing or changed")

    if preflight is not None:
        payload = read_json(preflight)
        if payload.get("aggregate_fingerprint") != PREFLIGHT_AGGREGATE or payload.get("planned_episode_rows") != ROWS or payload.get("readiness_allowed") is not False:
            errors.append("preflight binding mismatch")
    if schedule is not None:
        payload = read_json(schedule)
        rows = list(payload.get("rows") or [])
        tasks = list(payload.get("tasks") or [])
        if len(tasks) != READINESS_TASKS or len({task.get("task_identity") for task in tasks}) != READINESS_TASKS:
            errors.append("schedule task identity mismatch")
        if len(rows) != ROWS or len({row.get("run_id") for row in rows}) != ROWS:
            errors.append("schedule row identity mismatch")
        if any(row.get("max_steps") != MAX_STEPS or row.get("primary_step_landmark") != 50 for row in rows):
            errors.append("schedule step landmark mismatch")
    if selector_cfg is not None:
        payload = read_json(selector_cfg)
        if payload.get("selector_sha256") != SELECTOR_SHA256 or payload.get("readiness_allowed") is not False:
            errors.append("selector config binding mismatch")
    if readiness is not None:
        payload = read_json(readiness)
        if not (payload.get("status") == "passed" and payload.get("task_count") == READINESS_TASKS and payload.get("passed_task_count") == READINESS_TASKS and payload.get("failed_task_count") == 0 and payload.get("selector_probe_count") == 120 and payload.get("episodes_run") == 0 and payload.get("actions_taken") == 0):
            errors.append("readiness gate mismatch")

    receipt_path = _path(root, str(config.get("authorization_receipt", "")))
    if not receipt_path.is_file() or sha256(receipt_path) != config.get("authorization_receipt_sha256"):
        errors.append("authorization receipt missing or changed")
    else:
        receipt = read_json(receipt_path)
        if receipt.get("status") != "authorized" or receipt.get("authorization_opened") is not True:
            errors.append("authorization receipt is not open")
        bindings = receipt.get("bindings") or {}
        expected_bindings = {
            "preflight_aggregate_fingerprint": PREFLIGHT_AGGREGATE,
            "selector_sha256": SELECTOR_SHA256,
            "selector_config_sha256": SELECTOR_CONFIG_SHA256,
            "readiness_artifact_sha256": READINESS_SHA256,
        }
        for key, value in expected_bindings.items():
            if bindings.get(key) != value:
                errors.append(f"receipt {key} mismatch")
        scope = receipt.get("scope") or {}
        if scope.get("planned_episode_rows") != ROWS or scope.get("max_steps_per_episode") != MAX_STEPS or scope.get("max_retries") != 0 or scope.get("runtime_allowed_inputs") != ALLOWED_INPUTS or scope.get("stop_rule") != config.get("stop_rule"):
            errors.append("receipt scope mismatch")
    return errors


def load_schedule(config: dict[str, Any], root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = read_json(_path(root, str(config["development_schedule"])))
    tasks = list(payload["tasks"])
    rows = list(payload["rows"])
    if len(tasks) != READINESS_TASKS or len(rows) != ROWS:
        raise ValueError("TG8 schedule cardinality mismatch")
    task_map = {str(task["task_identity"]): task for task in tasks}
    if len(task_map) != READINESS_TASKS:
        raise ValueError("TG8 task identities are not unique")
    for row in rows:
        if row.get("task_identity") not in task_map or row.get("condition") not in selector.CONDITIONS:
            raise ValueError("TG8 row references an unknown task or condition")
        if row.get("max_steps") != MAX_STEPS or row.get("primary_step_landmark") != 50:
            raise ValueError("TG8 row step contract mismatch")
    return rows, task_map


def episode_metrics(transitions: list[dict[str, Any]], success: bool) -> dict[str, Any]:
    actions = [row["terminal_action_decision"] for row in transitions]
    snapshots = [row["observable_snapshot_fingerprint"] for row in transitions]
    completed_at = next((row["step"] + 1 for row in transitions if row.get("success_after_step")), None)
    return {
        "transition_count": len(transitions),
        "success": success,
        "completion_by_step_50": bool(success and completed_at is not None and completed_at <= 50),
        "completion_by_step_75": bool(success and completed_at is not None and completed_at <= 75),
        "episode_two_cycle_incidence_by_step_50": trace_base.has_two_cycle(actions[:50]),
        "observable_progress_event_rate": sum(bool(row.get("progress_event")) for row in transitions) / len(transitions) if transitions else 0.0,
        "false_progress_rate": sum(bool(row.get("false_progress_event")) for row in transitions) / len(transitions) if transitions else 0.0,
        "first_progress_step": next((row["step"] for row in transitions if row.get("progress_event")), None),
        "repeated_snapshot_rate": sum(bool(row.get("repeated_observable_snapshot")) for row in transitions) / len(transitions) if transitions else 0.0,
        "unique_snapshot_count": len(set(snapshots)),
        "ledger_validity": all(row.get("subgoal_ledger_valid") is True for row in transitions),
        "ledger_provenance_completeness": all(row.get("subgoal_ledger_provenance_complete") is True for row in transitions),
        "trace_validity": all(env_base.validate_transition(row)[0] for row in transitions),
        "terminal_admissibility": all(row["terminal_action_decision"] in row["runtime_inputs"]["admissible_actions"] for row in transitions),
        "history_truncation": any(len(row["runtime_inputs"]["historical_actions"]) > 75 for row in transitions),
    }


def run_row(builder: Any, index: env_base.SkillIndex, data_root: Path, row: dict[str, Any], task: dict[str, Any], max_steps: int) -> dict[str, Any]:
    gamefile = env_base.resolve_gamefile(data_root, task)
    if not gamefile.is_file():
        raise FileNotFoundError(gamefile)
    dataset = "eval_in_distribution" if row["split"] == "valid_seen" else "eval_out_of_distribution"
    env = builder(str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"), seed=int(row["seed"]), env_num=1, group_n=1, resources_per_worker=None, is_train=False, env_kwargs={"eval_dataset": dataset}, gamefiles=[str(gamefile)])
    transitions: list[dict[str, Any]] = []
    historical: list[str] = []
    snapshots: list[str] = []
    skills: list[str | None] = []
    edges: list[list[str] | None] = []
    ledger: dict[str, Any] | None = None
    success = False
    stop_reason = "max_steps"
    try:
        observations, _images, _infos = env.reset()
        for step in range(max_steps):
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            runtime_inputs = {"observation": str(observations[0]), "historical_actions": list(historical), "admissible_actions": list(admissible)}
            transition = selector.select_condition(index, row["condition"], runtime_inputs, previous_ledger=ledger, previous_snapshots=snapshots, previous_skills=skills, previous_edges=edges)
            valid, message = selector.validate_selector_transition(transition, ledger, index=index)
            if not valid:
                raise EpisodeExecutionError(f"selector invariant: {message}", transitions)
            transition["step"] = step
            transitions.append(transition)
            snapshots.append(transition["observable_snapshot_fingerprint"])
            skills.append(transition["selected_skill_id"])
            edges.append(transition["selected_edge"])
            ledger = transition["subgoal_ledger"]
            action = transition["terminal_action_decision"]
            historical.append(action)
            observations, _images, _rewards, dones, infos = env.step([action])
            success = bool(infos[0].get("won", False))
            transition["success_after_step"] = success
            if bool(dones[0]):
                stop_reason = "success" if success else "environment_done"
                break
        return {"run_id": row["run_id"], "task_identity": row["task_identity"], "task_ordinal": row["task_ordinal"], "split": row["split"], "task_family": row["task_family"], "template_key": row["template_key"], "replicate_index": row["replicate_index"], "condition": row["condition"], "condition_position": row["condition_position"], "latin_rotation": row["latin_rotation"], "seed": row["seed"], "gamefile": str(gamefile), "gamefile_sha256": sha256(gamefile), "success": success, "steps": len(transitions), "stop_reason": stop_reason, "hard_invariant_violation": None, "metrics": episode_metrics(transitions, success), "transitions": transitions}
    except Exception as exc:
        if isinstance(exc, EpisodeExecutionError):
            raise
        raise EpisodeExecutionError(str(exc), transitions) from exc
    finally:
        env.close()


def run(config: dict[str, Any], data_root: Path, output: Path) -> dict[str, Any]:
    errors = validate_authorized_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")
    rows, task_map = load_schedule(config)
    # ALFWorld's vendored YAML expands $ALFWORLD_DATA inside each worker.
    # Bind it explicitly to the authorized WSL data root before spawning workers.
    os.environ["ALFWORLD_DATA"] = str(data_root)
    index = selector.base.load_skill_index(ROOT / str(config["skillbank"]))
    builder = env_base.load_alfworld_builder()
    results: list[dict[str, Any]] = []
    hard_violation: dict[str, Any] | None = None
    actions_taken = 0
    for ordinal, row in enumerate(rows):
        task = task_map[str(row["task_identity"])]
        try:
            episode = run_row(builder, index, data_root, row, task, int(row["max_steps"]))
            actions_taken += len(episode["transitions"])
            results.append(episode)
        except Exception as exc:  # noqa: BLE001
            partial_transitions = list(getattr(exc, "transitions", []))
            hard_violation = {"run_id": row.get("run_id"), "task_identity": row.get("task_identity"), "condition": row.get("condition"), "ordinal": ordinal, "type": type(exc).__name__, "message": str(exc)}
            actions_taken += len(partial_transitions)
            results.append({"run_id": row.get("run_id"), "task_identity": row.get("task_identity"), "task_ordinal": row.get("task_ordinal"), "split": row.get("split"), "task_family": row.get("task_family"), "template_key": row.get("template_key"), "replicate_index": row.get("replicate_index"), "condition": row.get("condition"), "seed": row.get("seed"), "success": False, "steps": len(partial_transitions), "stop_reason": "hard_invariant_violation", "hard_invariant_violation": hard_violation, "metrics": None, "transitions": partial_transitions})
            break
    result = {"schema_version": 1, "phase_id": config["phase_id"], "artifact_type": "tracegraph_tg8_observable_subgoal_factorial_execution", "preflight_aggregate_fingerprint": PREFLIGHT_AGGREGATE, "selector_sha256": SELECTOR_SHA256, "selector_config_sha256": SELECTOR_CONFIG_SHA256, "readiness_artifact_sha256": READINESS_SHA256, "task_count": READINESS_TASKS, "planned_episode_rows": ROWS, "rows": results, "episodes_started": len(results), "episodes_completed": sum(item.get("hard_invariant_violation") is None for item in results), "successes": sum(item.get("success") is True for item in results), "actions_taken": actions_taken, "hard_invariant_violation": hard_violation, "stop_rule": config["stop_rule"], "max_steps_per_episode": MAX_STEPS, "max_retries": 0, "runtime_allowed_inputs": ALLOWED_INPUTS, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "api_calls": 0, "paid_api_calls": 0, "execution_authorized": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = read_json(args.config)
    output = args.output or _path(ROOT, str(config.get("episode_result_output", "")))
    try:
        result = run(config, args.data_root, output)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"TG8 authorized WSL runner: rows={result['episodes_started']}/{ROWS}; completed={result['episodes_completed']}; successes={result['successes']}; actions={result['actions_taken']}; network/provider/model/API/paid=0/0/0/0/0")
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == ROWS else 1


if __name__ == "__main__":
    raise SystemExit(main())
