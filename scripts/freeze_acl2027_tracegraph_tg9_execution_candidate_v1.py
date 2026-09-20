#!/usr/bin/env python3
"""Freeze the closed TG9 execution candidate and its aggregate fingerprint."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg9_runner_candidate_v1.json"
ANALYZER = ROOT / "scripts/analyze_acl2027_tracegraph_tg9_factorial_v1.py"
MANIFESTS = (
    ROOT / "artifacts/acl2027_tracegraph_tg9_failure_audit_v1/completion_manifest.json",
    ROOT / "artifacts/acl2027_tracegraph_tg9_task_pool_preflight_v1/completion_manifest.json",
    ROOT / "artifacts/acl2027_tracegraph_tg9_interaction_skillbank_v1/completion_manifest.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def freeze(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("execution_authorized") is not False:
        raise ValueError("candidate must remain unauthorized")
    if config.get("authorization_receipt") is not None:
        raise ValueError("candidate must not contain an authorization receipt")
    if config.get("planned_rows") != 180 or config.get("max_steps_per_episode") != 50:
        raise ValueError("row count or step-50 horizon mismatch")
    bound = {
        "runner_config_sha256": sha256(CONFIG),
        "schedule_sha256": config["schedule_sha256"],
        "selector_sha256": config["selector_sha256"],
        "base_skillbank_sha256": config["base_skillbank_sha256"],
        "interaction_skillbank_sha256": config["interaction_skillbank_sha256"],
        "readiness_sha256": config["readiness_sha256"],
        "runner_sha256": config["runner_sha256"],
        "analysis_script_sha256": sha256(ANALYZER),
        "governance_manifest_sha256": {
            path.parent.name: sha256(path) for path in MANIFESTS
        },
        "conditions": [
            "type_level_current_coverage",
            "instance_bound_current_coverage",
            "type_level_open_close_coverage",
            "instance_bound_open_close_coverage",
        ],
        "runtime_allowed_inputs": config["runtime_allowed_inputs"],
        "planned_rows": 180,
        "max_steps_per_episode": 50,
        "max_retries": 0,
        "stop_on_first_hard_invariant_violation": True,
    }
    for path in [CONFIG, ANALYZER, *MANIFESTS]:
        if not path.is_file():
            raise FileNotFoundError(path)
    return {
        "schema_version": "tg9-execution-candidate-v1",
        "status": "frozen_closed_pending_fresh_exact_authorization",
        "created_date": "2026-09-18",
        "bindings": bound,
        "aggregate_fingerprint": canonical_hash(bound),
        "primary_endpoint": "completion_by_step_50",
        "step_75_endpoint_status": "unavailable",
        "validation_label": "internal_validation_not_blind_confirmatory",
        "execution_authorized": False,
        "readiness_allowed": False,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload = freeze(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VALID: TG9 candidate {payload['aggregate_fingerprint']}; execution_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
