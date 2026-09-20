#!/usr/bin/env python3
"""Run the authorized, local-only TraceGraph TG6 ALFWorld episodes.

This module deliberately avoids importing any project model/provider module.
The policy sees only observation, historical_actions, and admissible_actions.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs" / "acl2027" / "tracegraph_tg6_local_execution_runner_v1.json"
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
REQUIRED_TRACE_FIELDS = {
    "observable_state_fingerprint",
    "candidate_skill_ids",
    "eligibility_rejections",
    "permitted_edges",
    "selected_skill_id",
    "selected_edge",
    "terminal_action_decision",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if config.get("experiment_line") != "tracegraph-observable-state-skill-composition":
        errors.append("wrong TraceGraph research line")
    if config.get("episode_count") != 40 or config.get("max_retries") != 0:
        errors.append("exact TG6 episode scope mismatch")
    if config.get("stop_rule") != "stop on first hard invariant violation":
        errors.append("stop rule mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
    for key in (
        "network_calls_allowed",
        "provider_calls_allowed",
        "model_calls_allowed",
        "paid_api_calls_allowed",
        "authorization_receipts_allowed",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    if config.get("execution_authorized") is not True:
        errors.append("local execution authorization is not bound")
    if config.get("webshop_status") != "blocked_pending_preregistered_alfworld_mechanism_gate":
        errors.append("WebShop gate relaxed")
    for path_key, hash_key in (
        ("parent_scope_config", "parent_scope_config_sha256"),
        ("heldout_schedule", "heldout_schedule_sha256"),
        ("readiness_artifact", "readiness_artifact_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif file_sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    return errors


def normalize_text(value: str) -> str:
    text = str(value or "").lower().replace("_", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def action_family(action_name: str) -> str:
    key = normalize_text(action_name).replace(" ", "")
    return {
        "gotolocation": "goto",
        "pickupobject": "pickup",
        "putobject": "put",
        "openobject": "open",
        "closeobject": "close",
        "toggleobject": "toggle",
        "cleanobject": "clean",
        "heatobject": "heat",
        "coolobject": "cool",
        "sliceobject": "slice",
        "examineobject": "examine",
        "lookatobject": "examine",
        "noop": "noop",
    }.get(key, key)


def command_family(command: str) -> str:
    text = normalize_text(command)
    if text in {"look", "wait", "none"}:
        return "noop"
    patterns = (
        ("goto", r"^(go to|move to|walk to|navigate to)\b"),
        ("pickup", r"^(take|pick up|pickup)\b"),
        ("put", r"^(put|place)\b"),
        ("open", r"^open\b"),
        ("close", r"^close\b"),
        ("toggle", r"^(turn on|turn off|switch on|switch off)\b"),
        ("clean", r"^clean\b"),
        ("heat", r"^heat\b"),
        ("cool", r"^cool\b"),
        ("slice", r"^slice\b"),
        ("examine", r"^(examine|look at)\b"),
    )
    for family, pattern in patterns:
        if re.search(pattern, text):
            return family
    return ""


def action_signature(action: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return (
        action_family(str(action.get("action", ""))),
        tuple(normalize_text(str(arg)) for arg in (action.get("args") or []) if normalize_text(str(arg))),
    )


def action_matches_command(action: dict[str, Any], command: str) -> bool:
    family, arguments = action_signature(action)
    if not family or family != command_family(command):
        return False
    text = normalize_text(command)
    compact = text.replace(" ", "")
    return all(argument in text or argument.replace(" ", "") in compact for argument in arguments)


class SkillIndex:
    """A deterministic representative index over the frozen train-only SkillBank."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._by_signature: dict[tuple[str, tuple[str, ...]], str] = {}
        self._actions: dict[str, dict[str, Any]] = {}
        for record in records:
            if record.get("source_split") != "train":
                raise ValueError("SkillBank contains a non-train source record")
            skill_id = str(record.get("skill_id", "")).strip()
            actions = record.get("canonical_actions") or []
            if not skill_id or not actions:
                raise ValueError("SkillBank record is missing skill_id or canonical_actions")
            action = dict(actions[0])
            signature = action_signature(action)
            if not signature[0]:
                continue
            previous = self._by_signature.get(signature)
            if previous is None or skill_id < previous:
                self._by_signature[signature] = skill_id
                self._actions[skill_id] = action

    def matching_skill_ids(self, command: str) -> list[str]:
        matches = [
            skill_id
            for skill_id, action in self._actions.items()
            if action_matches_command(action, command)
        ]
        return sorted(matches)


