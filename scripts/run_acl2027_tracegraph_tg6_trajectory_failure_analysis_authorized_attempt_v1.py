#!/usr/bin/env python3
"""Execute one freshly authorized TG6 trajectory-diagnostic attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from scripts import run_acl2027_tracegraph_tg6_trajectory_failure_analysis_runner_v1 as base

ROOT = Path(__file__).resolve().parents[1]
CLOSED = ROOT / "configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_runner_v1.json"
PREFLIGHT = ROOT / "configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_preflight_v2.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(config: dict) -> list[str]:
    errors = []
    if config.get("execution_authorized") is not True or config.get("episode_execution_allowed") is not True:
        errors.append("authorized execution flags missing")
    if config.get("runtime_platform") != "WSL Ubuntu":
        errors.append("runtime platform must be WSL Ubuntu")
    if config.get("planned_episode_rows") != 72 or config.get("max_steps_per_episode") != 50 or config.get("max_retries") != 0:
        errors.append("episode scope mismatch")
    if config.get("authorization_preflight_fingerprint") != "b82976f1c5be80bd00d67f4e0397f8a72f4eb56282536864ca649a8f9fe74d07":
        errors.append("user-bound preflight fingerprint mismatch")
    if config.get("parent_runner_config_sha256") != "bc16c19c53fa2c5d8fdc04fbffa369dca1e2df5ca091f9a5e5632c8b0dd22281":
        errors.append("user-bound runner fingerprint mismatch")
    if sha256(CLOSED) != config.get("parent_runner_config_sha256"):
        errors.append("closed runner fingerprint does not match")
    if sha256(PREFLIGHT) != config.get("parent_preflight_sha256"):
        errors.append("preflight file fingerprint mismatch")
    if config.get("runtime_allowed_inputs") != ["observation", "historical_actions", "admissible_actions"]:
        errors.append("runtime input boundary mismatch")
    for key in ("official_source_fallback_allowed", "network_calls_allowed", "provider_calls_allowed", "model_calls_allowed", "api_calls_allowed", "paid_api_calls_allowed", "phase0_to_phase6_reuse_allowed", "phase6_execution_allowed", "webshop_execution_allowed", "other_models_allowed", "other_datasets_allowed"):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    output = ROOT / str(config["episode_result_output"])
    if output.exists():
        print(f"ERROR: refusing to overwrite {output}", file=sys.stderr)
        return 2
    result = base.run_episodes(config, args.data_root, output)
    print(f"TG6 trajectory authorized attempt: rows={result['episodes_started']}/72; completed={result['episodes_completed']}; successes={result['successes']}; network/provider/model/API=0/0/0/0")
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 72 else 1


if __name__ == "__main__":
    raise SystemExit(main())
