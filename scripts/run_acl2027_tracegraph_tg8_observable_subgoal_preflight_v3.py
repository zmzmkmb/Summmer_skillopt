#!/usr/bin/env python3
"""Freeze the corrected TG8 v3 factorial pilot and explicit row schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_preflight_v2 import (
    collect_candidates,
    family_from_relative,
    read_json,
    sha256,
    template_key,
)

CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_preflight_v3.json"
SCHEDULE_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v3/development_schedule.json"
PREFLIGHT_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v3/preflight.json"
MANIFEST_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v3/completion_manifest.json"
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


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG8-tracegraph-observable-subgoal-preflight-v3",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_design_only",
        "task_family": "tg8_observable_subgoal_factorial_pilot_v3",
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
    for item in config.get("superseded_unexecuted_designs") or []:
        path = root / str(item.get("path", ""))
        if not path.is_file() or sha256(path) != item.get("sha256"):
            errors.append("superseded design fingerprint mismatch")
            continue
        data = read_json(path)
        if data.get("episodes_run") != 0 or item.get("episodes_run") != 0:
            errors.append("superseded design must have zero episodes")
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


def rank_value(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()


def choose_distinct_templates(candidates: list[dict[str, str]], quota: int) -> list[dict[str, str]]:
    by_template: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        by_template.setdefault(row["template_key"], []).append(row)
    if len(by_template) < quota:
        raise ValueError(f"not enough distinct templates: {len(by_template)} < {quota}")
    representatives = []
    for key, rows in by_template.items():
        chosen = min(rows, key=lambda row: rank_value("tg8-v3-task", row["task_identity"]))
        representatives.append((key, chosen))
    representatives.sort(key=lambda item: rank_value("tg8-v3-template", item[0]))
    return [row for _, row in representatives[:quota]]


def condition_order(task_id: str, replicate_index: int) -> list[str]:
    return sorted(CONDITIONS, key=lambda condition: rank_value(f"tg8-v3-order:{task_id}:{replicate_index}", condition))


def build_schedule(config: dict[str, Any], root: Path = ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    excluded, exclusion_manifest = load_excluded_ids(config, root)
    source_root = Path(str(config["source_data_root"]))
    tasks: list[dict[str, Any]] = []
    quota = int(config["family_split_quota"])
    for split in ("valid_seen", "valid_unseen"):
        for family in FAMILIES:
            candidates = [row for row in collect_candidates(source_root, split, family) if row["task_identity"] not in excluded]
            for row in choose_distinct_templates(candidates, quota):
                row["stratum"] = "tg8_v3_unique_template_pilot"
                tasks.append(row)
    if len(tasks) != 30 or len({row["task_identity"] for row in tasks}) != 30:
        raise ValueError("TG8 v3 must contain 30 unique task identities")
    for split in ("valid_seen", "valid_unseen"):
        for family in FAMILIES:
            cell = [row for row in tasks if row["split"] == split and row["task_family"] == family]
            if len(cell) != 5 or len({row["template_key"] for row in cell}) != 5:
                raise ValueError(f"template-unique cell mismatch: {split}/{family}")
    rows: list[dict[str, Any]] = []
    for ordinal, task in enumerate(tasks):
        for replicate_index in range(int(config["replicate_count"])):
            seed = 5200 + 100 * replicate_index + ordinal
            for position, condition in enumerate(condition_order(task["task_identity"], replicate_index)):
                run_id = hashlib.sha256(f"tg8-v3:{task['task_identity']}:{replicate_index}:{condition}".encode("utf-8")).hexdigest()
                rows.append({
                    "run_id": run_id,
                    "task_identity": task["task_identity"],
                    "task_ordinal": ordinal,
                    "split": task["split"],
                    "task_family": task["task_family"],
                    "template_key": task["template_key"],
                    "replicate_index": replicate_index,
                    "seed": seed,
                    "condition": condition,
                    "condition_position": position,
                    "max_steps": 75,
                    "primary_step_landmark": 50,
                })
    if len(rows) != 360 or len({row["run_id"] for row in rows}) != 360:
        raise ValueError("TG8 v3 row schedule mismatch")
    return tasks, rows, exclusion_manifest


def run(config: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors = validate_config(config, root)
    if errors:
        raise ValueError("; ".join(errors))
    paths = [root / SCHEDULE_REL, root / PREFLIGHT_REL, root / MANIFEST_REL]
    if any(path.exists() for path in paths):
        raise FileExistsError("TG8 v3 preflight artifacts already exist")
    tasks, rows, exclusion_manifest = build_schedule(config, root)
    schedule_path = root / SCHEDULE_REL
    schedule = {
        "schema_version": 3,
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "selection_rule": "one stable-hash-ranked identity from each of five stable-hash-ranked distinct templates per family and split",
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
    template_counts = {f"{split}/{family}": len({row["template_key"] for row in tasks if row["split"] == split and row["task_family"] == family}) for split in ("valid_seen", "valid_unseen") for family in FAMILIES}
    preflight = {
        "schema_version": 3,
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
        "superseded_unexecuted_designs": config["superseded_unexecuted_designs"],
        "executed_identity_exclusion_sources": exclusion_manifest,
        "skillbank": config["skillbank"],
        "skillbank_sha256": config["skillbank_sha256"],
        "development_schedule": SCHEDULE_REL,
        "development_schedule_sha256": schedule_hash,
        "development_task_count": 30,
        "replicate_count": 3,
        "planned_episode_rows": 360,
        "split_counts": {split: sum(row["split"] == split for row in tasks) for split in ("valid_seen", "valid_unseen")},
        "family_counts": {family: sum(row["task_family"] == family for row in tasks) for family in FAMILIES},
        "template_counts": template_counts,
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
            "superseded_designs_all_zero_episode": True,
            "phase0_to_phase6_reuse": False,
            "skillbank_source_split": "train_only",
        },
        "execution_authorized": False,
        "fresh_exact_user_authorization_required": True,
        "readiness_allowed": False,
        "readiness_blocker": "selector implementation and adversarial unit tests not yet frozen",
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
        "conditions": config["conditions"],
        "development_task_count": 30,
        "replicate_count": 3,
        "planned_episode_rows": 360,
        "selector_contract": config["selector_contract"],
        "estimands": config["estimands"],
        "decision_gate": config["decision_gate"],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    (root / PREFLIGHT_REL).write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 3,
        "phase_id": config["phase_id"],
        "status": "complete",
        "completion_kind": "zero_network_design_preflight",
        "completed_calls": 360,
        "rows": 360,
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
    print(f"VALID: froze {result['development_task_count']} unique-template TG8 v3 tasks and {result['planned_episode_rows']} explicit rows; readiness_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