def load_skill_index(path: Path) -> SkillIndex:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("SkillBank is empty")
    return SkillIndex(records)


def select_from_observable(index: SkillIndex, runtime_inputs: dict[str, Any]) -> dict[str, Any]:
    if list(runtime_inputs) != ALLOWED_INPUTS:
        raise ValueError("runtime inputs must contain exactly the three observable fields")
    admissible = [str(item) for item in runtime_inputs["admissible_actions"] if str(item).strip()]
    if not admissible:
        raise ValueError("environment returned no admissible action")

    command_candidates: dict[str, list[str]] = {
        command: index.matching_skill_ids(command) for command in admissible
    }
    candidate_ids = sorted({skill_id for ids in command_candidates.values() for skill_id in ids})
    selected_skill_id: str | None = None
    selected_command: str | None = None
    for command in admissible:
        if command_candidates[command]:
            selected_skill_id = command_candidates[command][0]
            selected_command = command
            break
    non_help = [command for command in admissible if normalize_text(command) != "help"]
    terminal = selected_command or (non_help[0] if non_help else admissible[0])

    rejections = [
        {"action": command, "reason": "no eligible train-derived canonical action"}
        for command, skill_ids in command_candidates.items()
        if not skill_ids
    ]
    permitted_edges: list[list[str]] = []
    if selected_skill_id is not None:
        for candidate_id in candidate_ids:
            if candidate_id != selected_skill_id:
                permitted_edges.append([selected_skill_id, candidate_id])
    selected_edge = permitted_edges[0] if permitted_edges else None
    return {
        "candidate_skill_ids": candidate_ids,
        "eligibility_rejections": rejections,
        "permitted_edges": permitted_edges,
        "selected_skill_id": selected_skill_id,
        "selected_edge": selected_edge,
        "terminal_action_decision": terminal,
        "abstained": selected_skill_id is None,
    }


def validate_transition(transition: dict[str, Any]) -> tuple[bool, str]:
    runtime = transition.get("runtime_inputs")
    if not isinstance(runtime, dict) or list(runtime) != ALLOWED_INPUTS:
        return False, "runtime input violation"
    if any(key in transition for key in FORBIDDEN_INPUTS):
        return False, "forbidden runtime field present"
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        return False, "trace incomplete"
    admissible = list(runtime.get("admissible_actions") or [])
    terminal = transition.get("terminal_action_decision")
    if terminal not in admissible:
        return False, "terminal action inadmissible"
    candidates = set(transition.get("candidate_skill_ids") or [])
    selected = transition.get("selected_skill_id")
    if selected is not None and selected not in candidates:
        return False, "selected skill missing"
    if (selected is None) != bool(transition.get("abstained")):
        return False, "abstention flag inconsistent"
    edges = [list(edge) for edge in transition.get("permitted_edges") or []]
    if any(len(edge) != 2 or edge[0] not in candidates or edge[1] not in candidates for edge in edges):
        return False, "permitted edge endpoint violation"
    selected_edge = transition.get("selected_edge")
    if selected_edge is not None and list(selected_edge) not in edges:
        return False, "selected edge is not permitted"
    if transition.get("observable_state_fingerprint") != fingerprint(runtime):
        return False, "observable-state fingerprint mismatch"
    return True, "ok"


def build_transition(
    index: SkillIndex,
    observation: str,
    historical_actions: list[str],
    admissible_actions: list[str],
) -> dict[str, Any]:
    runtime_inputs = {
        "observation": str(observation),
        "historical_actions": [str(item) for item in historical_actions],
        "admissible_actions": [str(item) for item in admissible_actions],
    }
    transition = {
        "runtime_inputs": runtime_inputs,
        "observable_state_fingerprint": fingerprint(runtime_inputs),
        **select_from_observable(index, runtime_inputs),
    }
    valid, message = validate_transition(transition)
    if not valid:
        raise RuntimeError(message)
    return transition


