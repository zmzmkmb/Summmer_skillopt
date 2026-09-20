#!/usr/bin/env python3
"""Validate the enabled, zero-network TG1 SkillBank construction preflight."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs/acl2027/tracegraph_tg1_skillbank_construction_preflight_v2.json"
MANIFEST = ROOT / "artifacts/acl2027_tracegraph_tg1_skillbank_preflight_v1/skillbank_source_manifest.json"

def validate(config: dict, manifest: dict) -> list[str]:
    errors=[]
    if config.get("experiment_line") != "tracegraph-observable-state-skill-composition": errors.append("wrong experiment line")
    if config.get("source_manifest_sha256") != hashlib.sha256(MANIFEST.read_bytes()).hexdigest(): errors.append("source manifest fingerprint mismatch")
    if manifest.get("source_split") != "train" or manifest.get("trajectory_count") != 3553: errors.append("unexpected train manifest")
    for k in ("network_calls_allowed","provider_calls_allowed","model_calls_allowed","authorization_receipts_allowed"):
        if config.get(k) is not False: errors.append(f"{k} must be false")
    if config.get("construction_enabled") is not True: errors.append("construction must be explicitly enabled for this preflight")
    if config.get("runtime_allowed_inputs") != ["observation","historical_actions","admissible_actions"]: errors.append("runtime inputs are not observable-only")
    forbidden=set(config.get("runtime_forbidden_fields",[]))
    if not {"raw_traj_data","planner_state","pddl_params","expert_future_actions","phase0_to_phase6_artifact"}.issubset(forbidden): errors.append("runtime forbidden fields incomplete")
    return errors

def main():
    config=json.loads(CONFIG.read_text(encoding="utf-8")); manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors=validate(config,manifest)
    if errors:
        for e in errors: print("ERROR:",e)
        return 1
    print("VALID: enabled TG1 SkillBank construction preflight; source manifest bound; zero network/provider/model/API calls.")
    return 0
if __name__ == "__main__": raise SystemExit(main())
