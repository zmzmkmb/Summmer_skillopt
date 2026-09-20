#!/usr/bin/env python3
"""Freeze the TG9 two-object task pool and zero-execution row schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg9_task_pool_preflight_v1.json"
OUTPUT_DIR = ROOT / "artifacts/acl2027_tracegraph_tg9_task_pool_preflight_v1"
GENERATOR = ROOT / "scripts/run_acl2027_tracegraph_tg9_task_pool_preflight_v1.py"

TASK_POOL_NAME = "task_pool.json"
SCHEDULE_NAME = "internal_validation_schedule.json"
PREFLIGHT_NAME = "preflight.json"
MANIFEST_NAME = "completion_manifest.json"

TASK_FAMILY = "pick_two_obj_and_place"
SPLITS = ("valid_seen", "valid_unseen")
CONDITIONS = (
    "type_level_current_coverage",
    "instance_bound_current_coverage",
    "type_level_open_close_coverage",
    "instance_bound_open_close_coverage",
)
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = {
    "task_description",
    "raw_trajectory",
    "planner_state",
    "pddl_params",
    "scene_state",
    "environment_object_ids",
    "expert_future_actions",
    "evaluation_label",
    "phase0_to_phase6_artifact",
    "tg6_private_metadata",
    "tg7_private_metadata",
    "tg8_private_metadata",
    "tg9_private_metadata",
}
CLOSED_FLAGS = (
    "execution_authorized",
    "readiness_allowed",
    "episode_execution_allowed",
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
    "tuning_on_internal_validation_allowed",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def task_identity(split: str, relative: str) -> str:
    return hashlib.sha256(f"{split}:{relative}".encode("utf-8")).hexdigest()


def template_key(relative: str) -> str:
    task_dir = Path(relative).parts[1]
    parts = task_dir.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    return "-".join(parts)


def stable_rank(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()


def extract_task_ids(data: dict[str, Any]) -> set[str]:
    rows = list(data.get("tasks") or data.get("rows") or [])
    return {
        str(row["task_identity"])
        for row in rows
        if isinstance(row, dict) and row.get("task_identity")
    }


def validate_bound_sources(
    specs: list[dict[str, Any]], root: Path, label: str
) -> list[str]:
    errors: list[str] = []
    labels: set[str] = set()
    for spec in specs:
        source_label = str(spec.get("label", ""))
        if not source_label or source_label in labels:
            errors.append(f"{label} labels must be present and unique")
        labels.add(source_label)
        path = root / str(spec.get("path", ""))
        if not path.is_file():
            errors.append(f"missing {label}: {path}")
        elif sha256(path) != spec.get("sha256"):
            errors.append(f"{label} fingerprint mismatch: {path}")
    return errors


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG9-tracegraph-task-pool-preflight-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_design_only",
        "task_family": TASK_FAMILY,
        "replicate_count": 3,
        "planned_episode_rows": 180,
        "max_steps_per_episode": 75,
        "primary_step_landmark": 50,
        "conditional_step_75_landmark": 75,
        "step_75_endpoint_status": "unavailable_until_readiness_proves_environment_support",
        "max_retries": 0,
        "independent_unit": "task_identity",
        "validation_label": "internal_validation_not_blind_confirmatory",
        "fresh_exact_user_authorization_required": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if tuple(config.get("splits") or []) != SPLITS:
        errors.append("split order mismatch")
    if tuple(item.get("id") for item in config.get("conditions") or []) != CONDITIONS:
        errors.append("condition order mismatch")
    expected_factor_cells = {
        ("type_level", "current"),
        ("instance_bound", "current"),
        ("type_level", "open_close"),
        ("instance_bound", "open_close"),
    }
    observed_factor_cells = {
        (str(item.get("object_binding")), str(item.get("skill_coverage")))
        for item in config.get("conditions") or []
    }
    if observed_factor_cells != expected_factor_cells:
        errors.append("factor cell mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs") or [])):
        errors.append("runtime forbidden inputs incomplete")
    for key in CLOSED_FLAGS:
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    counts = config.get("expected_counts") or {}
    expected_counts = {
        "runnable_double_object_identities": 41,
        "executed_double_object_identities": 26,
        "pre_tg8_executed_excluded": 16,
        "tg8_executed_diagnosis_only": 10,
        "never_executed_internal_validation": 15,
        "internal_validation_valid_seen": 10,
        "internal_validation_valid_unseen": 5,
        "internal_validation_templates": 11,
        "schedule_contaminated_internal_validation": 13,
        "prior_schedule_identity_blind_internal_validation": 2,
    }
    if counts != expected_counts:
        errors.append("expected counts mismatch")
    blind_ids = set(config.get("expected_prior_schedule_identity_blind_ids") or [])
    if blind_ids != {
        "636f12ec414272e08fb20759618a008de9bebb084ccee16e2076b34284547add",
        "f965e61b35a96d3bff980a93f387a7073422ae9951a4123c09cbc115669a5f4e",
    }:
        errors.append("prior-schedule identity-blind set mismatch")
    plan = root / str(config.get("plan", ""))
    if not plan.is_file():
        errors.append("missing plan")
    elif sha256(plan) != config.get("plan_sha256"):
        errors.append("plan fingerprint mismatch")
    skillbank = root / str(config.get("base_skillbank", ""))
    if not skillbank.is_file():
        errors.append("missing base skillbank")
    elif sha256(skillbank) != config.get("base_skillbank_sha256"):
        errors.append("base skillbank fingerprint mismatch")
    source_root = Path(str(config.get("source_data_root", "")))
    if not source_root.is_dir():
        errors.append("local ALFWorld source root unavailable")
    errors.extend(
        validate_bound_sources(
            list(config.get("executed_result_sources") or []), root, "executed result source"
        )
    )
    errors.extend(
        validate_bound_sources(
            list(config.get("prior_schedule_sources") or []), root, "prior schedule source"
        )
    )
    executed_labels = {
        str(item.get("label")) for item in config.get("executed_result_sources") or []
    }
    if config.get("tg8_executed_source_label") not in executed_labels:
        errors.append("TG8 executed source label is not bound")
    return errors


def collect_candidates(source_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    data_root = source_root / "json_2.1.1"
    for split in SPLITS:
        base = data_root / split
        for trajectory in sorted(base.rglob("traj_data.json")):
            task_dir = trajectory.parent
            relative = task_dir.relative_to(data_root).as_posix()
            parts = Path(relative).parts
            if len(parts) < 2 or not parts[1].startswith(f"{TASK_FAMILY}-"):
                continue
            gamefile = task_dir / "game.tw-pddl"
            if not gamefile.is_file():
                continue
            rows.append(
                {
                    "task_identity": task_identity(split, relative),
                    "split": split,
                    "task_family": TASK_FAMILY,
                    "task_relative_path": relative,
                    "template_key": template_key(relative),
                    "gamefile_sha256": sha256(gamefile),
                    "trajectory_sha256": sha256(trajectory),
                }
            )
    rows.sort(key=lambda row: (row["split"], row["task_relative_path"]))
    if len(rows) != len({row["task_identity"] for row in rows}):
        raise ValueError("duplicate runnable task identity")
    return rows


def load_source_memberships(
    specs: list[dict[str, Any]], candidate_ids: set[str], root: Path
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    memberships: dict[str, set[str]] = {}
    manifest: list[dict[str, Any]] = []
    for spec in specs:
        path = root / str(spec["path"])
        all_ids = extract_task_ids(read_json(path))
        family_ids = all_ids & candidate_ids
        label = str(spec["label"])
        memberships[label] = family_ids
        manifest.append(
            {
                "label": label,
                "path": str(spec["path"]).replace("\\", "/"),
                "sha256": sha256(path),
                "all_task_identity_count": len(all_ids),
                "double_object_task_identity_count": len(family_ids),
            }
        )
    return memberships, manifest


def classify_pool(
    config: dict[str, Any], root: Path = ROOT
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = collect_candidates(Path(str(config["source_data_root"])))
    candidate_ids = {row["task_identity"] for row in candidates}
    executed_memberships, executed_manifest = load_source_memberships(
        list(config["executed_result_sources"]), candidate_ids, root
    )
    schedule_memberships, schedule_manifest = load_source_memberships(
        list(config["prior_schedule_sources"]), candidate_ids, root
    )
    executed_ids = set().union(*executed_memberships.values())
    scheduled_ids = set().union(*schedule_memberships.values())
    tg8_ids = executed_memberships[str(config["tg8_executed_source_label"])]
    pre_tg8_ids = executed_ids - tg8_ids
    internal_ids = candidate_ids - executed_ids
    contaminated_ids = internal_ids & scheduled_ids
    identity_blind_ids = internal_ids - scheduled_ids

    by_id = {row["task_identity"]: row for row in candidates}
    internal_templates = {by_id[identity]["template_key"] for identity in internal_ids}
    executed_templates = {by_id[identity]["template_key"] for identity in executed_ids}
    counts = {
        "runnable_double_object_identities": len(candidate_ids),
        "executed_double_object_identities": len(executed_ids),
        "pre_tg8_executed_excluded": len(pre_tg8_ids),
        "tg8_executed_diagnosis_only": len(tg8_ids),
        "never_executed_internal_validation": len(internal_ids),
        "internal_validation_valid_seen": sum(
            by_id[identity]["split"] == "valid_seen" for identity in internal_ids
        ),
        "internal_validation_valid_unseen": sum(
            by_id[identity]["split"] == "valid_unseen" for identity in internal_ids
        ),
        "internal_validation_templates": len(internal_templates),
        "schedule_contaminated_internal_validation": len(contaminated_ids),
        "prior_schedule_identity_blind_internal_validation": len(identity_blind_ids),
    }
    if counts != config["expected_counts"]:
        raise ValueError(f"task-pool counts mismatch: {counts}")
    if identity_blind_ids != set(config["expected_prior_schedule_identity_blind_ids"]):
        raise ValueError("prior-schedule identity-blind identities changed")
    if executed_ids & internal_ids:
        raise ValueError("executed and internal-validation identities overlap")

    classified: list[dict[str, Any]] = []
    for pool_ordinal, row in enumerate(candidates):
        identity = row["task_identity"]
        if identity in tg8_ids:
            role = "diagnosis_only_tg8_executed"
        elif identity in executed_ids:
            role = "historical_executed_excluded"
        else:
            role = "internal_validation"
        prior_schedule_labels = sorted(
            label for label, ids in schedule_memberships.items() if identity in ids
        )
        executed_result_labels = sorted(
            label for label, ids in executed_memberships.items() if identity in ids
        )
        classified.append(
            {
                **row,
                "pool_ordinal": pool_ordinal,
                "tg9_role": role,
                "eligible_for_internal_validation": role == "internal_validation",
                "executed_result_labels": executed_result_labels,
                "prior_schedule_labels": prior_schedule_labels,
                "schedule_contaminated": identity in contaminated_ids,
                "prior_schedule_identity_blind": identity in identity_blind_ids,
                "template_previously_executed": row["template_key"] in executed_templates,
            }
        )
    audit = {
        **counts,
        "runnable_split_counts": dict(Counter(row["split"] for row in candidates)),
        "runnable_template_count": len({row["template_key"] for row in candidates}),
        "prior_schedule_union_count": len(scheduled_ids),
        "prior_schedule_identity_blind_ids": sorted(identity_blind_ids),
        "claim_boundary": "internal validation only; not blind confirmatory",
    }
    return classified, audit, executed_manifest, schedule_manifest


def build_schedule(
    config: dict[str, Any], classified: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    tasks = [row for row in classified if row["eligible_for_internal_validation"]]
    tasks.sort(
        key=lambda row: (
            row["split"],
            stable_rank("tg9-internal-validation-order", row["task_identity"]),
        )
    )
    scheduled_tasks: list[dict[str, Any]] = []
    for task_ordinal, row in enumerate(tasks):
        scheduled_tasks.append(
            {
                **{key: value for key, value in row.items() if key != "pool_ordinal"},
                "task_ordinal": task_ordinal,
            }
        )

    blocks = [
        (task, replicate_index)
        for task in scheduled_tasks
        for replicate_index in range(int(config["replicate_count"]))
    ]
    blocks.sort(
        key=lambda block: stable_rank(
            "tg9-task-replicate-block",
            f"{block[0]['task_identity']}:{block[1]}",
        )
    )
    rows: list[dict[str, Any]] = []
    for block_ordinal, (task, replicate_index) in enumerate(blocks):
        rotation = block_ordinal % len(CONDITIONS)
        condition_order = CONDITIONS[rotation:] + CONDITIONS[:rotation]
        seed = 6100 + 100 * replicate_index + int(task["task_ordinal"])
        for condition_position, condition in enumerate(condition_order):
            run_id = hashlib.sha256(
                f"tg9-v1:{task['task_identity']}:{replicate_index}:{condition}".encode(
                    "utf-8"
                )
            ).hexdigest()
            rows.append(
                {
                    "run_id": run_id,
                    "block_ordinal": block_ordinal,
                    "task_identity": task["task_identity"],
                    "task_ordinal": task["task_ordinal"],
                    "split": task["split"],
                    "task_family": task["task_family"],
                    "template_key": task["template_key"],
                    "schedule_contaminated": task["schedule_contaminated"],
                    "prior_schedule_identity_blind": task[
                        "prior_schedule_identity_blind"
                    ],
                    "replicate_index": replicate_index,
                    "seed": seed,
                    "condition": condition,
                    "condition_position": condition_position,
                    "latin_rotation": rotation,
                    "max_steps": config["max_steps_per_episode"],
                    "primary_step_landmark": config["primary_step_landmark"],
                    "conditional_step_75_landmark": config[
                        "conditional_step_75_landmark"
                    ],
                }
            )
    if len(rows) != 180 or len({row["run_id"] for row in rows}) != 180:
        raise ValueError("TG9 row schedule must contain 180 unique run IDs")
    per_condition = Counter(row["condition"] for row in rows)
    if per_condition != Counter({condition: 45 for condition in CONDITIONS}):
        raise ValueError("TG9 condition counts are not balanced")
    per_position = Counter((row["condition"], row["condition_position"]) for row in rows)
    if len(per_position) != 16 or set(per_position.values()) - {11, 12}:
        raise ValueError("TG9 condition positions are not balanced")
    return scheduled_tasks, rows, {
        f"{condition}@{position}": per_position[(condition, position)]
        for condition in CONDITIONS
        for position in range(4)
    }


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def build_artifacts(
    config: dict[str, Any], output_dir: Path = OUTPUT_DIR, root: Path = ROOT
) -> dict[str, dict[str, Any]]:
    errors = validate_config(config, root)
    if errors:
        raise ValueError("; ".join(errors))
    classified, audit, executed_manifest, schedule_manifest = classify_pool(config, root)
    scheduled_tasks, rows, position_counts = build_schedule(config, classified)

    task_pool = {
        "schema_version": 1,
        "artifact_type": "tg9_double_object_task_pool",
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "eligibility_rule": config["runnable_rule"],
        "identity_rule": config["identity_rule"],
        "task_family": TASK_FAMILY,
        "splits": list(SPLITS),
        "exposure_audit": audit,
        "executed_result_sources": executed_manifest,
        "prior_schedule_sources": schedule_manifest,
        "tasks": classified,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }
    schedule = {
        "schema_version": 1,
        "artifact_type": "tg9_internal_validation_factorial_schedule",
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "validation_label": config["validation_label"],
        "task_family": TASK_FAMILY,
        "conditions": config["conditions"],
        "independent_unit": config["independent_unit"],
        "replicate_interpretation": config["replicate_interpretation"],
        "tasks": scheduled_tasks,
        "rows": rows,
        "task_count": len(scheduled_tasks),
        "replicate_count": config["replicate_count"],
        "planned_episode_rows": len(rows),
        "condition_position_counts": position_counts,
        "max_steps_per_episode": config["max_steps_per_episode"],
        "primary_step_landmark": config["primary_step_landmark"],
        "conditional_step_75_landmark": config["conditional_step_75_landmark"],
        "step_75_endpoint_status": config["step_75_endpoint_status"],
        "max_retries": config["max_retries"],
        "stop_rule": config["stop_rule"],
        "paired_seed_rule": config["paired_seed_rule"],
        "condition_order_rule": config["condition_order_rule"],
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "runtime_forbidden_inputs": config["runtime_forbidden_inputs"],
        "execution_authorized": False,
        "episode_execution_allowed": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }
    pool_hash = sha256_bytes(json_bytes(task_pool))
    schedule_hash = sha256_bytes(json_bytes(schedule))
    config_hash = sha256(root / relative_path(CONFIG, root))
    generator_hash = sha256(GENERATOR)
    preflight = {
        "schema_version": 1,
        "artifact_type": "tg9_task_pool_preflight",
        "status": "complete",
        "phase_status": "completed_zero_network_design_preflight",
        "phase_id": config["phase_id"],
        "experiment_line": config["experiment_line"],
        "config": relative_path(CONFIG, root),
        "config_sha256": config_hash,
        "generator": relative_path(GENERATOR, root),
        "generator_sha256": generator_hash,
        "plan": config["plan"],
        "plan_sha256": config["plan_sha256"],
        "base_skillbank": config["base_skillbank"],
        "base_skillbank_sha256": config["base_skillbank_sha256"],
        "task_pool": relative_path(output_dir / TASK_POOL_NAME, root),
        "task_pool_sha256": pool_hash,
        "internal_validation_schedule": relative_path(output_dir / SCHEDULE_NAME, root),
        "internal_validation_schedule_sha256": schedule_hash,
        "counts": audit,
        "conditions": config["conditions"],
        "planned_episode_rows": len(rows),
        "materialized_rows": len(rows),
        "independent_task_count": len(scheduled_tasks),
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "runtime_forbidden_inputs": config["runtime_forbidden_inputs"],
        "primary_metrics": config["primary_metrics"],
        "secondary_metrics": config["secondary_metrics"],
        "mechanism_metrics": config["mechanism_metrics"],
        "claim_boundary": audit["claim_boundary"],
        "execution_authorized": False,
        "readiness_allowed": False,
        "episode_execution_allowed": False,
        "fresh_exact_user_authorization_required": True,
        "completed_calls": 0,
        "executed_calls": 0,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }
    preflight["aggregate_fingerprint"] = canonical_fingerprint(
        {
            "config_sha256": config_hash,
            "generator_sha256": generator_hash,
            "plan_sha256": config["plan_sha256"],
            "base_skillbank_sha256": config["base_skillbank_sha256"],
            "task_pool_sha256": pool_hash,
            "internal_validation_schedule_sha256": schedule_hash,
            "conditions": config["conditions"],
            "counts": audit,
            "runtime_allowed_inputs": ALLOWED_INPUTS,
        }
    )
    preflight_hash = sha256_bytes(json_bytes(preflight))
    manifest = {
        "schema_version": 1,
        "artifact_type": "tg9_task_pool_preflight_completion_manifest",
        "status": "complete",
        "completion_kind": "zero_network_design_only",
        "phase_id": config["phase_id"],
        "config_sha256": config_hash,
        "generator_sha256": generator_hash,
        "task_pool_sha256": pool_hash,
        "internal_validation_schedule_sha256": schedule_hash,
        "preflight_sha256": preflight_hash,
        "aggregate_fingerprint": preflight["aggregate_fingerprint"],
        "runnable_task_identities": 41,
        "internal_validation_task_identities": 15,
        "planned_rows": 180,
        "materialized_rows": 180,
        "completed_calls": 0,
        "executed_calls": 0,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "execution_authorized": False,
        "readiness_allowed": False,
        "episode_execution_allowed": False,
    }
    return {
        TASK_POOL_NAME: task_pool,
        SCHEDULE_NAME: schedule,
        PREFLIGHT_NAME: preflight,
        MANIFEST_NAME: manifest,
    }


def write_artifacts(artifacts: dict[str, dict[str, Any]], output_dir: Path) -> None:
    targets = [output_dir / name for name in artifacts]
    if any(path.exists() for path in targets):
        raise FileExistsError("TG9 task-pool preflight artifacts already exist")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in artifacts.items():
        (output_dir / name).write_bytes(json_bytes(value))


def verify_artifacts(artifacts: dict[str, dict[str, Any]], output_dir: Path) -> None:
    for name, expected in artifacts.items():
        path = output_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing TG9 artifact: {path}")
        observed = read_json(path)
        if observed != expected:
            raise ValueError(f"TG9 artifact does not match deterministic rebuild: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        config = read_json(args.config)
        artifacts = build_artifacts(config, args.output_dir)
        if args.verify:
            verify_artifacts(artifacts, args.output_dir)
        else:
            write_artifacts(artifacts, args.output_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    action = "verified" if args.verify else "froze"
    print(
        f"VALID: {action} 41 runnable double-object identities, "
        "10 TG8 diagnosis-only tasks, 15 internal-validation tasks, "
        "and 180 materialized rows; episodes=0; actions=0; "
        "execution_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
