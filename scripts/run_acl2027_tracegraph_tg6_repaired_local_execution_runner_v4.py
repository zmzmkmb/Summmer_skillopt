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
from scripts.run_acl2027_tracegraph_tg6_repaired_local_execution_preflight_v2 import (
    validate as validate_preflight,
)

CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_repaired_local_execution_runner_v4.json"
PREFLIGHT = ROOT / "configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v2.json"
PREFLIGHT_SHA256 = "9eb082c1e775c2355629c88abd7f8099dc97260dfca923418a2afae6cddc1df2"
MANIFEST_SHA256 = "921344f3658215d8aaa4ef7deea5afa978d41a1ecf6aa6503d57040740c389fd"
REPAIR_PREFLIGHT_SHA256 = "b38728824423e934df397c84e3566b85d99b5155215df9048d7533f3dc0e7686"
ZERO_STEP_EVIDENCE_SHA256 = "5c0aee25718d1edca68e6e06c5954b2210186c8f4de2d805f067549fa246dc7b"
COMPLETION_MANIFEST_SHA256 = "9247481e0a1e066cff063530b6ab3a3bf45466f4532a0fc3f6f26cc00d863fd5"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_v4(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG6-tracegraph-repaired-local-execution-runner-v4",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "parent_scope_config": "configs/acl2027/tracegraph_tg6_repaired_local_execution_preflight_v2.json",
        "parent_scope_config_sha256": PREFLIGHT_SHA256,
        "episode_count": 40,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_rule": "stop on first hard invariant violation",
        "pddl_repair_manifest": "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/repair_manifest.json",
        "pddl_repair_manifest_sha256": MANIFEST_SHA256,
        "pddl_repair_preflight": "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/preflight.json",
        "pddl_repair_preflight_sha256": REPAIR_PREFLIGHT_SHA256,
        "zero_step_evidence": "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/zero_step_evidence.json",
        "zero_step_evidence_sha256": ZERO_STEP_EVIDENCE_SHA256,
        "pddl_repair_completion_manifest": "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/completion_manifest.json",
        "pddl_repair_completion_manifest_sha256": COMPLETION_MANIFEST_SHA256,
        "derived_gamefile_root": "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/derived",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            errors.append(f"{key} mismatch")

    if not PREFLIGHT.is_file() or sha256(PREFLIGHT) != PREFLIGHT_SHA256:
        errors.append("parent execution preflight fingerprint mismatch")
    else:
        errors.extend(f"parent preflight: {error}" for error in validate_preflight(json.loads(PREFLIGHT.read_text(encoding="utf-8"))))

    if config.get("runtime_allowed_inputs") != base.ALLOWED_INPUTS:
        errors.append("runtime allowed inputs mismatch")
    if not base.FORBIDDEN_INPUTS.issubset(set(config.get("runtime_forbidden_inputs", []))):
        errors.append("runtime forbidden inputs incomplete")

    false_keys = (
        "official_source_fallback_allowed",
        "terminal_tg6_retry_or_resume_allowed",
        "network_calls_allowed",
        "provider_calls_allowed",
        "model_calls_allowed",
        "api_calls_allowed",
        "paid_api_calls_allowed",
        "authorization_receipts_allowed",
        "phase6_execution_allowed",
        "phase0_to_phase6_reuse_allowed",
        "other_models_allowed",
        "other_datasets_allowed",
        "expanded_batch_allowed",
        "tuning_allowed",
    )
    for key in false_keys:
        if config.get(key) is not False:
            errors.append(f"{key} must be false")

    if config.get("execution_authorized") is not True:
        errors.append("exact user authorization is not bound")
    if config.get("fresh_exact_user_authorization_required") is not True:
        errors.append("fresh authorization gate missing")
    if config.get("derived_gamefile_manifest_enforced") is not True:
        errors.append("derived gamefile manifest must be enforced")
    if config.get("webshop_status") != "blocked_pending_preregistered_alfworld_mechanism_gate":
        errors.append("WebShop gate relaxed")

    for path_key, hash_key in (
        ("heldout_schedule", "heldout_schedule_sha256"),
        ("runtime_runner_dryrun", "runtime_runner_dryrun_sha256"),
        ("skillbank", "skillbank_sha256"),
        ("pddl_repair_manifest", "pddl_repair_manifest_sha256"),
        ("pddl_repair_preflight", "pddl_repair_preflight_sha256"),
        ("zero_step_evidence", "zero_step_evidence_sha256"),
        ("pddl_repair_completion_manifest", "pddl_repair_completion_manifest_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")

    expected_root = (root / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2/derived").resolve()
    configured_root = (root / str(config.get("derived_gamefile_root", ""))).resolve()
    if not configured_root.is_dir() or configured_root != expected_root:
        errors.append("derived gamefile root mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.config.is_file():
        print("ERROR: authorized v4 config is missing", file=sys.stderr)
        return 2
    config = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate_v4(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"ERROR: refusing to overwrite {args.output}", file=sys.stderr)
        return 2

    base.validate_authorized_config = validate_v4
    try:
        result = base.run(config, args.output, args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"TG6 repaired v4 runner: started {result['episodes_started']}/{result['task_count']} episodes; "
        f"completed={result['episodes_completed']}; successes={result['successes']}; "
        "official_fallback=false; network/provider/model/API=0/0/0/0"
    )
    return 0 if result["hard_invariant_violation"] is None and result["episodes_completed"] == 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
