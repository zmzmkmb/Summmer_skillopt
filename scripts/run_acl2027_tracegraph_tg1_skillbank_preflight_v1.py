#!/usr/bin/env python3
"""Validate the zero-network TraceGraph TG1 ALFWorld SkillBank contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "acl2027" / "tracegraph_tg1_alfworld_skillbank_preflight_v1.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("TG1 config must be a JSON object")
    return payload


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "phase_id": "TG1-tracegraph-alfworld-skillbank-preflight-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "zero_network_preflight_only",
        "primary_environment": "ALFWorld",
    }
    for field, value in expected.items():
        if config.get(field) != value:
            errors.append(f"{field} must be {value!r}")
    for field in ("provider_calls_allowed", "model_calls_allowed", "authorization_receipts_allowed"):
        if config.get(field) is not False:
            errors.append(f"{field} must be false")

    source = config.get("source_contract")
    if not isinstance(source, dict):
        errors.append("source_contract must be an object")
    else:
        if source.get("root_env") != "ALFWORLD_DATA":
            errors.append("source_contract.root_env must be ALFWORLD_DATA")
        if source.get("allowed_relative_root") != "json_2.1.1/train":
            errors.append("source_contract.allowed_relative_root must be json_2.1.1/train")
        if source.get("allowed_split") != "train":
            errors.append("source_contract.allowed_split must be train")
        markers = set(source.get("forbidden_path_markers", []))
        if not {"/valid_seen/", "/valid_unseen/", "\\valid_seen\\", "\\valid_unseen\\"}.issubset(markers):
            errors.append("source_contract must reject both ALFWorld evaluation splits")

    skillbank = config.get("skillbank_contract")
    if not isinstance(skillbank, dict):
        errors.append("skillbank_contract must be an object")
    else:
        required = {"trajectory_id", "gamefile_sha256", "traj_data_sha256", "task_type", "source_split"}
        if not required.issubset(set(skillbank.get("required_provenance_fields", []))):
            errors.append("skillbank_contract is missing required provenance fields")
        if skillbank.get("runtime_allowed_inputs") != ["observation", "historical_actions", "admissible_actions"]:
            errors.append("skillbank_contract.runtime_allowed_inputs must match the observable-state contract")
        forbidden = set(skillbank.get("runtime_payload_forbidden", []))
        if not {"raw_traj_data", "expert_future_actions", "planner_state", "evaluation_trajectory"}.issubset(forbidden):
            errors.append("skillbank_contract must forbid raw or privileged expert payloads at runtime")

    isolation = config.get("contamination_isolation")
    if not isinstance(isolation, dict) or isolation.get("phase0_to_phase6_status") != "frozen-read-only":
        errors.append("contamination_isolation.phase0_to_phase6_status must be frozen-read-only")
    elif isolation.get("required_audit") != "zero_phase0_to_phase6_dependency":
        errors.append("contamination_isolation.required_audit must prove zero Phase 0-6 dependency")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    errors = validate_config(load_config(args.config))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("VALID: TraceGraph TG1 is a zero-network ALFWorld training-split SkillBank preflight only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())