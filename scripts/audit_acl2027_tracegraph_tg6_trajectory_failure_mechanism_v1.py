#!/usr/bin/env python3
"""Post-hoc, zero-network mechanism audit for the completed TG6 pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as base

CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_trajectory_failure_mechanism_audit_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG6-tracegraph-trajectory-failure-mechanism-audit-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_posthoc_audit",
        "episodes_run": 0,
        "posthoc_private_metadata_allowed": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if config.get("runtime_allowed_inputs") != base.ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    for key in (
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
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    for path_key, hash_key in (
        ("parent_result", "parent_result_sha256"),
        ("parent_schedule", "parent_schedule_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path).upper() != str(config.get(hash_key, "")).upper():
            errors.append(f"{path_key} fingerprint mismatch")
    return errors


def task_goal_surface(task_relative_path: str) -> dict[str, Any]:
    stem = Path(task_relative_path).parent.name
    parts = stem.split("-")
    family = parts[0] if parts else ""
    target = parts[1].lower() if len(parts) > 1 else ""
    destination = parts[3].lower() if len(parts) > 3 else ""
    return {
        "family": family,
        "target": target.replace("_", " "),
        "destination": destination.replace("_", " "),
    }


def command_mentions(command: str, value: str) -> bool:
    value = base.normalize_text(value)
    command = base.normalize_text(command)
    return bool(value) and (value in command or value.replace(" ", "") in command.replace(" ", ""))


def goal_surface_action(command: str, goal: dict[str, Any]) -> bool:
    family = base.command_family(command)
    if goal["family"] == "look_at_obj_in_light":
        return family in {"examine", "toggle"} or command_mentions(command, goal["target"])
    if goal["family"] in {"pick_and_place_simple", "pick_two_obj_and_place"}:
        return (
            command_mentions(command, goal["target"])
            or command_mentions(command, goal["destination"])
        ) and family in {"goto", "pickup", "put", "open", "close", "toggle", "examine"}
    return False


def episode_audit(
    row: dict[str, Any],
    index: base.SkillIndex,
    matching_cache: dict[str, list[str]],
) -> dict[str, Any]:
    transitions = list(row.get("transitions") or [])
    goal = task_goal_surface(str(row.get("task_relative_path", "")))
    snapshots = [str(t["observable_snapshot_fingerprint"]) for t in transitions]
    prior_snapshots: set[str] = set()
    state_changed = 0
    novel_action_to_novel_state = 0
    novel_action_count = 0
    eligible_outside_cycle = 0
    goal_surface_available = 0
    goal_surface_selected = 0
    goal_surface_missed = 0
    skill_switch_repeated_state = 0
    edge_switch_repeated_state = 0
    exact_allowed_inputs: Counter[str] = Counter()
    for pos, transition in enumerate(transitions):
        inputs = transition["runtime_inputs"]
        exact_allowed_inputs[base.fingerprint(inputs)] += 1
        current_snapshot = snapshots[pos]
        selected = str(transition["terminal_action_decision"])
        admissible = [str(a) for a in inputs["admissible_actions"]]
        eligible = []
        for action in admissible:
            if action not in matching_cache:
                matching_cache[action] = index.matching_skill_ids(action)
            if matching_cache[action]:
                eligible.append(action)
        cycle_pair = set()
        historical = [str(a) for a in inputs["historical_actions"]]
        if len(historical) >= 4:
            a, b, c, d = historical[-4:]
            if a == c and b == d and a != b:
                cycle_pair = {a, b}
        if cycle_pair and any(a not in cycle_pair for a in eligible):
            eligible_outside_cycle += 1
        surface = [a for a in admissible if goal_surface_action(a, goal)]
        if surface:
            goal_surface_available += 1
            if goal_surface_action(selected, goal):
                goal_surface_selected += 1
            else:
                goal_surface_missed += 1
        if transition.get("action_seen_before") is False:
            novel_action_count += 1
            if pos + 1 < len(transitions) and snapshots[pos + 1] not in prior_snapshots | {current_snapshot}:
                novel_action_to_novel_state += 1
        if pos + 1 < len(transitions) and snapshots[pos + 1] != current_snapshot:
            state_changed += 1
        if pos > 0 and transition.get("skill_changed") and current_snapshot in set(snapshots[:pos]):
            skill_switch_repeated_state += 1
        if pos > 0 and transition.get("edge_changed") and current_snapshot in set(snapshots[:pos]):
            edge_switch_repeated_state += 1
        prior_snapshots.add(current_snapshot)
    return {
        "task_identity": row.get("task_identity"),
        "condition": row.get("condition"),
        "split": row.get("split"),
        "task_family": row.get("task_family"),
        "stratum": row.get("stratum"),
        "goal_surface": goal,
        "transitions": len(transitions),
        "eligible_outside_cycle_steps": eligible_outside_cycle,
        "goal_surface_available_steps": goal_surface_available,
        "goal_surface_selected_steps": goal_surface_selected,
        "goal_surface_missed_steps": goal_surface_missed,
        "state_changed_after_action_steps": state_changed,
        "nonterminal_steps": max(len(transitions) - 1, 0),
        "novel_action_steps": novel_action_count,
        "novel_action_to_novel_state_steps": novel_action_to_novel_state,
        "skill_switch_on_repeated_snapshot_steps": skill_switch_repeated_state,
        "edge_switch_on_repeated_snapshot_steps": edge_switch_repeated_state,
        "exact_allowed_input_fingerprints": dict(exact_allowed_inputs),
    }


def aggregate(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(row.get(key, "")) for key in key_fields)].append(row)
    output = []
    for key, members in sorted(groups.items()):
        def total(field: str) -> int:
            return sum(int(m[field]) for m in members)
        nonterminal = total("nonterminal_steps")
        novel = total("novel_action_steps")
        available = total("goal_surface_available_steps")
        output.append({
            **{field: value for field, value in zip(key_fields, key)},
            "episode_count": len(members),
            "two_cycle_episode_count": sum(bool(m.get("two_cycle_episode")) for m in members),
            "success_count": sum(bool(m.get("success")) for m in members),
            "eligible_outside_cycle_steps": total("eligible_outside_cycle_steps"),
            "state_changed_after_action_rate": total("state_changed_after_action_steps") / max(nonterminal, 1),
            "novel_action_to_novel_state_rate": total("novel_action_to_novel_state_steps") / max(novel, 1),
            "goal_surface_available_steps": available,
            "goal_surface_missed_rate": total("goal_surface_missed_steps") / max(available, 1),
            "skill_switch_on_repeated_snapshot_steps": total("skill_switch_on_repeated_snapshot_steps"),
            "edge_switch_on_repeated_snapshot_steps": total("edge_switch_on_repeated_snapshot_steps"),
        })
    return output


def audit(config: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors = validate_config(config, root)
    if errors:
        raise ValueError("; ".join(errors))
    parent = read_json(root / config["parent_result"])
    if parent.get("episodes_started") != 72 or parent.get("episodes_completed") != 72:
        raise ValueError("parent result is not the completed 72-episode artifact")
    schedule = read_json(root / config["parent_schedule"])
    schedule_by_id = {str(t["task_identity"]): t for t in schedule["tasks"]}
    index = base.load_skill_index(root / config["skillbank"])
    episode_rows = []
    matching_cache: dict[str, list[str]] = {}
    for row in parent["rows"]:
        task_id = str(row["task_identity"])
        if task_id not in schedule_by_id:
            raise ValueError(f"row not in frozen schedule: {task_id}")
        enriched = dict(row)
        enriched.update(schedule_by_id[task_id])
        audit_row = episode_audit(enriched, index, matching_cache)
        audit_row.update({
            "success": bool(row.get("success")),
            "two_cycle_episode": bool((row.get("metrics") or {}).get("two_cycle_episode")),
        })
        episode_rows.append(audit_row)
    collision_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in parent["rows"]:
        for transition in row.get("transitions") or []:
            fp = base.fingerprint(transition["runtime_inputs"])
            collision_groups[fp].append({
                "task_identity": row["task_identity"],
                "condition": row["condition"],
                "step": transition["step"],
                "task_family": row["task_family"],
            })
    collisions = [
        {"allowed_input_fingerprint": fp, "occurrences": occ}
        for fp, occ in sorted(collision_groups.items())
        if len({item["task_identity"] for item in occ}) > 1
    ]
    result = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "artifact_type": "tracegraph_tg6_trajectory_failure_mechanism_audit",
        "status": "completed",
        "parent_result": config["parent_result"],
        "parent_result_sha256": sha256(root / config["parent_result"]),
        "task_count": len(schedule["tasks"]),
        "episode_count": len(parent["rows"]),
        "transition_count": sum(len(row.get("transitions") or []) for row in parent["rows"]),
        "runtime_allowed_inputs": base.ALLOWED_INPUTS,
        "posthoc_private_metadata_used": True,
        "posthoc_private_metadata_boundary": "task-family/target-surface description only; no selector or gate mutation",
        "exact_allowed_input_cross_task_collision_count": len(collisions),
        "exact_allowed_input_cross_task_collisions": collisions,
        "episode_audits": episode_rows,
        "aggregates": {
            "condition": aggregate(episode_rows, ("condition",)),
            "stratum_condition": aggregate(episode_rows, ("stratum", "condition")),
            "family_condition": aggregate(episode_rows, ("task_family", "condition")),
            "split_condition": aggregate(episode_rows, ("split", "condition")),
        },
        "interpretation": {
            "input_information": "The initial observation contains the task sentence, so this audit does not claim information-theoretic impossibility.",
            "supported_claim": "The frozen selector frequently changes skills/edges or explores novel commands without converting those changes into target-surface selection or durable state novelty.",
            "gate_unchanged": True,
            "episodes_run": 0,
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "api_calls": 0,
            "paid_api_calls": 0
        }
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    config = read_json(Path(args.config))
    result = audit(config)
    output = ROOT / config["result_output"]
    manifest = ROOT / config["manifest_output"]
    if output.exists() or manifest.exists():
        raise FileExistsError("refusing to overwrite completed audit artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_payload = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "config": str(Path(args.config).relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256(Path(args.config)),
        "parent_result": config["parent_result"],
        "parent_result_sha256": sha256(ROOT / config["parent_result"]),
        "audit": config["result_output"],
        "audit_sha256": sha256(output),
        "episodes_run": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0
    }
    manifest.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "task_count": result["task_count"],
        "episode_count": result["episode_count"],
        "transition_count": result["transition_count"],
        "exact_allowed_input_cross_task_collision_count": result["exact_allowed_input_cross_task_collision_count"],
        "audit_sha256": sha256(output)
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
