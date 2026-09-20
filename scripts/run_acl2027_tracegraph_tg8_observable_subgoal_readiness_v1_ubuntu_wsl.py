#!/usr/bin/env python3
"""TG8 reset-only WSL readiness plus zero-action selector probes."""
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

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as env_base  # noqa: E402
from scripts import run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3 as selector  # noqa: E402

CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_readiness_v1_ubuntu_wsl.json"
CONDITIONS = selector.CONDITIONS
ALLOWED_INPUTS = selector.ALLOWED_INPUTS
EXPECTED_SELECTOR = "scripts/run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3.py"
EXPECTED_SELECTOR_CONFIG = "configs/acl2027/tracegraph_tg8_observable_subgoal_selector_v3.json"
EXPECTED_SELECTOR_AUDIT = (
    "artifacts/acl2027_tracegraph_tg8_observable_subgoal_selector_audit_v3/selector_audit.json"
)
EXPECTED_SELECTOR_AUDIT_MANIFEST = (
    "artifacts/acl2027_tracegraph_tg8_observable_subgoal_selector_audit_v3/run_manifest.json"
)


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
        "phase_id": "TG8-tracegraph-observable-subgoal-readiness-v1",
        "mode": "zero_network_reset_readiness",
        "task_count": 30,
        "condition_count": 4,
        "selector_probe_count": 120,
        "episodes_run": 0,
        "actions_taken": 0,
        "max_steps_per_episode": 0,
        "execution_authorized": False,
        "readiness_only": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    # Readiness must bind the frozen v3 selector and its v3 audit artifact;
    # accepting a stale v2 path would make the zero-step probes non-reproducible.
    if config.get("selector") != EXPECTED_SELECTOR:
        errors.append("readiness selector must be selector v3")
    if config.get("selector_audit") != EXPECTED_SELECTOR_AUDIT:
        errors.append("readiness selector audit must be audit v3")
    if config.get("selector_probe_count") != config.get("task_count", 0) * config.get("condition_count", 0):
        errors.append("selector probe count must equal task_count * condition_count")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime input boundary mismatch")
    for key in (
        "network_calls_allowed", "provider_calls_allowed", "model_calls_allowed",
        "api_calls_allowed", "paid_api_calls_allowed", "phase0_to_phase6_reuse_allowed",
        "phase6_execution_allowed", "webshop_execution_allowed", "other_models_allowed",
        "other_datasets_allowed",
    ):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    for path_key, hash_key in (
        ("parent_preflight", "parent_preflight_sha256"),
        ("preflight_config", "preflight_config_sha256"),
        ("selector", "selector_sha256"),
        ("selector_audit", "selector_audit_sha256"),
        ("development_schedule", "development_schedule_sha256"),
        ("skillbank", "skillbank_sha256"),
    ):
        path = root / str(config[path_key])
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config[hash_key]:
            errors.append(f"{path_key} hash mismatch")
    selector_path = root / EXPECTED_SELECTOR
    if selector_path.is_file():
        source = selector_path.read_text(encoding="utf-8")
        for forbidden in ("load_alfworld_builder", ".step(", "requests", "httpx", "openai", "anthropic"):
            if forbidden in source:
                errors.append(f"selector v3 contains forbidden execution/network token: {forbidden}")
    selector_config_path = root / EXPECTED_SELECTOR_CONFIG
    if not selector_config_path.is_file():
        errors.append("missing selector v3 config")
    else:
        selector_config = read_json(selector_config_path)
        if selector_config.get("selector") != EXPECTED_SELECTOR:
            errors.append("selector v3 config source mismatch")
        if selector_config.get("selector_sha256") != config.get("selector_sha256"):
            errors.append("selector v3 config source hash mismatch")
        if selector_config.get("audit") != EXPECTED_SELECTOR_AUDIT:
            errors.append("selector v3 config audit mismatch")
        if selector_config.get("audit_manifest") != EXPECTED_SELECTOR_AUDIT_MANIFEST:
            errors.append("selector v3 config audit manifest mismatch")
    readiness_audit = read_json(root / str(config["selector_audit"]))
    if readiness_audit.get("phase_id") != "TG8-tracegraph-observable-subgoal-selector-v3":
        errors.append("selector audit phase mismatch")
    if readiness_audit.get("status") != "passed" or readiness_audit.get("passed_case_count") != 5:
        errors.append("selector audit is not passed 5/5")
    if any(readiness_audit.get(key) != 0 for key in (
        "episodes_run", "actions_taken", "network_calls", "provider_calls",
        "model_calls", "api_calls", "paid_api_calls",
    )):
        errors.append("selector audit is not zero-step/zero-network")
    audit_manifest_path = root / EXPECTED_SELECTOR_AUDIT_MANIFEST
    if not audit_manifest_path.is_file():
        errors.append("missing selector audit manifest")
    else:
        audit_manifest = read_json(audit_manifest_path)
        if audit_manifest.get("phase_id") != "TG8-tracegraph-observable-subgoal-selector-v3":
            errors.append("selector audit manifest phase mismatch")
        if audit_manifest.get("audit") != EXPECTED_SELECTOR_AUDIT:
            errors.append("selector audit manifest source mismatch")
        if audit_manifest.get("audit_sha256") != sha256(root / EXPECTED_SELECTOR_AUDIT):
            errors.append("selector audit manifest hash mismatch")
        for key in ("episodes_run", "actions_taken", "network_calls", "provider_calls", "model_calls", "api_calls", "paid_api_calls"):
            if audit_manifest.get(key) != 0:
                errors.append(f"selector audit manifest {key} must be zero")
    schedule = read_json(root / str(config["development_schedule"]))
    if len(schedule.get("tasks") or []) != 30 or len({row.get("task_identity") for row in schedule.get("tasks") or []}) != 30:
        errors.append("TG8 v4 schedule is not 30 unique tasks")
    if len(schedule.get("rows") or []) != 360:
        errors.append("TG8 v4 schedule does not contain 360 materialized rows")
    return errors


