#!/usr/bin/env python3
"""Run the exact repair-v2-bound TG6 local authorization."""
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

from scripts import run_acl2027_tracegraph_tg6_repaired_local_execution_runner_v1 as base

CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_repaired_local_execution_runner_v3.json"
MANIFEST_SHA256 = "2d604905b9c45b81b07478741c45f191b4da31e6198b454f6394464effa64e1e"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_v3(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG6-tracegraph-repaired-local-execution-runner-v3",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "episode_count": 40,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_rule": "stop on first hard invariant violation",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")
    if config.get("runtime_allowed_inputs") != base.ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    manifest = root / str(config.get("pddl_repair_manifest", ""))
    if not manifest.is_file() or sha256(manifest) != MANIFEST_SHA256:
        errors.append("repair v2 manifest fingerprint mismatch")
    derived = (root / str(config.get("derived_gamefile_root", ""))).resolve()
    if not derived.is_dir():
        errors.append("repair v2 derived root missing")
    false_keys = (
        "official_source_fallback_allowed", "terminal_tg6_retry_or_resume_allowed",
        "network_calls_allowed", "provider_calls_allowed", "model_calls_allowed",
        "api_calls_allowed", "paid_api_calls_allowed", "authorization_receipts_allowed",
        "phase6_execution_allowed", "phase0_to_phase6_reuse_allowed",
        "other_models_allowed", "other_datasets_allowed", "expanded_batch_allowed",
        "tuning_allowed",
    )
    for key in false_keys:
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    if config.get("execution_authorized") is not True:
        errors.append("execution authorization is not true")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate_v3(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"ERROR: refusing to overwrite {args.output}", file=sys.stderr)
        return 2
    base.validate_authorized_config = validate_v3
    try:
        result = base.run(config, args.output, args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"TG6 repaired v3 runner: started {result['episodes_started']}/{result['task_count']} episodes; "
        f"completed={result['episodes_completed']}; successes={result['successes']}; "
        "official_fallback=false; network/provider/model/API=0/0/0/0"
    )
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
