#!/usr/bin/env python3
"""Freeze TG8 v2's zero-network, cluster-aware factorial pilot design."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_preflight_v2.json"
OUTPUT_DIR = ROOT / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2"
SCHEDULE_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2/development_schedule.json"
PREFLIGHT_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2/preflight.json"
MANIFEST_REL = "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2/completion_manifest.json"
FAMILIES = (
    "pick_and_place_simple",
    "pick_two_obj_and_place",
    "pick_clean_then_place_in_recep",
)
CONDITIONS = (
    "baseline_first_eligible",
    "lexical_progress_memory",
    "observable_subgoal_first_eligible",
    "observable_subgoal_progress_memory",
)
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = {
    "task_description", "raw_trajectory", "planner_state", "pddl_params",
    "scene_state", "expert_future_actions", "evaluation_label",
    "phase0_to_phase6_artifact", "tg6_private_metadata", "tg7_private_metadata",
    "tg8_private_metadata",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def task_identity(split: str, relative: str) -> str:
    return hashlib.sha256(f"{split}:{relative}".encode("utf-8")).hexdigest()


def family_from_relative(relative: str) -> str | None:
    parts = relative.split("/")
    if len(parts) < 2:
        return None
    return next((family for family in FAMILIES if parts[1].startswith(f"{family}-")), None)


def template_key(relative: str) -> str:
    stem = Path(relative).parts[1]
    parts = stem.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    return "-".join(parts)


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG8-tracegraph-observable-subgoal-preflight-v2",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_design_only",
        "parent_completed_phase": "TG8-tracegraph-observable-subgoal-preflight-v1",
        "task_family": "tg8_observable_subgoal_factorial_pilot",
        "family_split_quota": 6,
        "development_task_count": 36,
        "replicate_count": 3,
        "planned_episode_rows": 432,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "execution_authorized": False,
        "fresh_exact_user_authorization_required": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if tuple(config.get("families") or []) != FAMILIES:
        errors.append("family order mismatch")
    if config.get("split_counts") != {"valid_seen": 18, "valid_unseen": 18}:
        errors.append("split counts mismatch")
    if tuple(item.get("id") for item in config.get("conditions") or []) != CONDITIONS:
        errors.append("condition order mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")
    if config.get("sensitivity_step_budgets") != [50, 75]:
        errors.append("step-budget sensitivity mismatch")
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
        ("parent_schedule", "parent_schedule_sha256"),
        ("parent_manifest", "parent_manifest_sha256"),
        ("parent_review", "parent_review_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    plan = root / str(config.get("plan", ""))
    if not plan.is_file():
        errors.append("missing plan")
    if not Path(str(config.get("source_data_root", ""))).is_dir():
        errors.append("local ALFWorld source root unavailable")
    for relative in config.get("exclusion_sources") or []:
        if not (root / str(relative)).is_file():
            errors.append(f"missing exclusion source: {relative}")
    return errors


def load_excluded_ids(config: dict[str, Any], root: Path = ROOT) -> tuple[set[str], list[dict[str, Any]]]:
    excluded: set[str] = set()
    manifest: list[dict[str, Any]] = []
    for relative in config["exclusion_sources"]:
        path = root / str(relative)
        data = read_json(path)
        rows = list(data.get("tasks") or data.get("rows") or [])
        ids = {str(row["task_identity"]) for row in rows if isinstance(row, dict) and row.get("task_identity")}
        excluded.update(ids)
        manifest.append({"path": str(relative).replace("\\", "/"), "sha256": sha256(path), "task_identity_count": len(ids)})
    return excluded, manifest


def collect_candidates(source_root: Path, split: str, family: str) -> list[dict[str, str]]:
    base = source_root / "json_2.1.1" / split
    rows: list[dict[str, str]] = []
    for trajectory in sorted(base.rglob("traj_data.json")):
        task_dir = trajectory.parent
        relative = task_dir.relative_to(source_root / "json_2.1.1").as_posix()
        if family_from_relative(relative) != family:
            continue
        gamefile = task_dir / "game.tw-pddl"
        if not gamefile.is_file():
            continue
        rows.append({
            "task_identity": task_identity(split, relative),
            "split": split,
            "task_family": family,
            "task_relative_path": relative,
            "template_key": template_key(relative),
            "gamefile_sha256": sha256(gamefile),
            "trajectory_sha256": sha256(trajectory),
        })
    return rows


def stable_rank(row: dict[str, str]) -> str:
    return hashlib.sha256(f"tg8-v2:{row['split']}:{row['task_family']}:{row['task_identity']}".encode("utf-8")).hexdigest()


def choose_cluster_aware(candidates: list[dict[str, str]], quota: int) -> list[dict[str, str]]:
    ranked = sorted(candidates, key=stable_rank)
    selected: list[dict[str, str]] = []
    seen_templates: set[str] = set()
    for row in ranked:
        if row["template_key"] not in seen_templates:
            selected.append(row)
            seen_templates.add(row["template_key"])
            if len(selected) == quota:
                return selected
    for row in ranked:
        if row not in selected:
            selected.append(row)
            if len(selected) == quota:
                return selected
    raise ValueError("not enough candidates for cluster-aware quota")


def build_schedule(config: dict[str, Any], root: Path = ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded, exclusion_manifest = load_excluded_ids(config, root)
    source_root = Path(str(config["source_data_root"]))
    selected: list[dict[str, Any]] = []
    quota = int(config["family_split_quota"])
    for split in ("valid_seen", "valid_unseen"):
        for family in FAMILIES:
            candidates = [row for row in collect_candidates(source_root, split, family) if row["task_identity"] not in excluded]
            chosen = choose_cluster_aware(candidates, quota)
            for row in chosen:
                row["stratum"] = "tg8_v2_multistep_pilot"
                selected.append(row)
    if len(selected) != 36 or len({row["task_identity"] for row in selected}) != 36:
        raise ValueError("TG8 v2 schedule must contain 36 unique tasks")
    if any(row["task_identity"] in excluded for row in selected):
        raise ValueError("selected task overlaps an exclusion source")
    if sum(row["split"] == "valid_seen" for row in selected) != 18 or sum(row["split"] == "valid_unseen" for row in selected) != 18:
        raise ValueError("split balance mismatch")
    for family in FAMILIES:
        if sum(row["task_family"] == family for row in selected) != 12:
            raise ValueError(f"family count mismatch: {family}")
    return selected, exclusion_manifest


def run(config: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors = validate_config(config, root)
    if errors:
        raise ValueError("; ".join(errors))
    paths = [root / SCHEDULE_REL, root / PREFLIGHT_REL, root / MANIFEST_REL]
    if any(path.exists() for path in paths):
        raise FileExistsError("TG8 v2 preflight artifacts already exist")
    tasks, exclusion_manifest = build_schedule(config, root)
    schedule_path = root / SCHEDULE_REL
    schedule = {
        "schema_version": 2,
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "selection_rule": "fixed SHA-256 rank; first maximize distinct object/receptacle template keys, then fill quota",
        "task_family": config["task_family"],
        "families": list(FAMILIES),
        "tasks": tasks,
        "conditions": config["conditions"],
        "replicate_count": 3,
        "planned_episode_rows": 432,
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
    preflight = {
        "schema_version": 2,
        "status": "complete",
        "phase_status": "completed_zero_network_design_preflight",
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "config": str(CONFIG.relative_to(root)).replace("\\", "/"),
        "config_sha256": config_hash,
        "plan": str(plan_path.relative_to(root)).replace("\\", "/"),
        "plan_sha256": plan_hash,
        "parent_completed_phase": config["parent_completed_phase"],
        "parent_preflight": config["parent_preflight"],
        "parent_preflight_sha256": config["parent_preflight_sha256"],
        "parent_schedule": config["parent_schedule"],
        "parent_schedule_sha256": config["parent_schedule_sha256"],
        "parent_manifest": config["parent_manifest"],
        "parent_manifest_sha256": config["parent_manifest_sha256"],
        "parent_review": config["parent_review"],
        "parent_review_sha256": config["parent_review_sha256"],
        "skillbank": config["skillbank"],
        "skillbank_sha256": config["skillbank_sha256"],
        "exclusion_sources": exclusion_manifest,
        "development_schedule": SCHEDULE_REL,
        "development_schedule_sha256": schedule_hash,
        "task_family": config["task_family"],
        "families": list(FAMILIES),
        "development_task_count": 36,
        "replicate_count": 3,
        "split_counts": {split: sum(row["split"] == split for row in tasks) for split in ("valid_seen", "valid_unseen")},
        "family_counts": {family: sum(row["task_family"] == family for row in tasks) for family in FAMILIES},
        "template_counts": {f"{split}/{family}": len({row["template_key"] for row in tasks if row["split"] == split and row["task_family"] == family}) for split in ("valid_seen", "valid_unseen") for family in FAMILIES},
        "conditions": config["conditions"],
        "planned_episode_rows": 432,
        "max_steps_per_episode": config["max_steps_per_episode"],
        "sensitivity_step_budgets": config["sensitivity_step_budgets"],
        "max_retries": config["max_retries"],
        "stop_rule": config["stop_rule"],
        "paired_seed_rule": config["paired_seed_rule"],
        "condition_order_rule": config["condition_order_rule"],
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "runtime_forbidden_inputs": config["runtime_forbidden_inputs"],
        "estimands": config["estimands"],
        "primary_metrics": config["primary_metrics"],
        "secondary_metrics": config["secondary_metrics"],
        "decision_gate": config["decision_gate"],
        "no_overlap_audit": {
            "excluded_task_identity_count": sum(item["task_identity_count"] for item in exclusion_manifest),
            "selected_task_identity_overlap": 0,
            "phase0_to_phase6_reuse": False,
            "skillbank_source_split": "train_only",
        },
        "execution_authorized": False,
        "fresh_exact_user_authorization_required": True,
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
        "families": list(FAMILIES),
        "development_task_count": 36,
        "replicate_count": 3,
        "planned_episode_rows": 432,
        "estimands": config["estimands"],
        "decision_gate": config["decision_gate"],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    (root / PREFLIGHT_REL).write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "phase_id": config["phase_id"],
        "status": "complete",
        "completion_kind": "zero_network_design_preflight",
        "completed_calls": 432,
        "rows": 432,
        "aggregate_fingerprint": preflight["aggregate_fingerprint"],
        "development_task_count": 36,
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
    print(f"VALID: froze {result['development_task_count']} fresh TG8 v2 tasks and {result['planned_episode_rows']} rows; zero-network design only; execution_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
