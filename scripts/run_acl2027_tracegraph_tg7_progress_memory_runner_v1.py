#!/usr/bin/env python3
"""TG7 progress-memory runner with a closed readiness gate.

The selector receives only observation, historical_actions, and
admissible_actions.  Episode execution is intentionally disabled in v1; a
separately versioned authorized config must open both authorization flags.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as base

CONFIG = ROOT / "configs/acl2027/tracegraph_tg7_progress_memory_runner_v1.json"
PREFLIGHT = ROOT / "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/preflight.json"
SCHEDULE = ROOT / "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/development_schedule.json"
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = set(base.FORBIDDEN_INPUTS) | {"tg6_private_metadata"}
CONDITIONS = ("baseline_first_eligible", "task_anchor_aware", "progress_memory")
SkillIndex = base.SkillIndex
REQUIRED_TRACE_FIELDS = set(base.REQUIRED_TRACE_FIELDS) | {
    "observable_snapshot_fingerprint",
    "action_state_fingerprint",
    "cycle_triggered",
    "action_seen_before",
    "skill_changed",
    "edge_changed",
    "selector_condition",
    "selection_reason",
    "repeated_observable_snapshot",
    "task_anchor",
    "task_anchor_provenance",
    "progress_ledger",
    "progress_ledger_valid",
    "progress_ledger_provenance_complete",
}
STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "room", "task", "the", "then", "to", "up", "with",
    "your", "you",
}
TASK_MARKERS = ("your task is", "task is", "you need to")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(value).lower()).split())


def tokens(value: str) -> list[str]:
    return [token for token in normalize(value).split() if token and token not in STOPWORDS]


def extract_task_anchor(observation: str) -> list[str]:
    text = normalize(observation)
    clause = text
    for marker in TASK_MARKERS:
        if marker in text:
            clause = text.split(marker, 1)[1]
            break
    clause = clause.split(".", 1)[0]
    return sorted(set(tokens(clause)))


def action_anchor_overlap(command: str, anchor: list[str]) -> list[str]:
    command_tokens = set(tokens(command))
    return sorted(command_tokens.intersection(anchor))


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
        actions[i] == actions[i + 2]
        and actions[i + 1] == actions[i + 3]
        and actions[i] != actions[i + 1]
        for i in range(max(len(actions) - 3, 0))
    )


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG7-tracegraph-progress-memory-runner-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_runner_preflight",
        "parent_preflight": "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/preflight.json",
        "parent_preflight_sha256": "906284fa424b6edab06b289d50c91fbcabf628fe07402338c92009ca54e327d0",
        "development_schedule": "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/development_schedule.json",
        "development_schedule_sha256": "ef8287f756afc32e972a3519b3910f4ac0fb2d2a178745d508332ddd373775ab",
        "development_task_count": 24,
        "condition_count": 3,
        "planned_episode_rows": 72,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_rule": "stop on first hard invariant violation",
        "execution_authorized": False,
        "readiness_only_allowed": True,
        "episode_execution_allowed": False,
        "fresh_exact_user_authorization_required": True,
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
    for key in (
        "official_source_fallback_allowed", "network_calls_allowed",
        "provider_calls_allowed", "model_calls_allowed", "api_calls_allowed",
        "paid_api_calls_allowed", "phase0_to_phase6_reuse_allowed",
        "phase6_execution_allowed", "webshop_execution_allowed",
        "other_models_allowed", "other_datasets_allowed",
        "tuning_on_parent_heldout_allowed",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    for path_key, hash_key in (
        ("parent_preflight", "parent_preflight_sha256"),
        ("development_schedule", "development_schedule_sha256"),
        ("plan", "plan_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    if not Path(str(config.get("source_data_root", ""))).is_dir():
        errors.append("local ALFWorld source root unavailable")
    return errors


def load_schedule(config: dict[str, Any], root: Path = ROOT) -> list[dict[str, Any]]:
    schedule = read_json(root / str(config["development_schedule"]))
    tasks = list(schedule.get("tasks") or [])
    if len(tasks) != 24 or len({row.get("task_identity") for row in tasks}) != 24:
        raise ValueError("TG7 schedule must contain 24 unique tasks")
    if sum(row.get("split") == "valid_seen" for row in tasks) != 12:
        raise ValueError("TG7 valid_seen count mismatch")
    if sum(row.get("split") == "valid_unseen" for row in tasks) != 12:
        raise ValueError("TG7 valid_unseen count mismatch")
    return tasks


def _candidate_rows(
    index: base.SkillIndex, admissible: list[str]
) -> tuple[dict[str, list[str]], list[str], list[tuple[int, str, str]]]:
    command_candidates = {command: index.matching_skill_ids(command) for command in admissible}
    candidate_ids = sorted({skill_id for ids in command_candidates.values() for skill_id in ids})
    pairs = [
        (ordinal, command, skill_id)
        for ordinal, command in enumerate(admissible)
        for skill_id in command_candidates[command]
    ]
    return command_candidates, candidate_ids, pairs


def _baseline_choice(
    command_candidates: dict[str, list[str]], admissible: list[str]
) -> tuple[str | None, str | None]:
    for command in admissible:
        if command_candidates[command]:
            return command, command_candidates[command][0]
    return None, None


def _anchor_choice(
    pairs: list[tuple[int, str, str]],
    anchor: list[str],
    command_candidates: dict[str, list[str]],
    admissible: list[str],
) -> tuple[str | None, str | None, str]:
    if not pairs:
        for command in admissible:
            if action_anchor_overlap(command, anchor):
                return command, None, "anchor_fallback_without_skill"
        return None, None, "fallback_no_eligible_skill"
    ranked = sorted(
        pairs,
        key=lambda row: (-len(action_anchor_overlap(row[1], anchor)), row[0], row[2]),
    )
    _, command, skill_id = ranked[0]
    return command, skill_id, "anchor_overlap_rank"


def _progress_choice(
    pairs: list[tuple[int, str, str]],
    anchor: list[str],
    ledger: dict[str, Any],
    historical: list[str],
    cycle_pair: tuple[str, str] | None,
    previous_skill: str | None,
    command_candidates: dict[str, list[str]],
    admissible: list[str],
) -> tuple[str | None, str | None, str]:
    if not pairs:
        command, _, reason = _anchor_choice(pairs, anchor, command_candidates, admissible)
        return command, None, reason
    unresolved = set(ledger.get("unresolved_anchor_tokens") or [])
    seen = set(historical)
    cycle = set(cycle_pair or ())
    ranked = sorted(
        pairs,
        key=lambda row: (
            -len(set(action_anchor_overlap(row[1], sorted(unresolved)))),
            row[1] in seen,
            row[2] == previous_skill,
            row[1] in cycle,
            row[0],
            row[2],
        ),
    )
    _, command, skill_id = ranked[0]
    return command, skill_id, "progress_ledger_rank"


def update_ledger(
    previous: dict[str, Any] | None,
    observation: str,
    historical: list[str],
    admissible: list[str],
    action: str,
    anchor: list[str],
    snapshot: str,
) -> dict[str, Any]:
    prior = dict(previous or {})
    observed = set(prior.get("observed_anchor_tokens") or [])
    attempted = set(prior.get("attempted_anchor_tokens") or [])
    observed.update(action_anchor_overlap(observation, anchor))
    attempted.update(action_anchor_overlap(action, anchor))
    snapshots = list(prior.get("observable_snapshot_fingerprints") or [])
    snapshots.append(snapshot)
    return {
        "anchor_tokens": list(anchor),
        "observed_anchor_tokens": sorted(observed),
        "attempted_anchor_tokens": sorted(attempted),
        "unresolved_anchor_tokens": sorted(set(anchor) - attempted),
        "attempted_actions": list(historical) + [action],
        "observable_snapshot_fingerprints": snapshots,
        "state_change_count": sum(a != b for a, b in zip(snapshots, snapshots[1:])),
        "last_admissible_action_count": len(admissible),
        "provenance": {
            "anchor_tokens": "initial runtime_inputs.observation",
            "observed_anchor_tokens": "runtime_inputs.observation",
            "attempted_anchor_tokens": "runtime_inputs.historical_actions + selected terminal_action_decision",
            "unresolved_anchor_tokens": "derived from anchor_tokens and attempted_anchor_tokens",
            "attempted_actions": "runtime_inputs.historical_actions + selected terminal_action_decision",
            "observable_snapshot_fingerprints": "runtime_inputs.observation + runtime_inputs.admissible_actions",
            "last_admissible_action_count": "runtime_inputs.admissible_actions",
        },
    }


def select_condition(
    index: base.SkillIndex,
    condition: str,
    runtime_inputs: dict[str, Any],
    anchor: list[str],
    ledger: dict[str, Any] | None,
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
    command_candidates, candidate_ids, pairs = _candidate_rows(index, admissible)
    cycle_triggered, cycle_pair = detect_two_cycle(historical)
    selected_command, selected_skill = _baseline_choice(command_candidates, admissible)
    reason = "first_eligible"
    if condition == "task_anchor_aware":
        selected_command, selected_skill, reason = _anchor_choice(
            pairs, anchor, command_candidates, admissible
        )
    elif condition == "progress_memory":
        selected_command, selected_skill, reason = _progress_choice(
            pairs,
            anchor,
            ledger or {},
            historical,
            cycle_pair if cycle_triggered else None,
            previous_skills[-1] if previous_skills else None,
            command_candidates,
            admissible,
        )
    non_help = [command for command in admissible if base.normalize_text(command) != "help"]
    terminal = selected_command or (non_help[0] if non_help else admissible[0])
    if selected_command is None and reason == "first_eligible":
        reason = "fallback_no_eligible_skill"
    rejections = [
        {"action": command, "reason": "no eligible train-derived canonical action"}
        for command, skill_ids in command_candidates.items() if not skill_ids
    ]
    permitted_edges = (
        [[selected_skill, candidate] for candidate in candidate_ids if candidate != selected_skill]
        if selected_skill is not None else []
    )
    selected_edge = permitted_edges[0] if permitted_edges else None
    snapshot = snapshot_fingerprint(str(runtime_inputs["observation"]), admissible)
    next_ledger = update_ledger(
        ledger, str(runtime_inputs["observation"]), historical, admissible, terminal, anchor, snapshot
    )
    transition = {
        "runtime_inputs": runtime_inputs,
        "observable_state_fingerprint": base.fingerprint(runtime_inputs),
        "candidate_skill_ids": candidate_ids,
        "eligibility_rejections": rejections,
        "permitted_edges": permitted_edges,
        "selected_skill_id": selected_skill,
        "selected_edge": selected_edge,
        "terminal_action_decision": terminal,
        "abstained": selected_skill is None,
        "observable_snapshot_fingerprint": snapshot,
        "action_state_fingerprint": action_state_fingerprint(snapshot, terminal),
        "cycle_triggered": cycle_triggered,
        "action_seen_before": terminal in set(historical),
        "skill_changed": bool(previous_skills) and selected_skill != previous_skills[-1],
        "edge_changed": bool(previous_edges) and selected_edge != previous_edges[-1],
        "selector_condition": condition,
        "selection_reason": reason,
        "repeated_observable_snapshot": snapshot in set(previous_snapshots),
        "task_anchor": list(anchor),
        "task_anchor_provenance": "initial runtime_inputs.observation",
        "progress_ledger": next_ledger,
        "progress_ledger_valid": True,
        "progress_ledger_provenance_complete": True,
    }
    valid, message = base.validate_transition(transition)
    if not valid:
        raise RuntimeError(message)
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        raise RuntimeError("TG7 trace incomplete")
    return transition


def run_zero_step_readiness(
    config: dict[str, Any], data_root: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite readiness output: {output}")
    tasks = load_schedule(config)
    rows: list[dict[str, Any]] = []
    try:
        builder = base.load_alfworld_builder()
    except Exception as exc:  # noqa: BLE001
        result = {
            "schema_version": 1,
            "phase_id": config["phase_id"],
            "artifact_type": "tracegraph_tg7_progress_memory_zero_step_readiness",
            "status": "blocked_environment_readiness",
            "task_count": len(tasks),
            "passed_task_count": 0,
            "failed_task_count": len(tasks),
            "episodes_run": 0,
            "actions_taken": 0,
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "api_calls": 0,
            "paid_api_calls": 0,
            "runtime_allowed_inputs": ALLOWED_INPUTS,
            "global_error": {
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            "rows": [
                {
                    "task_identity": task["task_identity"],
                    "split": task["split"],
                    "task_family": task["task_family"],
                    "status": "not_attempted_dependency_block",
                    "actions_taken": 0,
                }
                for task in tasks
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    for ordinal, task in enumerate(tasks):
        gamefile = base.resolve_gamefile(data_root, task)
        row: dict[str, Any] = {
            "task_identity": task["task_identity"],
            "split": task["split"],
            "task_family": task["task_family"],
            "task_relative_path": task["task_relative_path"],
            "gamefile": str(gamefile),
            "gamefile_sha256": sha256(gamefile) if gamefile.is_file() else None,
            "seed": 4200 + ordinal,
            "actions_taken": 0,
        }
        if not gamefile.is_file():
            row.update({"status": "failed", "error_type": "FileNotFoundError", "error": str(gamefile)})
            rows.append(row)
            continue
        dataset = "eval_in_distribution" if task["split"] == "valid_seen" else "eval_out_of_distribution"
        env = builder(
            str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"),
            seed=4200 + ordinal,
            env_num=1,
            group_n=1,
            resources_per_worker=None,
            is_train=False,
            env_kwargs={"eval_dataset": dataset},
            gamefiles=[str(gamefile)],
        )
        try:
            observations, _images, infos = env.reset()
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            anchor = extract_task_anchor(str(observations[0]))
            row.update({
                "status": "passed",
                "observation_present": bool(observations and observations[0]),
                "admissible_action_count": len(admissible),
                "anchor_token_count": len(anchor),
                "info_present": bool(infos and isinstance(infos[0], dict)),
            })
        except Exception as exc:  # noqa: BLE001
            row.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        finally:
            env.close()
        rows.append(row)
    passed = sum(row["status"] == "passed" for row in rows)
    result = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "artifact_type": "tracegraph_tg7_progress_memory_zero_step_readiness",
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
    return {
        "transition_count": len(transitions),
        "two_cycle_episode": has_two_cycle(actions),
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
        "progress_ledger_valid": all(row["progress_ledger_valid"] for row in transitions),
        "progress_ledger_provenance_complete": all(
            row["progress_ledger_provenance_complete"] for row in transitions
        ),
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
    gamefile = base.resolve_gamefile(data_root, task)
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
    historical: list[str] = []
    snapshots: list[str] = []
    skills: list[str | None] = []
    edges: list[list[str] | None] = []
    ledger: dict[str, Any] | None = None
    success = False
    stop_reason = "max_steps"
    try:
        observations, _images, _infos = env.reset()
        anchor = extract_task_anchor(str(observations[0]))
        for step in range(max_steps):
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            runtime_inputs = {
                "observation": str(observations[0]),
                "historical_actions": list(historical),
                "admissible_actions": list(admissible),
            }
            transition = select_condition(
                index, condition, runtime_inputs, anchor, ledger, snapshots, skills, edges
            )
            transition["step"] = step
            transitions.append(transition)
            snapshots.append(transition["observable_snapshot_fingerprint"])
            skills.append(transition["selected_skill_id"])
            edges.append(transition["selected_edge"])
            ledger = transition["progress_ledger"]
            action = transition["terminal_action_decision"]
            historical.append(action)
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


def run_episodes(config: dict[str, Any], data_root: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite episode output: {output}")
    if config.get("execution_authorized") is not True or config.get("episode_execution_allowed") is not True:
        raise PermissionError("TG7 episode execution requires a fresh exact authorized runner config")
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
                        builder, index, data_root, task, condition,
                        seed=4200 + ordinal, max_steps=int(config["max_steps_per_episode"]),
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
                rows.append({
                    "task_identity": task.get("task_identity"),
                    "condition": condition,
                    "success": False,
                    "steps": 0,
                    "stop_reason": "hard_invariant_violation",
                    "hard_invariant_violation": hard_violation,
                })
                break
        if hard_violation is not None:
            break
    result = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "artifact_type": "tracegraph_tg7_progress_memory_execution",
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
    if args.execute:
        try:
            result = run_episodes(
                config, args.data_root, ROOT / str(config["episode_result_output"])
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(
            f"TG7 progress-memory runner: rows={result['episodes_started']}/72; "
            f"completed={result['episodes_completed']}; successes={result['successes']}; "
            "network/provider/model/API=0/0/0/0"
        )
        return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 72 else 1
    try:
        result = run_zero_step_readiness(
            config, args.data_root, ROOT / str(config["zero_step_readiness_output"])
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"TG7 progress-memory readiness: passed={result['passed_task_count']}/"
        f"{result['task_count']}; failed={result['failed_task_count']}; actions=0"
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
