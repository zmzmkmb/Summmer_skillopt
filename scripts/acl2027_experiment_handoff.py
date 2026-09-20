#!/usr/bin/env python3
"""Validate and summarize the persistent ACL 2027 experiment state."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_STATE = PROJECT_ROOT / "paper" / "acl2027" / "experiment_state.json"
ALLOWED_PHASE_STATUSES = {"planned", "in_progress", "completed", "blocked"}
REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "project",
    "updated_at",
    "paper_goal",
    "execution_policy",
    "last_completed_phase",
    "current_phase",
    "completed_phases",
    "verification",
    "entrypoints",
    "checkpoints",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def load_state(state_path: Path = DEFAULT_STATE) -> dict[str, Any]:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"state file does not exist: {state_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"state file is invalid JSON: {state_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("experiment state must be a JSON object")
    return payload


def _validate_call_manifest(
    *,
    errors: list[str],
    phase_id: str,
    phase: dict[str, Any],
    expected_runs: int,
    manifest: dict[str, Any],
    manifest_path: Path,
    artifact_dir: Path,
    config_path: Path | None,
) -> None:
    """Validate completed online-call artifacts with a separate analysis manifest."""
    for field in ("planned_logical_calls", "provider_attempts", "recorded_calls"):
        if manifest.get(field) != expected_runs:
            errors.append(
                f"completed phase {phase_id} {field} mismatch: "
                f"expected={expected_runs!r}, manifest={manifest.get(field)!r}"
            )
    if manifest.get("status") not in {"completed", "completed_with_invalid_outputs"}:
        errors.append(
            f"completed phase {phase_id} call manifest is not terminal: "
            f"{manifest.get('status')!r}"
        )
    if manifest.get("usage_known_for_all_attempts") is not True:
        errors.append(
            f"completed phase {phase_id} usage_known_for_all_attempts is not true"
        )

    if config_path and config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"completed phase {phase_id} config is unreadable: {exc}")
        else:
            planned_hash = (
                config.get("immutable_request_plan", {}).get("stable_sha256")
                if isinstance(config, dict)
                else None
            )
            if planned_hash != manifest.get("request_plan_sha256"):
                errors.append(
                    f"completed phase {phase_id} request-plan fingerprint mismatch: "
                    f"config={planned_hash!r}, manifest={manifest.get('request_plan_sha256')!r}"
                )

    analysis_path = artifact_dir / "analysis_manifest.json"
    if not analysis_path.is_file():
        errors.append(
            f"completed phase {phase_id} analysis manifest does not exist: {analysis_path}"
        )
        return
    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"completed phase {phase_id} analysis manifest is unreadable: {exc}")
        return
    if not isinstance(analysis, dict):
        errors.append(f"completed phase {phase_id} analysis manifest must be a JSON object")
        return
    if analysis.get("status") != "completed":
        errors.append(f"completed phase {phase_id} analysis status is not completed")
    if analysis.get("scored_calls") != expected_runs:
        errors.append(
            f"completed phase {phase_id} scored_calls mismatch: "
            f"expected={expected_runs!r}, analysis={analysis.get('scored_calls')!r}"
        )
    state_fingerprint = phase.get("aggregate_fingerprint")
    analysis_fingerprint = analysis.get("aggregate_fingerprint")
    if state_fingerprint != analysis_fingerprint:
        errors.append(
            f"completed phase {phase_id} aggregate fingerprint mismatch: "
            f"state={state_fingerprint!r}, manifest={analysis_fingerprint!r}"
        )
    manifest_hash = analysis.get("immutable_input_hashes", {}).get("live_run_manifest")
    actual_manifest_hash = _sha256_file(manifest_path)
    if manifest_hash != actual_manifest_hash:
        errors.append(
            f"completed phase {phase_id} live manifest SHA256 mismatch: "
            f"analysis={manifest_hash!r}, actual={actual_manifest_hash}"
        )

    output_names = {
        "scored_records": "scored_records.jsonl",
        "analysis_aggregates": "analysis_aggregates.json",
        "design_audit": "design_audit.json",
    }
    output_hashes = analysis.get("output_hashes")
    if not isinstance(output_hashes, dict):
        errors.append(f"completed phase {phase_id} analysis output_hashes must be an object")
        return
    for key, filename in output_names.items():
        output_path = artifact_dir / filename
        if not output_path.is_file():
            errors.append(f"completed phase {phase_id} analysis output is missing: {output_path}")
            continue
        actual_hash = _sha256_file(output_path)
        if output_hashes.get(key) != actual_hash:
            errors.append(
                f"completed phase {phase_id} analysis output SHA256 mismatch for "
                f"{filename}: manifest={output_hashes.get(key)!r}, actual={actual_hash}"
            )


def _validate_aggregate_completion_manifest(
    *,
    errors: list[str],
    phase_id: str,
    phase: dict[str, Any],
    expected_runs: int,
    manifest: dict[str, Any],
) -> None:
    """Validate a terminal aggregate audit used by recovery-style phases."""
    if manifest.get("status") != "complete":
        errors.append(f"completed phase {phase_id} aggregate status is not complete")
    for field in ("completed_calls", "rows"):
        if manifest.get(field) != expected_runs:
            errors.append(
                f"completed phase {phase_id} {field} mismatch: "
                f"expected={expected_runs!r}, manifest={manifest.get(field)!r}"
            )
    state_fingerprint = phase.get("aggregate_fingerprint")
    manifest_fingerprint = manifest.get("aggregate_fingerprint")
    if state_fingerprint != manifest_fingerprint:
        errors.append(
            f"completed phase {phase_id} aggregate fingerprint mismatch: "
            f"state={state_fingerprint!r}, manifest={manifest_fingerprint!r}"
        )


def validate_state(state: dict[str, Any], root: Path = PROJECT_ROOT) -> list[str]:
    """Return validation errors. An empty list means the handoff state is valid."""
    errors: list[str] = []

    missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - state.keys())
    if missing:
        errors.append("missing required top-level fields: " + ", ".join(missing))

    policy = state.get("execution_policy")
    if not isinstance(policy, dict):
        errors.append("execution_policy must be an object")
        policy = {}
    for field in ("paid_api_allowed", "formal_scaling_allowed", "provider_calls_allowed"):
        if not isinstance(policy.get(field), bool):
            errors.append(f"execution_policy.{field} must be an explicit boolean")

    active_line = state.get("active_research_line")
    if not isinstance(active_line, dict):
        errors.append("active_research_line must be an object")
        active_line = {}
    for field in ("id", "title", "status", "authoritative_plan", "primary_endpoints"):
        if field not in active_line:
            errors.append(f"active_research_line.{field} is required")
    plan_path_value = active_line.get("authoritative_plan")
    if not isinstance(plan_path_value, str) or not plan_path_value:
        errors.append("active_research_line.authoritative_plan must be a nonempty path")
    elif not _resolve(root, plan_path_value).is_file():
        errors.append(f"active research plan does not exist: {plan_path_value}")

    tracegraph = state.get("tracegraph")
    if not isinstance(tracegraph, dict):
        errors.append("tracegraph must be an object")
        tracegraph = {}
    for field in ("current_stage", "status", "primary_environment", "webshop_status", "skillbank_source", "runtime_allowed_inputs", "composer", "base_model", "phase0_to_phase6"):
        if field not in tracegraph:
            errors.append(f"tracegraph.{field} is required")
    stage = tracegraph.get("current_stage")
    if stage not in {"TG0", "TG1", "TG6", "TG7", "TG8"}:
        errors.append("tracegraph.current_stage must be TG0, TG1, TG6, TG7, or TG8")
    if stage == "TG1":
        tg1 = tracegraph.get("tg1_preflight")
        if not isinstance(tg1, dict):
            errors.append("tracegraph.tg1_preflight must be an object during TG1")
        else:
            if tg1.get("status") != "zero-network-preflight-planned":
                errors.append("tracegraph.tg1_preflight.status must be zero-network-preflight-planned")
            for field in ("config", "plan", "script", "source_audit_script"):
                value = tg1.get(field)
                if not isinstance(value, str) or not _resolve(root, value).is_file():
                    errors.append(f"tracegraph.tg1_preflight.{field} must point to an existing file")
    if stage == "TG6":
        tg6 = tracegraph.get("tg6_execution")
        if not isinstance(tg6, dict):
            errors.append("tracegraph.tg6_execution must be an object during TG6")
        else:
            required_tg6 = (
                "status",
                "artifact_dir",
                "result",
                "manifest",
                "result_sha256",
                "manifest_sha256",
                "episodes_scheduled",
                "episodes_started",
                "episodes_completed",
                "successes",
                "max_retries",
                "stop_rule",
                "network_calls",
                "provider_calls",
                "model_calls",
                "paid_api_calls",
                "retry_or_resume_forbidden",
            )
            for field in required_tg6:
                if field not in tg6:
                    errors.append(f"tracegraph.tg6_execution.{field} is required")
            if tg6.get("status") != "blocked_local_environment_integrity":
                errors.append(
                    "tracegraph.tg6_execution.status must be blocked_local_environment_integrity"
                )
            artifact_dir_value = tg6.get("artifact_dir")
            artifact_dir = (
                _resolve(root, artifact_dir_value)
                if isinstance(artifact_dir_value, str) and artifact_dir_value
                else None
            )
            if artifact_dir is None or not artifact_dir.is_dir():
                errors.append("tracegraph.tg6_execution.artifact_dir must point to an existing directory")
            else:
                for field in ("result", "manifest"):
                    value = tg6.get(field)
                    path = _resolve(root, value) if isinstance(value, str) and value else None
                    if path is None or not path.is_file():
                        errors.append(f"tracegraph.tg6_execution.{field} must point to an existing file")
                result_path = _resolve(root, tg6.get("result")) if isinstance(tg6.get("result"), str) else None
                manifest_path = _resolve(root, tg6.get("manifest")) if isinstance(tg6.get("manifest"), str) else None
                if result_path is not None and result_path.is_file():
                    actual_result_hash = _sha256_file(result_path)
                    if tg6.get("result_sha256") != actual_result_hash:
                        errors.append(
                            "tracegraph.tg6_execution.result_sha256 mismatch: "
                            f"state={tg6.get('result_sha256')!r}, actual={actual_result_hash}"
                        )
                if manifest_path is not None and manifest_path.is_file():
                    actual_manifest_hash = _sha256_file(manifest_path)
                    if tg6.get("manifest_sha256") != actual_manifest_hash:
                        errors.append(
                            "tracegraph.tg6_execution.manifest_sha256 mismatch: "
                            f"state={tg6.get('manifest_sha256')!r}, actual={actual_manifest_hash}"
                        )
            expected_counts = {
                "episodes_scheduled": 40,
                "episodes_started": 2,
                "episodes_completed": 1,
                "successes": 0,
                "max_retries": 0,
                "network_calls": 0,
                "provider_calls": 0,
                "model_calls": 0,
                "paid_api_calls": 0,
            }
            for field, expected in expected_counts.items():
                if tg6.get(field) != expected:
                    errors.append(
                        f"tracegraph.tg6_execution.{field} must remain {expected!r}; "
                        f"got {tg6.get(field)!r}"
                    )
            if tg6.get("retry_or_resume_forbidden") is not True:
                errors.append("tracegraph.tg6_execution.retry_or_resume_forbidden must be true")
            if tg6.get("stop_rule") != "stop on first hard invariant violation":
                errors.append("tracegraph.tg6_execution.stop_rule is not preserved")
        repaired = tracegraph.get("tg6_repaired_execution")
        if not isinstance(repaired, dict):
            errors.append("tracegraph.tg6_repaired_execution must be an object during TG6")
        else:
            required_repaired = (
                "status",
                "artifact_dir",
                "config",
                "config_sha256",
                "parent_scope_config_sha256",
                "result",
                "result_sha256",
                "manifest",
                "manifest_sha256",
                "episodes_scheduled",
                "episodes_started",
                "episodes_completed",
                "successes",
                "max_retries",
                "stop_rule",
                "runtime_allowed_inputs",
                "hard_invariant_violation",
                "official_source_fallback_used",
                "network_calls",
                "provider_calls",
                "model_calls",
                "api_calls",
                "paid_api_calls",
                "phase0_to_phase6_reuse",
                "phase6_executed",
                "webshop_executed",
                "retry_or_resume_used",
            )
            for field in required_repaired:
                if field not in repaired:
                    errors.append(f"tracegraph.tg6_repaired_execution.{field} is required")
            if repaired.get("status") != "completed_zero_network_execution":
                errors.append(
                    "tracegraph.tg6_repaired_execution.status must be completed_zero_network_execution"
                )
            artifact_dir_value = repaired.get("artifact_dir")
            artifact_dir = (
                _resolve(root, artifact_dir_value)
                if isinstance(artifact_dir_value, str) and artifact_dir_value
                else None
            )
            if artifact_dir is None or not artifact_dir.is_dir():
                errors.append(
                    "tracegraph.tg6_repaired_execution.artifact_dir must point to an existing directory"
                )
            for path_field, hash_field in (
                ("config", "config_sha256"),
                ("result", "result_sha256"),
                ("manifest", "manifest_sha256"),
            ):
                value = repaired.get(path_field)
                path = _resolve(root, value) if isinstance(value, str) and value else None
                if path is None or not path.is_file():
                    errors.append(
                        f"tracegraph.tg6_repaired_execution.{path_field} must point to an existing file"
                    )
                elif repaired.get(hash_field) != _sha256_file(path):
                    errors.append(
                        f"tracegraph.tg6_repaired_execution.{hash_field} mismatch"
                    )
            expected_repaired_counts = {
                "episodes_scheduled": 40,
                "episodes_started": 40,
                "episodes_completed": 40,
                "successes": 0,
                "max_retries": 0,
                "network_calls": 0,
                "provider_calls": 0,
                "model_calls": 0,
                "api_calls": 0,
                "paid_api_calls": 0,
            }
            for field, expected in expected_repaired_counts.items():
                if repaired.get(field) != expected:
                    errors.append(
                        f"tracegraph.tg6_repaired_execution.{field} must be {expected!r}; "
                        f"got {repaired.get(field)!r}"
                    )
            if repaired.get("runtime_allowed_inputs") != [
                "observation",
                "historical_actions",
                "admissible_actions",
            ]:
                errors.append(
                    "tracegraph.tg6_repaired_execution.runtime_allowed_inputs must contain only "
                    "observation, historical_actions, and admissible_actions"
                )
            if repaired.get("hard_invariant_violation") is not None:
                errors.append(
                    "tracegraph.tg6_repaired_execution.hard_invariant_violation must be null"
                )
            for field in (
                "official_source_fallback_used",
                "phase0_to_phase6_reuse",
                "phase6_executed",
                "webshop_executed",
                "retry_or_resume_used",
            ):
                if repaired.get(field) is not False:
                    errors.append(
                        f"tracegraph.tg6_repaired_execution.{field} must be false"
                    )
            if repaired.get("stop_rule") != "stop on first hard invariant violation":
                errors.append("tracegraph.tg6_repaired_execution.stop_rule is not preserved")
        derived = tracegraph.get("tg6_derived_repair")
        if derived is not None:
            if not isinstance(derived, dict):
                errors.append("tracegraph.tg6_derived_repair must be an object")
            else:
                required_repair = (
                    "status",
                    "config",
                    "config_sha256",
                    "repair_manifest",
                    "repair_manifest_sha256",
                    "preflight",
                    "preflight_sha256",
                    "task_count",
                    "repaired_task_count",
                    "planner_status_counts",
                    "episodes_run",
                    "network_calls",
                    "provider_calls",
                    "model_calls",
                    "paid_api_calls",
                    "source_files_mutated",
                    "frozen_schedule_mutated",
                    "terminal_tg6_artifact_mutated",
                    "fresh_execution_authorization_required",
                )
                for field in required_repair:
                    if field not in derived:
                        errors.append(f"tracegraph.tg6_derived_repair.{field} is required")
                if derived.get("status") != "completed_zero_network_preflight":
                    errors.append(
                        "tracegraph.tg6_derived_repair.status must be completed_zero_network_preflight"
                    )
                for path_field, hash_field in (
                    ("config", "config_sha256"),
                    ("repair_manifest", "repair_manifest_sha256"),
                    ("preflight", "preflight_sha256"),
                ):
                    value = derived.get(path_field)
                    path = _resolve(root, value) if isinstance(value, str) and value else None
                    if path is None or not path.is_file():
                        errors.append(
                            f"tracegraph.tg6_derived_repair.{path_field} must point to an existing file"
                        )
                    elif derived.get(hash_field) != _sha256_file(path):
                        errors.append(
                            f"tracegraph.tg6_derived_repair.{hash_field} mismatch"
                        )
                expected_repair_counts = {
                    "task_count": 40,
                    "repaired_task_count": 8,
                    "episodes_run": 0,
                    "network_calls": 0,
                    "provider_calls": 0,
                    "model_calls": 0,
                    "paid_api_calls": 0,
                }
                for field, expected in expected_repair_counts.items():
                    if derived.get(field) != expected:
                        errors.append(
                            f"tracegraph.tg6_derived_repair.{field} must remain {expected!r}"
                        )
                if derived.get("planner_status_counts") != {"passed": 40}:
                    errors.append(
                        "tracegraph.tg6_derived_repair.planner_status_counts must be {'passed': 40}"
                    )
                for field in (
                    "source_files_mutated",
                    "frozen_schedule_mutated",
                    "terminal_tg6_artifact_mutated",
                ):
                    if derived.get(field) is not False:
                        errors.append(f"tracegraph.tg6_derived_repair.{field} must be false")
                if derived.get("fresh_execution_authorization_required") is not True:
                    errors.append(
                        "tracegraph.tg6_derived_repair.fresh_execution_authorization_required must be true"
                    )
    if tracegraph.get("primary_environment") != "ALFWorld":
        errors.append("tracegraph.primary_environment must be ALFWorld")
    if tracegraph.get("webshop_status") != "blocked_pending_preregistered_alfworld_mechanism_gate":
        errors.append("tracegraph.webshop_status must preserve the ALFWorld mechanism gate")
    if tracegraph.get("runtime_allowed_inputs") != ["observation", "historical_actions", "admissible_actions"]:
        errors.append("tracegraph.runtime_allowed_inputs must contain only observation, historical_actions, and admissible_actions")
    isolation = tracegraph.get("phase0_to_phase6")
    if not isinstance(isolation, dict) or isolation.get("status") != "frozen-read-only":
        errors.append("tracegraph.phase0_to_phase6 must be frozen-read-only")
    elif not {"TraceGraph data source", "SkillBank construction", "tuning", "evaluation substrate"}.issubset(set(isolation.get("forbidden_uses", []))):
        errors.append("tracegraph.phase0_to_phase6 must prohibit TraceGraph data, SkillBank, tuning, and evaluation use")
    if active_line.get("id") != "tracegraph-observable-state-skill-composition":
        errors.append("active_research_line.id must be tracegraph-observable-state-skill-composition")
    if active_line.get("authoritative_plan") != "paper/acl2027/TRACEGRAPH_RESEARCH_PLAN.md":
        errors.append("active_research_line.authoritative_plan must be the TraceGraph plan")

    current = state.get("current_phase")
    if not isinstance(current, dict):
        errors.append("current_phase must be an object")
        current = {}
    for field in ("id", "title", "status", "objective", "next_actions", "expected_write_scope"):
        if field not in current:
            errors.append(f"current_phase.{field} is required")
    if current.get("research_line") != active_line.get("id"):
        errors.append("current_phase.research_line must match active_research_line.id")

    if current.get("status") not in ALLOWED_PHASE_STATUSES:
        errors.append(
            "current_phase.status must be one of "
            + ", ".join(sorted(ALLOWED_PHASE_STATUSES))
            + f"; got {current.get('status')!r}"
        )
    if not isinstance(current.get("next_actions"), list) or not current.get("next_actions"):
        errors.append("current_phase.next_actions must be a nonempty list")
    if not isinstance(current.get("expected_write_scope"), list) or not current.get("expected_write_scope"):
        errors.append("current_phase.expected_write_scope must be a nonempty list")

    entrypoints = state.get("entrypoints")
    if not isinstance(entrypoints, dict):
        errors.append("entrypoints must be an object")
        entrypoints = {}
    for name in ("roadmap", "protocol", "status_script", "graph"):
        value = entrypoints.get(name)
        if not isinstance(value, str) or not value:
            errors.append(f"entrypoints.{name} must be a nonempty path")
        elif not _resolve(root, value).exists():
            errors.append(f"entrypoint does not exist: {name}={value}")

    completed = state.get("completed_phases")
    if not isinstance(completed, list):
        errors.append("completed_phases must be a list")
        completed = []
    completed_ids: set[str] = set()
    for index, phase in enumerate(completed):
        label = f"completed_phases[{index}]"
        if not isinstance(phase, dict):
            errors.append(f"{label} must be an object")
            continue
        phase_id = phase.get("id")
        if not isinstance(phase_id, str) or not phase_id:
            errors.append(f"{label}.id must be a nonempty string")
            phase_id = f"index-{index}"
        else:
            if phase_id in completed_ids:
                errors.append(f"duplicate completed phase id: {phase_id}")
            completed_ids.add(phase_id)
        if phase.get("status") != "completed":
            errors.append(f"completed phase {phase_id} must have status='completed'")

        expected_runs = phase.get("expected_runs")
        if not isinstance(expected_runs, int) or isinstance(expected_runs, bool) or expected_runs <= 0:
            errors.append(f"completed phase {phase_id} expected_runs must be a positive integer")

        required_paths = {}
        for field in ("config", "artifact_dir", "report"):
            value = phase.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"completed phase {phase_id} missing path: {field}")
                continue
            path = _resolve(root, value)
            required_paths[field] = path
            if not path.exists():
                errors.append(f"completed phase {phase_id} path does not exist: {value}")
        artifact_dir = required_paths.get("artifact_dir")
        if artifact_dir is None or not artifact_dir.is_dir():
            continue
        completion_manifest = phase.get("completion_manifest")
        if completion_manifest is not None and (
            not isinstance(completion_manifest, str) or not completion_manifest
        ):
            errors.append(
                f"completed phase {phase_id} completion_manifest must be a nonempty string"
            )
            continue
        manifest_path = artifact_dir / (completion_manifest or "run_manifest.json")
        if not manifest_path.is_file():
            errors.append(f"completed phase {phase_id} manifest does not exist: {manifest_path}")
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"completed phase {phase_id} manifest is unreadable: {exc}")
            continue
        if not isinstance(manifest, dict):
            errors.append(f"completed phase {phase_id} manifest must be a JSON object")
            continue

        if completion_manifest is not None:
            _validate_aggregate_completion_manifest(
                errors=errors,
                phase_id=phase_id,
                phase=phase,
                expected_runs=expected_runs,
                manifest=manifest,
            )
            continue

        config_path = required_paths.get("config")
        if "planned_logical_calls" in manifest:
            _validate_call_manifest(
                errors=errors,
                phase_id=phase_id,
                phase=phase,
                expected_runs=expected_runs,
                manifest=manifest,
                manifest_path=manifest_path,
                artifact_dir=artifact_dir,
                config_path=config_path,
            )
            continue

        manifest_expected = manifest.get("expected_runs")
        available_runs = manifest.get("available_runs")
        runs = manifest.get("runs")
        if manifest_expected != expected_runs:
            errors.append(
                f"completed phase {phase_id} expected_runs mismatch: "
                f"state={expected_runs!r}, manifest={manifest_expected!r}"
            )
        if available_runs != expected_runs:
            errors.append(
                f"completed phase {phase_id} available_runs mismatch: "
                f"expected={expected_runs!r}, manifest={available_runs!r}"
            )
        if manifest.get("complete_grid") is not True:
            errors.append(f"completed phase {phase_id} manifest complete_grid is not true")
        state_fingerprint = phase.get("aggregate_fingerprint")
        manifest_fingerprint = manifest.get("aggregate_fingerprint")
        if state_fingerprint != manifest_fingerprint:
            errors.append(
                f"completed phase {phase_id} aggregate fingerprint mismatch: "
                f"state={state_fingerprint!r}, manifest={manifest_fingerprint!r}"
            )
        if not isinstance(runs, list):
            errors.append(f"completed phase {phase_id} manifest.runs must be a list")
            continue
        if len(runs) != expected_runs:
            errors.append(
                f"completed phase {phase_id} run-list length mismatch: "
                f"expected={expected_runs}, actual={len(runs)}"
            )

        if config_path and config_path.is_file():
            declared_config = manifest.get("config_path")
            if declared_config != phase.get("config"):
                errors.append(
                    f"completed phase {phase_id} config path mismatch: "
                    f"state={phase.get('config')!r}, manifest={declared_config!r}"
                )
            actual_config_hash = _sha256_file(config_path)
            if manifest.get("config_sha256") != actual_config_hash:
                errors.append(
                    f"completed phase {phase_id} config SHA256 mismatch: "
                    f"manifest={manifest.get('config_sha256')!r}, actual={actual_config_hash}"
                )

        seen_run_ids: set[str] = set()
        seen_result_paths: set[str] = set()
        for run_index, run in enumerate(runs):
            run_label = f"completed phase {phase_id} run[{run_index}]"
            if not isinstance(run, dict):
                errors.append(f"{run_label} must be an object")
                continue
            run_id = run.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                errors.append(f"{run_label} has no run_id")
            elif run_id in seen_run_ids:
                errors.append(f"completed phase {phase_id} has duplicate run_id: {run_id}")
            else:
                seen_run_ids.add(run_id)
            result_value = run.get("result_path")
            if not isinstance(result_value, str) or not result_value:
                errors.append(f"{run_label} has no result_path")
                continue
            if result_value in seen_result_paths:
                errors.append(f"completed phase {phase_id} has duplicate result_path: {result_value}")
            seen_result_paths.add(result_value)
            result_path = _resolve(root, result_value)
            if not result_path.is_file():
                errors.append(f"{run_label} result file does not exist: {result_value}")
                continue
            expected_hash = run.get("file_sha256")
            actual_hash = _sha256_file(result_path)
            if expected_hash != actual_hash:
                errors.append(
                    f"{run_label} SHA256 mismatch for {result_value}: "
                    f"manifest={expected_hash!r}, actual={actual_hash}"
                )

    last_completed = state.get("last_completed_phase")
    if last_completed not in completed_ids:
        errors.append(
            f"last_completed_phase={last_completed!r} is not present in completed_phases"
        )

    checkpoints = state.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        errors.append("checkpoints must be a nonempty list")

    verification = state.get("verification")
    if not isinstance(verification, dict):
        errors.append("verification must be an object")
    else:
        for field in ("test_command", "last_result", "last_verified_at"):
            if not isinstance(verification.get(field), str) or not verification.get(field):
                errors.append(f"verification.{field} must be a nonempty string")

    return errors


def status_payload(state: dict[str, Any]) -> dict[str, Any]:
    current = state["current_phase"]
    policy = state["execution_policy"]
    verification = state["verification"]
    return {
        "project": state["project"],
        "updated_at": state["updated_at"],
        "last_completed_phase": state["last_completed_phase"],
        "current_phase": current["id"],
        "current_title": current["title"],
        "current_status": current["status"],
        "objective": current["objective"],
        "paid_api_allowed": policy["paid_api_allowed"],
        "formal_scaling_allowed": policy["formal_scaling_allowed"],
        "next_actions": current["next_actions"],
        "last_test_result": verification["last_result"],
        "last_verified_at": verification["last_verified_at"],
    }


def format_status(state: dict[str, Any]) -> str:
    payload = status_payload(state)
    actions = "\n".join(
        f"  {index}. {action}" for index, action in enumerate(payload["next_actions"], start=1)
    )
    return (
        f"Project: {payload['project']}\n"
        f"Updated: {payload['updated_at']}\n"
        f"Last completed phase: {payload['last_completed_phase']}\n"
        f"Current phase: {payload['current_phase']} - {payload['current_title']} "
        f"[{payload['current_status']}]\n"
        f"Objective: {payload['objective']}\n"
        f"Paid API allowed: {str(payload['paid_api_allowed']).lower()}\n"
        f"Formal scaling allowed: {str(payload['formal_scaling_allowed']).lower()}\n"
        f"Next actions:\n{actions}\n"
        f"Last test verification: {payload['last_test_result']} "
        f"({payload['last_verified_at']})"
    )


def format_handoff(state: dict[str, Any]) -> str:
    current = state["current_phase"]
    policy = state["execution_policy"]
    actions = "\n".join(
        f"{index}. {action}" for index, action in enumerate(current["next_actions"], start=1)
    )
    scope = "\n".join(f"- {item}" for item in current["expected_write_scope"])
    return (
        "Continue the SummerSkillOpt ACL 2027 experiment from repository state, not chat memory.\n\n"
        "Startup:\n"
        "1. Read paper/acl2027/experiment_state.json and "
        "paper/acl2027/CROSS_CONVERSATION_PROTOCOL.md.\n"
        "2. Run `python scripts/acl2027_experiment_handoff.py validate`.\n"
        "3. Run `python scripts/acl2027_experiment_handoff.py status`.\n"
        f"4. Resume Phase {current['id']} ({current['title']}) with status "
        f"{current['status']}.\n\n"
        f"Objective: {current['objective']}\n\n"
        f"Paid API allowed: {str(policy['paid_api_allowed']).lower()}\n"
        f"Formal scaling allowed: {str(policy['formal_scaling_allowed']).lower()}\n\n"
        f"Ordered next actions:\n{actions}\n\n"
        f"Expected write scope:\n{scope}\n\n"
        "Do not rerun validated completed artifacts or touch unrelated repository work. "
        "After material progress, update experiment_state.json, append a checkpoint, run the "
        "relevant regression suite, and validate the state again."
    )


def _print_errors(errors: Iterable[str]) -> None:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help="Experiment-state JSON path (defaults to the repository state file).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("command", choices=("validate", "status", "handoff"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        state = load_state(args.state)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = validate_state(state, PROJECT_ROOT)
    if args.command == "validate":
        if args.json:
            print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        elif errors:
            _print_errors(errors)
        else:
            completed = state.get("completed_phases", [])
            run_count = sum(int(item.get("expected_runs", 0)) for item in completed if isinstance(item, dict))
            print(
                f"VALID: {len(completed)} completed phases, {run_count} immutable runs, "
                f"current Phase {state['current_phase']['id']}."
            )
        return 0 if not errors else 1

    if errors:
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
        else:
            _print_errors(errors)
        return 1

    if args.command == "status":
        if args.json:
            print(json.dumps(status_payload(state), ensure_ascii=False, indent=2))
        else:
            print(format_status(state))
        return 0

    if args.json:
        print(json.dumps({"handoff": format_handoff(state)}, ensure_ascii=False, indent=2))
    else:
        print(format_handoff(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