def load_tasks(config: dict[str, Any], root: Path = ROOT) -> list[dict[str, Any]]:
    schedule = read_json(root / str(config["development_schedule"]))
    return list(schedule["tasks"])


def readiness(config: dict[str, Any], data_root: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite readiness output: {output}")
    tasks = load_tasks(config)
    builder = env_base.load_alfworld_builder()
    index = selector.base.load_skill_index(ROOT / str(config["skillbank"]))
    rows: list[dict[str, Any]] = []
    for ordinal, task in enumerate(tasks):
        gamefile = env_base.resolve_gamefile(data_root, task)
        row: dict[str, Any] = {
            "task_identity": task["task_identity"],
            "split": task["split"],
            "task_family": task["task_family"],
            "template_key": task["template_key"],
            "task_relative_path": task["task_relative_path"],
            "gamefile": str(gamefile),
            "gamefile_sha256": sha256(gamefile) if gamefile.is_file() else None,
            "seed": 5200 + ordinal,
            "actions_taken": 0,
            "episodes_run": 0,
        }
        if not gamefile.is_file():
            row.update({"status": "failed", "error_type": "FileNotFoundError", "error": str(gamefile)})
            rows.append(row)
            continue
        dataset = "eval_in_distribution" if task["split"] == "valid_seen" else "eval_out_of_distribution"
        env = builder(
            str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"),
            seed=5200 + ordinal,
            env_num=1,
            group_n=1,
            resources_per_worker=None,
            is_train=False,
            env_kwargs={"eval_dataset": dataset},
            gamefiles=[str(gamefile)],
        )
        try:
            observations, _images, infos = env.reset()
            observation = str(observations[0])
            admissible = [str(item) for item in (env.get_admissible_commands[0] or [])]
            runtime_inputs = {
                "observation": observation,
                "historical_actions": [],
                "admissible_actions": admissible,
            }
            probes = []
            for condition in CONDITIONS:
                transition = selector.select_condition(index, condition, runtime_inputs)
                valid, message = selector.validate_selector_transition(transition, index=index)
                if not valid:
                    raise RuntimeError(f"selector probe invalid for {condition}: {message}")
                probes.append({
                    "condition": condition,
                    "selected_action": transition["terminal_action_decision"],
                    "pending_subgoal_id": transition["pending_subgoal_id"],
                    "trace_valid": valid,
                })
            row.update({
                "status": "passed",
                "observation_present": bool(observation),
                "admissible_action_count": len(admissible),
                "info_present": bool(infos and isinstance(infos[0], dict)),
                "selector_probe_count": len(probes),
                "selector_probes": probes,
            })
        except Exception as exc:  # noqa: BLE001
            row.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        finally:
            env.close()
        rows.append(row)
    passed = sum(row["status"] == "passed" for row in rows)
    probe_count = sum(int(row.get("selector_probe_count", 0)) for row in rows)
    result = {
        "schema_version": 1,
        "phase_id": config["phase_id"],
        "artifact_type": "tracegraph_tg8_observable_subgoal_zero_step_readiness",
        "status": "passed" if passed == len(rows) == 30 and probe_count == 120 else "blocked_environment_readiness",
        "task_count": len(rows),
        "passed_task_count": passed,
        "failed_task_count": len(rows) - passed,
        "selector_probe_count": probe_count,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "runtime_allowed_inputs": ALLOWED_INPUTS,
        "rows": rows,
        "execution_authorized": False,
        "readiness_only": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = read_json(args.config)
    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    output = args.output or (ROOT / str(config["readiness_output"]))
    try:
        result = readiness(config, args.data_root, output)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"TG8 zero-step readiness: passed={result['passed_task_count']}/30; "
        f"selector_probes={result['selector_probe_count']}/120; actions=0; episodes=0"
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
