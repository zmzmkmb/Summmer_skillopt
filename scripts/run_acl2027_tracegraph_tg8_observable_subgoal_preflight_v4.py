#!/usr/bin/env python3
"""Freeze TG8 v4 with global template uniqueness and balanced row order."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_preflight_v3 import (  # noqa: E402
    collect_candidates,
    rank_value,
    read_json,
    sha256,
)

CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_preflight_v4.json"
SCHEDULE_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v4/development_schedule.json"
PREFLIGHT_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v4/preflight.json"
MANIFEST_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v4/completion_manifest.json"
FAMILIES = (
    "pick_and_place_simple",
    "pick_two_obj_and_place",
    "pick_clean_then_place_in_recep",
)
CONDITIONS = (
    "lexical_greedy",
    "lexical_anti_cycle",
    "observable_subgoal_greedy",
    "observable_subgoal_anti_cycle",
)
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = {
    "task_description", "raw_trajectory", "planner_state", "pddl_params",
    "scene_state", "expert_future_actions", "evaluation_label",
    "phase0_to_phase6_artifact", "tg6_private_metadata", "tg7_private_metadata",
    "tg8_private_metadata",
}


def validate_zero_execution_manifest(item: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    path = root / str(item.get("path", ""))
    if not path.is_file() or sha256(path) != item.get("sha256"):
        return ["superseded design fingerprint mismatch"]
    data = read_json(path)
    for key in (
        "episodes_run", "actions_taken", "network_calls", "provider_calls",
        "model_calls", "api_calls", "paid_api_calls",
    ):
        if data.get(key) != 0:
            errors.append(f"superseded design {key} must be zero")
    if data.get("execution_authorized") is not False:
        errors.append("superseded design execution authorization must be closed")
    if any(candidate.name.startswith("result") and candidate.suffix == ".json" for candidate in path.parent.iterdir()):
        errors.append("superseded design directory contains result data")
    return errors


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG8-tracegraph-observable-subgoal-preflight-v4",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_design_only",
        "task_family": "tg8_observable_subgoal_factorial_pilot_v4",
        "family_split_quota": 5,
        "development_task_count": 30,
        "replicate_count": 3,
        "planned_episode_rows": 360,
        "max_steps_per_episode": 75,
        "primary_step_landmark": 50,
        "sensitivity_step_landmark": 75,
        "max_retries": 0,
        "execution_authorized": False,
        "fresh_exact_user_authorization_required": True,
        "readiness_only_allowed_after_selector_tests": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if tuple(config.get("families") or []) != FAMILIES:
        errors.append("family order mismatch")
    if config.get("split_counts") != {"valid_seen": 15, "valid_unseen": 15}:
        errors.append("split counts mismatch")
    if tuple(item.get("id") for item in config.get("conditions") or []) != CONDITIONS:
        errors.append("condition order mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
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
        ("parent_design_preflight", "parent_design_preflight_sha256"),
        ("parent_design_review", "parent_design_review_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    for item in config.get("generator_dependencies") or []:
        path = root / str(item.get("path", ""))
        if not path.is_file() or sha256(path) != item.get("sha256"):
            errors.append("generator dependency fingerprint mismatch")
    for item in config.get("superseded_unexecuted_designs") or []:
        errors.extend(validate_zero_execution_manifest(item, root))
    if not (root / str(config.get("plan", ""))).is_file():
        errors.append("missing plan")
    if not Path(str(config.get("source_data_root", ""))).is_dir():
        errors.append("local ALFWorld source root unavailable")
    for relative in config.get("executed_identity_exclusion_sources") or []:
        if not (root / str(relative)).is_file():
            errors.append(f"missing executed exclusion source: {relative}")
    return errors


def load_excluded_ids(config: dict[str, Any], root: Path = ROOT) -> tuple[set[str], list[dict[str, Any]]]:
    excluded: set[str] = set()
    manifest: list[dict[str, Any]] = []
    for relative in config["executed_identity_exclusion_sources"]:
        path = root / str(relative)
        data = read_json(path)
        rows = list(data.get("tasks") or data.get("rows") or [])
        ids = {str(row["task_identity"]) for row in rows if isinstance(row, dict) and row.get("task_identity")}
        excluded.update(ids)
        manifest.append({"path": str(relative).replace("\\", "/"), "sha256": sha256(path), "task_identity_count": len(ids)})
    return excluded, manifest


def choose_global_unique_templates(
    candidates_by_cell: dict[tuple[str, str], list[dict[str, str]]], quota: int
) -> list[dict[str, Any]]:
    used_templates: set[str] = set()
    selected: list[dict[str, Any]] = []
    cell_order = sorted(
        candidates_by_cell,
        key=lambda cell: (
            len({row["template_key"] for row in candidates_by_cell[cell]}),
            rank_value("tg8-v4-cell", "/".join(cell)),
        ),
    )
    for split, family in cell_order:
        by_template: dict[str, list[dict[str, str]]] = {}
        for row in candidates_by_cell[(split, family)]:
            by_template.setdefault(row["template_key"], []).append(row)
        available = [key for key in by_template if key not in used_templates]
        available.sort(key=lambda key: rank_value(f"tg8-v4-template:{split}:{family}", key))
        if len(available) < quota:
            raise ValueError(f"not enough globally unique templates: {split}/{family}")
        for key in available[:quota]:
            chosen = min(by_template[key], key=lambda row: rank_value("tg8-v4-task", row["task_identity"]))
            chosen["stratum"] = "tg8_v4_global_unique_template_pilot"
            selected.append(chosen)
            used_templates.add(key)
    return selected


def build_balanced_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks = [
        (ordinal, task, replicate)
        for ordinal, task in enumerate(tasks)
        for replicate in range(3)
    ]
    ranked_blocks = sorted(
        blocks,
        key=lambda block: rank_value(
            "tg8-v4-block", f"{block[1]['task_identity']}:{block[2]}"
        ),
    )
    rotations = {
        (task["task_identity"], replicate): rank % 4
        for rank, (_ordinal, task, replicate) in enumerate(ranked_blocks)
    }
    rows: list[dict[str, Any]] = []
    for ordinal, task in enumerate(tasks):
        for replicate in range(3):
            seed = 5200 + 100 * replicate + ordinal
            rotation = rotations[(task["task_identity"], replicate)]
            order = list(CONDITIONS[rotation:] + CONDITIONS[:rotation])
            for position, condition in enumerate(order):
                run_id = hashlib.sha256(
                    f"tg8-v4:{task['task_identity']}:{replicate}:{condition}".encode("utf-8")
                ).hexdigest()
                rows.append({
                    "run_id": run_id,
                    "task_identity": task["task_identity"],
                    "task_ordinal": ordinal,
                    "split": task["split"],
                    "task_family": task["task_family"],
                    "template_key": task["template_key"],
                    "replicate_index": replicate,
                    "seed": seed,
                    "condition": condition,
                    "condition_position": position,
                    "latin_rotation": rotation,
                    "max_steps": 75,
                    "primary_step_landmark": 50,
                })
    return rows


def build_schedule(
    config: dict[str, Any], root: Path = ROOT
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    excluded, exclusion_manifest = load_excluded_ids(config, root)
    source_root = Path(str(config["source_data_root"]))
    candidates_by_cell = {
        (split, family): [
            row
            for row in collect_candidates(source_root, split, family)
            if row["task_identity"] not in excluded
        ]
        for split in ("valid_seen", "valid_unseen")
        for family in FAMILIES
    }
    tasks = choose_global_unique_templates(candidates_by_cell, 5)
    tasks.sort(key=lambda row: (row["split"], row["task_family"], rank_value("tg8-v4-final", row["task_identity"])))
    if len(tasks) != 30 or len({row["task_identity"] for row in tasks}) != 30:
        raise ValueError("TG8 v4 task count mismatch")
    if len({row["template_key"] for row in tasks}) != 30:
        raise ValueError("TG8 v4 templates are not globally unique")
    for split in ("valid_seen", "valid_unseen"):
        for family in FAMILIES:
            cell = [row for row in tasks if row["split"] == split and row["task_family"] == family]
            if len(cell) != 5:
                raise ValueError(f"cell count mismatch: {split}/{family}")
    rows = build_balanced_rows(tasks)
    if len(rows) != 360 or len({row["run_id"] for row in rows}) != 360:
        raise ValueError("TG8 v4 row count mismatch")
    position_counts = Counter((row["condition"], row["condition_position"]) for row in rows)
    if set(position_counts.values()) - {22, 23}:
        raise ValueError("condition positions are not balanced")
    return tasks, rows, exclusion_manifest


def run(config: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors = validate_config(config, root)
    if errors:
        raise ValueError("; ".join(errors))
    paths = [root / SCHEDULE_REL, root / PREFLIGHT_REL, root / MANIFEST_REL]
    if any(path.exists() for path in paths):
        raise FileExistsError("TG8 v4 preflight artifacts already exist")
    tasks, rows, exclusion_manifest = build_schedule(config, root)
    schedule_path = root / SCHEDULE_REL
    schedule = {
        "schema_version": 4,
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "selection_rule": "five globally unique stable-hash-ranked templates per family and split; one stable-hash-ranked identity per template",
        "condition_order_rule": config["condition_order_rule"],
        "task_family": config["task_family"],
        "families": list(FAMILIES),
        "conditions": config["conditions"],
        "tasks": tasks,
        "rows": rows,
        "development_task_count": 30,
        "replicate_count": 3,
        "planned_episode_rows": 360,
        "max_steps_per_episode": 75,
        "primary_step_landmark": 50,
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    schedule_path.write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config_hash = sha256(CONFIG)
    plan_path = root / str(config["plan"])
    plan_hash = sha256(plan_path)
    schedule_hash = sha256(schedule_path)
    position_counts = Counter((row["condition"], row["condition_position"]) for row in rows)
    preflight = {
        "schema_version": 4,
        "status": "complete",
        "phase_status": "completed_zero_network_design_preflight",
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "config": str(CONFIG.relative_to(root)).replace("\\", "/"),
        "config_sha256": config_hash,
        "plan": str(plan_path.relative_to(root)).replace("\\", "/"),
        "plan_sha256": plan_hash,
        "parent_design_preflight": config["parent_design_preflight"],
        "parent_design_preflight_sha256": config["parent_design_preflight_sha256"],
        "parent_design_review": config["parent_design_review"],
        "parent_design_review_sha256": config["parent_design_review_sha256"],
        "generator_dependencies": config["generator_dependencies"],
        "superseded_unexecuted_designs": config["superseded_unexecuted_designs"],
        "executed_identity_exclusion_sources": exclusion_manifest,
        "skillbank": config["skillbank"],
        "skillbank_sha256": config["skillbank_sha256"],
        "development_schedule": SCHEDULE_REL,
        "development_schedule_sha256": schedule_hash,
        "development_task_count": 30,
        "globally_unique_template_count": 30,
        "replicate_count": 3,
        "planned_episode_rows": 360,
        "materialized_row_count": len(rows),
        "split_counts": {split: sum(row["split"] == split for row in tasks) for split in ("valid_seen", "valid_unseen")},
        "family_counts": {family: sum(row["task_family"] == family for row in tasks) for family in FAMILIES},
        "template_counts": {f"{split}/{family}": len({row["template_key"] for row in tasks if row["split"] == split and row["task_family"] == family}) for split in ("valid_seen", "valid_unseen") for family in FAMILIES},
        "condition_position_counts": {f"{condition}@{position}": position_counts[(condition, position)] for condition in CONDITIONS for position in range(4)},
        "conditions": config["conditions"],
        "max_steps_per_episode": 75,
        "primary_step_landmark": 50,
        "sensitivity_step_landmark": 75,
        "max_retries": 0,
        "stop_rule": config["stop_rule"],
        "paired_seed_rule": config["paired_seed_rule"],
        "condition_order_rule": config["condition_order_rule"],
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "runtime_forbidden_inputs": config["runtime_forbidden_inputs"],
        "selector_contract": config["selector_contract"],
        "estimands": config["estimands"],
        "primary_metrics": config["primary_metrics"],
        "secondary_metrics": config["secondary_metrics"],
        "decision_gate": config["decision_gate"],
        "no_overlap_audit": {
            "executed_excluded_identity_count": len(load_excluded_ids(config, root)[0]),
            "selected_executed_identity_overlap": 0,
            "superseded_designs_zero_execution_verified": True,
            "phase0_to_phase6_reuse": False,
            "skillbank_source_split": "train_only",
        },
        "execution_authorized": False,
        "fresh_exact_user_authorization_required": True,
        "readiness_allowed": False,
        "readiness_blocker": "selector implementation and adversarial unit tests not yet frozen",
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }
    preflight["aggregate_fingerprint"] = hashlib.sha256(json.dumps({
        "config_sha256": config_hash,
        "plan_sha256": plan_hash,
        "schedule_sha256": schedule_hash,
        "globally_unique_template_count": 30,
        "condition_position_counts": preflight["condition_position_counts"],
        "selector_contract": config["selector_contract"],
        "estimands": config["estimands"],
        "decision_gate": config["decision_gate"],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    (root / PREFLIGHT_REL).write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 4,
        "phase_id": config["phase_id"],
        "status": "complete",
        "completion_kind": "zero_network_design_preflight",
        "planned_rows": 360,
        "materialized_rows": 360,
        "rows": 360,
        "completed_calls": 0,
        "executed_calls": 0,
        "aggregate_fingerprint": preflight["aggregate_fingerprint"],
        "development_task_count": 30,
        "replicate_count": 3,
        "conditions": 4,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "execution_authorized": False,
        "readiness_allowed": False,
        "phase0_to_phase6_reuse": False,
    }
    (root / MANIFEST_REL).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    try:
        result = run(read_json(args.config))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    print(f"VALID: froze {result['globally_unique_template_count']} global templates and {result['materialized_row_count']} balanced rows; completed_calls=0; readiness_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
