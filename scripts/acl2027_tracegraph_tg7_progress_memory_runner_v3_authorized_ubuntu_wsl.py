#!/usr/bin/env python3
"""Execute the exact user-authorized TG7 WSL run after all bindings validate."""
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

from scripts import run_acl2027_tracegraph_tg7_progress_memory_runner_v1 as base

CONFIG = ROOT / "configs/acl2027/tracegraph_tg7_progress_memory_runner_v3_authorized_ubuntu_wsl.json"
PREFLIGHT_AGGREGATE = "48470f6d571cf4a40547304ea475a536ab9855b40efaf644839b40e7fcdfc0d2"
CANDIDATE_CONFIG_SHA256 = "ff78a67030b00a85b594da064f9c0fa6cedc1e2685438bd0ab674496b0aea737"
READINESS_SHA256 = "b5ed392361360e0c3152e43a73f42da87be74b545a2521b1491fbb9c6089f3fc"
COMPLETION_MANIFEST_SHA256 = "7164f2fb6a8401546496fd6197db86dfb791d937302c199792d34d7e1d279909"
ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_authorized_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    closed = dict(config)
    closed["execution_authorized"] = False
    closed["episode_execution_allowed"] = False
    closed["readiness_only_allowed"] = True
    closed["phase_id"] = "TG7-tracegraph-progress-memory-runner-v1"
    closed["mode"] = "zero_network_runner_preflight"
    configured_root = Path(str(closed.get("source_data_root", "")))
    windows_root = str(closed.get("source_data_root_windows", ""))
    if not configured_root.is_dir() and windows_root and Path(windows_root).is_dir():
        closed["source_data_root"] = windows_root
    errors.extend(base.validate_config(closed, root))

    if config.get("execution_authorized") is not True:
        errors.append("execution_authorized must be true")
    if config.get("episode_execution_allowed") is not True:
        errors.append("episode_execution_allowed must be true")
    if config.get("readiness_only_allowed") is not False:
        errors.append("readiness_only_allowed must be false")
    if config.get("authorization_status") != "authorized":
        errors.append("authorization_status must be authorized")
    if config.get("preflight_aggregate_fingerprint") != PREFLIGHT_AGGREGATE:
        errors.append("preflight aggregate fingerprint mismatch")
    if config.get("authorized_candidate_config_sha256") != CANDIDATE_CONFIG_SHA256:
        errors.append("candidate config fingerprint mismatch")
    if config.get("completion_manifest_sha256") != COMPLETION_MANIFEST_SHA256:
        errors.append("completion manifest fingerprint mismatch")
    if config.get("readiness_artifact_sha256") != READINESS_SHA256:
        errors.append("readiness fingerprint mismatch")
    if config.get("planned_episode_rows") != 72 or config.get("development_task_count") != 24:
        errors.append("TG7 scope must be 24 tasks and 72 rows")
    if config.get("max_steps_per_episode") != 50 or config.get("max_retries") != 0:
        errors.append("step/retry scope mismatch")
    if config.get("stop_rule") != "stop on first hard invariant violation":
        errors.append("stop rule mismatch")
    if config.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
        errors.append("runtime input boundary mismatch")
    runner_path = root / str(config.get("runner", ""))
    if not runner_path.is_file() or config.get("runner_sha256") != sha256(runner_path):
        errors.append("authorized runner missing or changed")

    candidate_path = root / str(config.get("authorized_candidate_config", ""))
    if not candidate_path.is_file() or sha256(candidate_path) != CANDIDATE_CONFIG_SHA256:
        errors.append("authorized candidate config missing or changed")

    readiness_path = root / str(config.get("readiness_artifact", ""))
    if not readiness_path.is_file() or sha256(readiness_path) != READINESS_SHA256:
        errors.append("readiness artifact missing or changed")
    elif (
        read_json(readiness_path).get("status") != "passed"
        or read_json(readiness_path).get("passed_task_count") != 24
        or read_json(readiness_path).get("failed_task_count") != 0
        or read_json(readiness_path).get("actions_taken") != 0
        or read_json(readiness_path).get("episodes_run") != 0
    ):
        errors.append("readiness gate payload is not 24/24 zero-action")

    manifest_path = root / "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/completion_manifest.json"
    if not manifest_path.is_file() or sha256(manifest_path) != COMPLETION_MANIFEST_SHA256:
        errors.append("preflight completion manifest missing or changed")
    elif read_json(manifest_path).get("aggregate_fingerprint") != PREFLIGHT_AGGREGATE:
        errors.append("preflight completion aggregate mismatch")

    receipt_path = root / str(config.get("authorization_receipt", ""))
    if not receipt_path.is_file():
        errors.append("authorization receipt missing")
    elif config.get("authorization_receipt_sha256") != sha256(receipt_path):
        errors.append("authorization receipt fingerprint mismatch")
    else:
        receipt = read_json(receipt_path)
        if receipt.get("status") != "authorized" or receipt.get("authorization_opened") is not True:
            errors.append("authorization receipt is not open/authorized")
        bindings = receipt.get("bindings", {})
        if bindings.get("preflight_aggregate_fingerprint") != PREFLIGHT_AGGREGATE:
            errors.append("receipt preflight binding mismatch")
        if bindings.get("readiness_artifact_sha256") != READINESS_SHA256:
            errors.append("receipt readiness binding mismatch")
        if bindings.get("candidate_config_sha256") != CANDIDATE_CONFIG_SHA256:
            errors.append("receipt candidate binding mismatch")
        scope = receipt.get("scope", {})
        if scope.get("planned_episode_rows") != 72 or scope.get("max_steps_per_episode") != 50:
            errors.append("receipt episode scope mismatch")
        if scope.get("max_retries") != 0 or scope.get("stop_rule") != "stop on first hard invariant violation":
            errors.append("receipt stop/retry scope mismatch")
        if scope.get("runtime_allowed_inputs") != ALLOWED_INPUTS:
            errors.append("receipt runtime boundary mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = read_json(args.config)
    errors = validate_authorized_config(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    output = args.output or (ROOT / str(config["episode_result_output"]))
    if output.exists():
        print(f"ERROR: refusing to overwrite {output}", file=sys.stderr)
        return 2
    result = base.run_episodes(config, args.data_root, output)
    result["execution_bindings"] = {
        "authorized_config": str(args.config),
        "authorized_candidate_config_sha256": config["authorized_candidate_config_sha256"],
        "authorization_receipt_sha256": config["authorization_receipt_sha256"],
        "runner_sha256": config["runner_sha256"],
        "preflight_aggregate_fingerprint": PREFLIGHT_AGGREGATE,
        "readiness_artifact_sha256": READINESS_SHA256,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"TG7 authorized v3 runner: rows={result['episodes_started']}/72; "
        f"completed={result['episodes_completed']}; successes={result['successes']}; "
        "network/provider/model/API=0/0/0/0"
    )
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 72 else 1


if __name__ == "__main__":
    raise SystemExit(main())
