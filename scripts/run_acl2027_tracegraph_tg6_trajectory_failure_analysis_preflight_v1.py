#!/usr/bin/env python3
"""Freeze the zero-network TG6 trajectory failure-analysis development design."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_preflight_v1.json"
PLAN = ROOT / "paper/acl2027/TRACEGRAPH_TG6_TRAJECTORY_FAILURE_ANALYSIS_PLAN_V1.md"
OUTPUT_DIR = ROOT / "artifacts/acl2027_tracegraph_tg6_trajectory_failure_analysis_preflight_v1"

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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def identity(split: str, relative: str) -> str:
    return hashlib.sha256(f"{split}:{relative}".encode("utf-8")).hexdigest()


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG6-tracegraph-trajectory-failure-analysis-preflight-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_design_only",
        "development_task_count": 24,
        "planned_episode_rows": 72,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_rule": "stop on first hard invariant violation",
        "task_family": "look_at_obj_in_light",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if config.get("development_split_counts") != {"valid_seen": 12, "valid_unseen": 12}:
        errors.append("development split counts mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
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
        "execution_authorized",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    if config.get("fresh_exact_user_authorization_required") is not True:
        errors.append("fresh exact user authorization gate missing")
    if len(config.get("conditions") or []) != 3:
        errors.append("exactly three conditions are required")
    for path_key, hash_key in (
        ("parent_result", "parent_result_sha256"),
        ("heldout_schedule", "heldout_schedule_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    source_root = Path(str(config.get("source_data_root", "")))
    if not source_root.is_dir():
        errors.append("local ALFWorld source root is unavailable")
    if not PLAN.is_file():
        errors.append("trajectory failure-analysis plan is missing")
    return errors


def collect_candidates(source_root: Path, split: str, family: str) -> list[dict[str, str]]:
    base = source_root / "json_2.1.1" / split
    candidates: list[dict[str, str]] = []
    for trajectory in sorted(base.rglob("traj_data.json")):
        task_dir = trajectory.parent
        relative = task_dir.relative_to(source_root / "json_2.1.1").as_posix()
        parts = relative.split("/")
        if len(parts) < 3 or not parts[1].startswith(f"{family}-"):
            continue
        gamefile = task_dir / "game.tw-pddl"
        if not gamefile.is_file():
            continue
        candidates.append(
            {
                "task_identity": identity(split, relative),
                "split": split,
                "task_relative_path": relative,
                "gamefile_sha256": sha256(gamefile),
                "trajectory_sha256": sha256(trajectory),
            }
        )
    return candidates


def build_schedule(config: dict[str, Any], root: Path = ROOT) -> list[dict[str, str]]:
    heldout = read_json(root / str(config["heldout_schedule"]))
    heldout_ids = {str(row["task_identity"]) for row in heldout.get("tasks", [])}
    parent_result = read_json(root / str(config["parent_result"]))
    parent_ids = {str(row["task_identity"]) for row in parent_result.get("rows", [])}
    if heldout_ids != parent_ids:
        raise ValueError("parent result identities do not match frozen held-out schedule")

    source_root = Path(str(config["source_data_root"]))
    family = str(config["task_family"])
    counts = config["development_split_counts"]
    selected: list[dict[str, str]] = []
    for split in ("valid_seen", "valid_unseen"):
        fresh = [
            row
            for row in collect_candidates(source_root, split, family)
            if row["task_identity"] not in heldout_ids and row["task_identity"] not in parent_ids
        ]
        wanted = int(counts[split])
        if len(fresh) < wanted:
            raise ValueError(f"not enough fresh {split} tasks for {family}: {len(fresh)}")
        selected.extend(fresh[:wanted])
    if len(selected) != int(config["development_task_count"]):
        raise ValueError("development task count mismatch")
    if len({row["task_identity"] for row in selected}) != len(selected):
        raise ValueError("development task identities are not unique")
    return selected


def run(config: dict[str, Any], output_dir: Path = OUTPUT_DIR, root: Path = ROOT) -> dict[str, Any]:
    errors = validate_config(config, root)
    if errors:
        raise ValueError("; ".join(errors))
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule_path = root / str(config["development_schedule"])
    preflight_path = root / str(config["preflight_output"])
    if schedule_path.exists() or preflight_path.exists():
        raise FileExistsError("trajectory failure-analysis preflight artifacts already exist")

    tasks = build_schedule(config, root)
    schedule = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "selection_rule": config["selection_rule"],
        "task_family": config["task_family"],
        "tasks": tasks,
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    schedule_path.write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    schedule_hash = sha256(schedule_path)
    split_counts = {
        split: sum(row["split"] == split for row in tasks)
        for split in ("valid_seen", "valid_unseen")
    }
    preflight_payload = {
        "schema_version": 1,
        "status": "complete",
        "phase_status": "completed_zero_network_design_preflight",
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "plan": str(PLAN.relative_to(root)).replace("\\", "/"),
        "plan_sha256": sha256(PLAN),
        "config": str(CONFIG.relative_to(root)).replace("\\", "/"),
        "config_sha256": sha256(CONFIG),
        "parent_completed_phase": config["parent_completed_phase"],
        "parent_result": config["parent_result"],
        "parent_result_sha256": config["parent_result_sha256"],
        "heldout_schedule": config["heldout_schedule"],
        "heldout_schedule_sha256": config["heldout_schedule_sha256"],
        "skillbank": config["skillbank"],
        "skillbank_sha256": config["skillbank_sha256"],
        "development_schedule": str(schedule_path.relative_to(root)).replace("\\", "/"),
        "development_schedule_sha256": schedule_hash,
        "task_family": config["task_family"],
        "development_task_count": len(tasks),
        "development_split_counts": split_counts,
        "conditions": config["conditions"],
        "planned_episode_rows": config["planned_episode_rows"],
        "completed_calls": config["planned_episode_rows"],
        "rows": config["planned_episode_rows"],
        "max_steps_per_episode": config["max_steps_per_episode"],
        "max_retries": config["max_retries"],
        "stop_rule": config["stop_rule"],
        "paired_seed_rule": config["paired_seed_rule"],
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "primary_metrics": config["primary_metrics"],
        "decision_gate": config["decision_gate"],
        "identifiability_audit": config["identifiability_audit"],
        "no_overlap_audit": {
            "heldout_task_identity_overlap": 0,
            "parent_result_identity_overlap": 0,
            "skillbank_source_split": "train_only",
            "phase0_to_phase6_reuse": False,
        },
        "execution_authorized": False,
        "fresh_exact_user_authorization_required": True,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "aggregate_fingerprint": hashlib.sha256(
            json.dumps(
                {
                    "schedule_sha256": schedule_hash,
                    "conditions": config["conditions"],
                    "planned_episode_rows": config["planned_episode_rows"],
                    "decision_gate": config["decision_gate"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    preflight_path.parent.mkdir(parents=True, exist_ok=True)
    preflight_path.write_text(
        json.dumps(preflight_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return preflight_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    config = read_json(args.config)
    try:
        result = run(config, args.output_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    print(
        "VALID: froze "
        f"{result['development_task_count']} fresh development tasks and "
        f"{result['planned_episode_rows']} paired condition rows; "
        "zero-network design only; execution_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
