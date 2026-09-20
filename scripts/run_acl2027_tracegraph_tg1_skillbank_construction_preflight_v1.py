#!/usr/bin/env python3
"""Validate the zero-network TG1 SkillBank construction protocol."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs" / "acl2027" / "tracegraph_tg1_skillbank_construction_v1.json"


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []
    if config.get("experiment_line") != "tracegraph-observable-state-skill-composition":
        errors.append("construction protocol must use the TraceGraph research line")
    if config.get("allowed_split") != "train" or config.get("source_root") != "ALFWORLD_DATA/json_2.1.1/train":
        errors.append("construction protocol must use ALFWORLD_DATA/json_2.1.1/train")
    if config.get("construction_enabled") is not False:
        errors.append("construction must remain disabled during the preflight")
    for field in ("network_calls_allowed", "provider_calls_allowed", "model_calls_allowed", "authorization_receipts_allowed"):
        if config.get(field) is not False:
            errors.append(f"{field} must be false")
    if config.get("runtime_allowed_inputs") != ["observation", "historical_actions", "admissible_actions"]:
        errors.append("runtime inputs must be observable-state only")
    forbidden = set(config.get("runtime_forbidden_fields", []))
    required_forbidden = {"raw_traj_data", "planner_state", "pddl_params", "expert_future_actions", "phase0_to_phase6_artifact"}
    if not required_forbidden.issubset(forbidden):
        errors.append("runtime forbidden fields are incomplete")
    required = {"skill_id", "trajectory_id", "source_split", "gamefile_sha256", "traj_data_sha256", "task_type", "span_start", "span_end", "canonical_actions", "construction_protocol_fingerprint"}
    if not required.issubset(set(config.get("required_record_fields", []))):
        errors.append("required record fields are incomplete")
    return errors


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("VALID: TG1 SkillBank construction protocol is frozen and zero-network; construction remains disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