def load_alfworld_builder():
    module_path = ROOT / "skillopt" / "envs" / "alfworld" / "vendor" / "alfworld_envs.py"
    spec = importlib.util.spec_from_file_location("tracegraph_alfworld_envs", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load ALFWorld environment module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_alfworld_envs


def resolve_gamefile(data_root: Path, task: dict[str, Any]) -> Path:
    relative = Path(str(task["task_relative_path"]))
    split = str(task["split"])
    if not relative.parts or relative.parts[0] != split:
        relative = Path(split) / relative
    return data_root / "json_2.1.1" / relative / "game.tw-pddl"


def aggregate_trace(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    if not transitions:
        raise ValueError("episode produced no transitions")
    return {
        "transition_count": len(transitions),
        "transition_fingerprints": [row["observable_state_fingerprint"] for row in transitions],
        "candidate_skill_ids": sorted(
            {skill_id for row in transitions for skill_id in row["candidate_skill_ids"]}
        ),
        "selected_skill_ids": [row["selected_skill_id"] for row in transitions],
        "selected_edges": [row["selected_edge"] for row in transitions],
        "terminal_action_decisions": [row["terminal_action_decision"] for row in transitions],
        "abstention_count": sum(bool(row["abstained"]) for row in transitions),
    }


def run_episode(
    build_env: Any,
    index: SkillIndex,
    data_root: Path,
    task: dict[str, Any],
    seed: int,
    max_steps: int,
) -> dict[str, Any]:
    split = str(task["split"])
    eval_dataset = "eval_in_distribution" if split == "valid_seen" else "eval_out_of_distribution"
    gamefile = resolve_gamefile(data_root, task)
    if not gamefile.is_file():
        raise RuntimeError(f"missing held-out game file: {gamefile}")

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
            "success": success,
            "steps": len(transitions),
            "stop_reason": stop_reason,
            "hard_invariant_violation": None,
            "trace": aggregate_trace(transitions),
            "transitions": transitions,
        }
    finally:
        env.close()


def run(config: dict[str, Any], output: Path, data_root: Path) -> dict[str, Any]:
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing TG6 output: {output}")
    schedule = read_json(ROOT / config["heldout_schedule"])
    readiness = read_json(ROOT / config["readiness_artifact"])
    tasks = list(schedule.get("tasks") or [])
    if len(tasks) != 40 or not readiness.get("ready_for_frozen_40_task_execution"):
        raise ValueError("frozen 40-task readiness gate is not satisfied")
    index = load_skill_index(ROOT / config["skillbank"])
    build_env = load_alfworld_builder()

    rows: list[dict[str, Any]] = []
    hard_violation: dict[str, Any] | None = None
    for ordinal, task in enumerate(tasks):
        try:
            rows.append(
                run_episode(
                    build_env,
                    index,
                    data_root,
                    task,
                    seed=42 + ordinal,
                    max_steps=int(config["max_steps_per_episode"]),
                )
            )
        except Exception as exc:  # noqa: BLE001
            hard_violation = {
                "task_identity": task.get("task_identity"),
                "ordinal": ordinal,
                "type": type(exc).__name__,
                "message": str(exc),
            }
            rows.append(
                {
                    "task_identity": task.get("task_identity"),
                    "split": task.get("split"),
                    "task_relative_path": task.get("task_relative_path"),
                    "success": False,
                    "steps": 0,
                    "stop_reason": "hard_invariant_violation",
                    "hard_invariant_violation": hard_violation,
                }
            )
            break

    result = {
        "experiment_line": config["experiment_line"],
        "phase_id": config["phase_id"],
        "config_sha256": file_sha256(CONFIG),
        "task_count": len(tasks),
        "episodes_started": len(rows),
        "episodes_completed": sum(row.get("hard_invariant_violation") is None for row in rows),
        "successes": sum(row.get("success") is True for row in rows),
        "hard_invariant_violation": hard_violation,
        "stop_rule": config["stop_rule"],
        "max_retries": config["max_retries"],
        "runtime_allowed_inputs": config["runtime_allowed_inputs"],
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()
    config = read_json(args.config)
    data_root = args.data_root or Path(os.environ.get("ALFWORLD_DATA", "").strip())
    if not data_root:
        print("ERROR: set ALFWORLD_DATA or pass --data-root", file=sys.stderr)
        return 2
    try:
        result = run(config, args.output, data_root)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"TG6 local runner: started {result['episodes_started']}/{result['task_count']} episodes; "
        f"completed={result['episodes_completed']}; successes={result['successes']}; "
        "network/provider/model/API=0/0/0/0"
    )
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
