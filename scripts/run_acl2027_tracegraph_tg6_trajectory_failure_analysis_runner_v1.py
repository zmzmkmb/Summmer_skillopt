#!/usr/bin/env python3
"""Run or readiness-audit the closed TG6 trajectory diagnostic.

The default closed configuration can perform only zero-step environment
readiness. Episode execution requires a separately versioned authorized
configuration and an explicit --execute flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_runner_v1.json"
PREFLIGHT = ROOT / "configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_preflight_v2.json"
SCHEDULE = ROOT / "artifacts/acl2027_tracegraph_tg6_trajectory_failure_analysis_preflight_v2/development_schedule.json"
SKILLBANK = ROOT / "artifacts/acl2027_tracegraph_tg1_skillbank_construction_v2/skillbank.jsonl"
NOTE = ROOT / "paper/acl2027/TRACEGRAPH_TG6_TRAJECTORY_FAILURE_ANALYSIS_IMPLEMENTATION_NOTE_V1.md"
SkillIndex = base.SkillIndex

CONDITIONS = (
    "baseline_first_eligible",
    "history_aware_anti_cycle",
    "observable_progress_aware",
)
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = set(base.FORBIDDEN_INPUTS)
REQUIRED_TRACE_FIELDS = set(base.REQUIRED_TRACE_FIELDS) | {
    "observable_snapshot_fingerprint",
    "action_state_fingerprint",
    "cycle_triggered",
    "action_seen_before",
    "skill_changed",
    "edge_changed",
    "selector_condition",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def snapshot_fingerprint(observation: str, admissible_actions: list[str]) -> str:
    return base.fingerprint(
        {
            "observation": str(observation),
            "admissible_actions": [str(item) for item in admissible_actions],
        }
    )


def action_state_fingerprint(snapshot: str, action: str) -> str:
    return base.fingerprint({"observable_snapshot_fingerprint": snapshot, "action": str(action)})


def detect_two_cycle(actions: list[str]) -> tuple[bool, tuple[str, str] | None]:
    if len(actions) < 4:
        return False, None
    a, b, c, d = actions[-4:]
    if a == c and b == d and a != b:
        return True, (a, b)
    return False, None


def has_two_cycle(actions: list[str]) -> bool:
    return any(
        actions[index] == actions[index + 2]
        and actions[index + 1] == actions[index + 3]
        and actions[index] != actions[index + 1]
        for index in range(max(len(actions) - 3, 0))
    )


def cycle_participating_positions(actions: list[str]) -> set[int]:
    positions: set[int] = set()
    for index in range(max(len(actions) - 3, 0)):
        window = actions[index : index + 4]
        if (
            len(window) == 4
            and window[0] == window[2]
            and window[1] == window[3]
            and window[0] != window[1]
        ):
            positions.update(range(index, index + 4))
    return positions


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG6-tracegraph-trajectory-failure-analysis-runner-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_runner_preflight",
        "parent_preflight": str(PREFLIGHT.relative_to(root)).replace("\\", "/"),
        "development_task_count": 24,
        "condition_count": 3,
        "planned_episode_rows": 72,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_rule": "stop on first hard invariant violation",
        "execution_authorized": False,
        "readiness_only_allowed": True,
        "episode_execution_allowed": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
    if tuple(item.get("id") for item in config.get("conditions") or []) != CONDITIONS:
        errors.append("condition order mismatch")
    selector = config.get("selector_definition") or {}
    if selector.get("snapshot_fingerprint_excludes_historical_actions") is not True:
        errors.append("snapshot fingerprint must exclude historical_actions")
    for key in (
        "official_source_fallback_allowed",
        "network_calls_allowed",
        "provider_calls_allowed",
        "model_calls_allowed",
        "api_calls_allowed",
        "paid_api_calls_allowed",
        "phase0_to_phase6_reuse_allowed",
        "phase6_execution_allowed",
        "webshop_execution_allowed",
        "other_models_allowed",
        "other_datasets_allowed",
        "tuning_on_parent_heldout_allowed",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    if config.get("fresh_exact_user_authorization_required") is not True:
        errors.append("fresh exact user authorization gate missing")
    for path_key, path, hash_key in (
        ("parent_preflight", root / str(config.get("parent_preflight", "")), "parent_preflight_sha256"),
        ("development_schedule", root / str(config.get("development_schedule", "")), "development_schedule_sha256"),
        ("skillbank", root / str(config.get("skillbank", "")), "skillbank_sha256"),
        ("implementation_note", root / str(config.get("implementation_note", "")), "implementation_note_sha256"),
    ):
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif config.get(hash_key) in (None, "", f"PENDING_{path_key.upper()}_SHA256"):
            errors.append(f"{path_key} hash is not finalized")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    return errors


def load_schedule(config: dict[str, Any], root: Path = ROOT) -> list[dict[str, Any]]:
    schedule = read_json(root / str(config["development_schedule"]))
    tasks = list(schedule.get("tasks") or [])
    if len(tasks) != 24:
        raise ValueError("development schedule must contain exactly 24 tasks")
    if len({str(task.get("task_identity")) for task in tasks}) != 24:
        raise ValueError("development task identities are not unique")
    if sum(task.get("stratum") == "direct_cycle_replication" for task in tasks) != 9:
        raise ValueError("direct-cycle stratum count mismatch")
    if sum(task.get("stratum") == "multi_step_transfer" for task in tasks) != 15:
        raise ValueError("transfer stratum count mismatch")
    return tasks


def resolve_gamefile(data_root: Path, task: dict[str, Any]) -> Path:
    relative = Path(str(task["task_relative_path"]))
    return data_root / "json_2.1.1" / relative / "game.tw-pddl"


def _candidate_pairs(
    index: base.SkillIndex, admissible_actions: list[str]
) -> tuple[dict[str, list[str]], list[str], list[tuple[int, str, str]]]:
    command_candidates = {
        command: index.matching_skill_ids(command)
        for command in admissible_actions
    }
    candidate_ids = sorted({skill_id for ids in command_candidates.values() for skill_id in ids})
    pairs = [
        (ordinal, command, skill_id)
        for ordinal, command in enumerate(admissible_actions)
        for skill_id in command_candidates[command]
    ]
    return command_candidates, candidate_ids, pairs


def _baseline_choice(
    command_candidates: dict[str, list[str]], admissible_actions: list[str]
) -> tuple[str | None, str | None]:
    for command in admissible_actions:
        if command_candidates[command]:
            return command, command_candidates[command][0]
    return None, None


def select_condition(
    index: base.SkillIndex,
    condition: str,
    runtime_inputs: dict[str, Any],
    previous_snapshots: list[str],
    previous_skills: list[str | None],
    previous_edges: list[list[str] | None],
) -> dict[str, Any]:
    if list(runtime_inputs) != ALLOWED_INPUTS:
        raise ValueError("runtime inputs must contain exactly the three observable fields")
    admissible = [str(item) for item in runtime_inputs["admissible_actions"] if str(item).strip()]
    historical = [str(item) for item in runtime_inputs["historical_actions"]]
    if not admissible:
        raise ValueError("environment returned no admissible action")

    command_candidates, candidate_ids, pairs = _candidate_pairs(index, admissible)
    cycle_triggered, cycle_pair = detect_two_cycle(historical)
    selected_command, selected_skill = _baseline_choice(command_candidates, admissible)
    selection_reason = "first_eligible"

    if cycle_triggered and condition == "history_aware_anti_cycle":
        outside = [
            (ordinal, command, skill_id)
            for ordinal, command, skill_id in pairs
            if cycle_pair is None or command not in cycle_pair
        ]
        if outside:
            _, selected_command, selected_skill = outside[0]
            selection_reason = "outside_detected_cycle_pair"

    if cycle_triggered and condition == "observable_progress_aware":
        seen_actions = set(historical)
        previous_skill = previous_skills[-1] if previous_skills else None
        cycle_pair_set = set(cycle_pair or ())
        ranked = sorted(
            pairs,
            key=lambda item: (
                item[1] in seen_actions,
                item[2] == previous_skill,
                item[1] in cycle_pair_set,
                item[0],
                item[2],
            ),
        )
        if ranked:
            _, selected_command, selected_skill = ranked[0]
            selection_reason = "observable_progress_rank"

    non_help = [command for command in admissible if base.normalize_text(command) != "help"]
    terminal = selected_command or (non_help[0] if non_help else admissible[0])
    if selected_command is None:
        selection_reason = "fallback_no_eligible_skill"

    rejections = [
        {"action": command, "reason": "no eligible train-derived canonical action"}
        for command, skill_ids in command_candidates.items()
        if not skill_ids
    ]
    permitted_edges = []
    if selected_skill is not None:
        permitted_edges = [
            [selected_skill, candidate_id]
            for candidate_id in candidate_ids
            if candidate_id != selected_skill
        ]
    selected_edge = permitted_edges[0] if permitted_edges else None
    current_snapshot = snapshot_fingerprint(
        str(runtime_inputs["observation"]), admissible
    )
    repeated_snapshot = current_snapshot in set(previous_snapshots)
    previous_action = historical[-1] if historical else None
    previous_edge = previous_edges[-1] if previous_edges else None

    return {
        "candidate_skill_ids": candidate_ids,
        "eligibility_rejections": rejections,
        "permitted_edges": permitted_edges,
        "selected_skill_id": selected_skill,
        "selected_edge": selected_edge,
        "terminal_action_decision": terminal,
        "abstained": selected_skill is None,
        "observable_snapshot_fingerprint": current_snapshot,
        "action_state_fingerprint": action_state_fingerprint(current_snapshot, terminal),
        "cycle_triggered": cycle_triggered,
        "action_seen_before": terminal in set(historical),
        "skill_changed": bool(previous_skills) and selected_skill != previous_skills[-1],
        "edge_changed": bool(previous_skills) and selected_edge != previous_edge,
        "selector_condition": condition,
        "selection_reason": selection_reason,
        "repeated_observable_snapshot": repeated_snapshot,
    }


def build_transition(
    index: base.SkillIndex,
    condition: str,
    observation: str,
    historical_actions: list[str],
    admissible_actions: list[str],
    previous_snapshots: list[str],
    previous_skills: list[str | None],
    previous_edges: list[list[str] | None],
) -> dict[str, Any]:
    runtime_inputs = {
        "observation": str(observation),
        "historical_actions": [str(item) for item in historical_actions],
        "admissible_actions": [str(item) for item in admissible_actions],
    }
    transition = {
        "runtime_inputs": runtime_inputs,
        "observable_state_fingerprint": base.fingerprint(runtime_inputs),
        **select_condition(
            index,
            condition,
            runtime_inputs,
            previous_snapshots,
            previous_skills,
            previous_edges,
        ),
    }
    valid, message = base.validate_transition(transition)
    if not valid:
        raise RuntimeError(message)
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        raise RuntimeError("trajectory diagnostic trace incomplete")
    return transition


def run_zero_step_readiness(
    config: dict[str, Any], data_root: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite readiness output: {output}")
    tasks = load_schedule(config)
    builder = base.load_alfworld_builder()
    rows: list[dict[str, Any]] = []
    for ordinal, task in enumerate(tasks):
        gamefile = resolve_gamefile(data_root, task)
        row: dict[str, Any] = {
            "task_identity": task["task_identity"],
            "split": task["split"],
            "task_relative_path": task["task_relative_path"],
            "gamefile": str(gamefile),
            "gamefile_sha256": sha256(gamefile) if gamefile.is_file() else None,
            "actions_taken": 0,
        }
        if not gamefile.is_file():
            row.update({"status": "failed", "error_type": "FileNotFoundError", "error": str(gamefile)})
            rows.append(row)
            continue
        dataset = "eval_in_distribution" if task["split"] == "valid_seen" else "eval_out_of_distribution"
        env = builder(
            str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"),
            seed=1000 + ordinal,
            env_num=1,
            group_n=1,
            resources_per_worker=None,
            is_train=False,
            env_kwargs={"eval_dataset": dataset},
            gamefiles=[str(gamefile)],
        )
        try:
            observations, _images, infos = env.reset()
            row.update(
                {
                    "status": "passed",
                    "observation_present": bool(observations and observations[0]),
                    "info_present": bool(infos and isinstance(infos[0], dict)),
                }
            )
        except Exception as exc:  # noqa: BLE001
            row.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        finally:
            env.close()
        rows.append(row)
    passed = sum(row["status"] == "passed" for row in rows)
    result = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "artifact_type": "tracegraph_tg6_trajectory_failure_analysis_zero_step_readiness",
        "status": "passed" if passed == len(rows) == 24 else "blocked_environment_readiness",
        "task_count": len(rows),
        "passed_task_count": passed,
        "failed_task_count": len(rows) - passed,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _episode_metrics(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    actions = [row["terminal_action_decision"] for row in transitions]
    snapshots = [row["observable_snapshot_fingerprint"] for row in transitions]
    skills = [row["selected_skill_id"] for row in transitions]
    edges = [row["selected_edge"] for row in transitions]
    cycle_positions = cycle_participating_positions(actions)
    two_cycle = has_two_cycle(actions)
    return {
        "transition_count": len(transitions),
        "two_cycle_episode": two_cycle,
        "cycle_participating_action_count": len(cycle_positions),
        "cycle_step_rate": len(cycle_positions) / max(len(actions) - 3, 1),
        "repeated_snapshot_episode": len(set(snapshots)) < len(snapshots),
        "repeated_snapshot_count": len(snapshots) - len(set(snapshots)),
        "unique_action_count": len(set(actions)),
        "unique_observable_snapshot_count": len(set(snapshots)),
        "skill_switch_count": sum(a != b for a, b in zip(skills, skills[1:])),
        "edge_switch_count": sum(a != b for a, b in zip(edges, edges[1:])),
        "abstention_count": sum(row["abstained"] for row in transitions),
        "terminal_actions_all_admissible": all(
            row["terminal_action_decision"] in row["runtime_inputs"]["admissible_actions"]
            for row in transitions
        ),
        "trace_valid": all(base.validate_transition(row)[0] for row in transitions),
    }


def run_episode(
    builder: Any,
    index: base.SkillIndex,
    data_root: Path,
    task: dict[str, Any],
    condition: str,
    seed: int,
    max_steps: int,
) -> dict[str, Any]:
    gamefile = resolve_gamefile(data_root, task)
    if not gamefile.is_file():
        raise FileNotFoundError(gamefile)
    dataset = "eval_in_distribution" if task["split"] == "valid_seen" else "eval_out_of_distribution"
    env = builder(
        str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"),
        seed=seed,
        env_num=1,
        group_n=1,
        resources_per_worker=None,
        is_train=False,
        env_kwargs={"eval_dataset": dataset},
        gamefiles=[str(gamefile)],
    )
    transitions: list[dict[str, Any]] = []
    historical_actions: list[str] = []
    previous_snapshots: list[str] = []
    previous_skills: list[str | None] = []
    previous_edges: list[list[str] | None] = []
    success = False
    stop_reason = "max_steps"
    try:
        observations, _images, _infos = env.reset()
        for step in range(max_steps):
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            transition = build_transition(
                index,
                condition,
                observations[0],
                historical_actions,
                admissible,
                previous_snapshots,
                previous_skills,
                previous_edges,
            )
            transition["step"] = step
            transitions.append(transition)
            previous_snapshots.append(transition["observable_snapshot_fingerprint"])
            previous_skills.append(transition["selected_skill_id"])
            previous_edges.append(transition["selected_edge"])
            action = transition["terminal_action_decision"]
            historical_actions.append(action)
            observations, _images, _rewards, dones, infos = env.step([action])
            success = bool(infos[0].get("won", False))
            if bool(dones[0]):
                stop_reason = "success" if success else "environment_done"
                break
        return {
            "task_identity": task["task_identity"],
            "split": task["split"],
            "task_family": task["task_family"],
            "stratum": task["stratum"],
            "condition": condition,
            "seed": seed,
            "success": success,
            "steps": len(transitions),
            "stop_reason": stop_reason,
            "hard_invariant_violation": None,
            "gamefile": str(gamefile),
            "gamefile_sha256": sha256(gamefile),
            "metrics": _episode_metrics(transitions),
            "transitions": transitions,
        }
    finally:
        env.close()


def run_episodes(
    config: dict[str, Any], data_root: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite episode output: {output}")
    if config.get("execution_authorized") is not True or config.get("episode_execution_allowed") is not True:
        raise PermissionError("episode execution requires a fresh exact authorized runner config")
    tasks = load_schedule(config)
    index = base.load_skill_index(ROOT / str(config["skillbank"]))
    builder = base.load_alfworld_builder()
    rows: list[dict[str, Any]] = []
    hard_violation: dict[str, Any] | None = None
    for ordinal, task in enumerate(tasks):
        for condition in CONDITIONS:
            try:
                rows.append(
                    run_episode(
                        builder,
                        index,
                        data_root,
                        task,
                        condition,
                        seed=42 + ordinal,
                        max_steps=int(config["max_steps_per_episode"]),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                hard_violation = {
                    "task_identity": task.get("task_identity"),
                    "condition": condition,
                    "ordinal": ordinal,
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                rows.append(
                    {
                        "task_identity": task.get("task_identity"),
                        "condition": condition,
                        "success": False,
                        "steps": 0,
                        "stop_reason": "hard_invariant_violation",
                        "hard_invariant_violation": hard_violation,
                    }
                )
                break
        if hard_violation is not None:
            break
    result = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "artifact_type": "tracegraph_tg6_trajectory_failure_analysis_execution",
        "task_count": len(tasks),
        "planned_episode_rows": 72,
        "rows": rows,
        "episodes_started": len(rows),
        "episodes_completed": sum(row.get("hard_invariant_violation") is None for row in rows),
        "successes": sum(row.get("success") is True for row in rows),
        "hard_invariant_violation": hard_violation,
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = read_json(args.config)
    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    try:
        if args.execute:
            result = run_episodes(
                config,
                args.data_root,
                ROOT / str(config["episode_result_output"]),
            )
            print(
                f"TG6 trajectory runner: rows={result['episodes_started']}/72; "
                f"completed={result['episodes_completed']}; successes={result['successes']}; "
                "network/provider/model/API=0/0/0/0"
            )
            return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 72 else 1
        readiness = run_zero_step_readiness(
            config,
            args.data_root,
            ROOT / str(config["zero_step_readiness_output"]),
        )
        print(
            f"TG6 trajectory readiness: passed={readiness['passed_task_count']}/"
            f"{readiness['task_count']}; failed={readiness['failed_task_count']}; actions=0"
        )
        return 0 if readiness["status"] == "passed" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
