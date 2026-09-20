#!/usr/bin/env python3
"""Zero-network v13 correction preflight for the closed v12 recovery ledger."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.materialize_acl2027_phase2_candidates_recovery_v13 import build_recovery_candidate_artifact, load, sha256_file

CONFIG = ROOT / "configs/acl2027/phase2_formal_history_recovery_preflight_v13.json"
V12_CONFIG = ROOT / "configs/acl2027/phase2_formal_history_recovery_preflight_v12.json"
V12_MANIFEST = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v12/run_manifest.json"
V12_LEDGER = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_live_v12/ledger.json"
V11_LEDGER = ROOT / "artifacts/acl2027_phase2_formal_history_v11/ledger.json"
COMBINED_SCHEDULE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v12/combined_formal_history_schedule.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13"
CANDIDATES = ARTIFACT / "combined_candidates_v13.json"
MANIFEST = ARTIFACT / "run_manifest.json"
REPORT = ROOT / "paper/acl2027/results/phase2_formal_history_recovery_preflight_v13.md"


def stable(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_inputs() -> dict[str, Any]:
    config = load(CONFIG)
    v12_config = load(V12_CONFIG)
    v12_manifest = load(V12_MANIFEST)
    if v12_manifest.get("aggregate_fingerprint") != config["bindings"]["v12_aggregate_fingerprint"]:
        raise RuntimeError("v12 aggregate fingerprint drift")
    if sha256_file(V12_CONFIG) != config["bindings"]["v12_config_sha256"]:
        raise RuntimeError("v12 config hash drift")
    for path_key, path in (("v12_manifest_sha256", V12_MANIFEST), ("v12_ledger_sha256", V12_LEDGER), ("v11_ledger_sha256", V11_LEDGER), ("combined_schedule_sha256", COMBINED_SCHEDULE)):
        if sha256_file(path) != config["bindings"][path_key]:
            raise RuntimeError(f"{path_key} drift")
    if v12_manifest.get("status") != "preflight-passed-authorization-closed":
        raise RuntimeError("v12 preflight is not closed")
    if load(ROOT / "artifacts/acl2027_phase2_formal_history_recovery_live_v12/authorization_registry.json").get("authorizations"):
        raise RuntimeError("v12 authorization registry is not closed")
    return {"schema_version": 13, "status": "inputs-bound-zero-network", "v12_aggregate_fingerprint": v12_manifest["aggregate_fingerprint"], "counters": {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0}}


def execute() -> dict[str, Any]:
    preflight = validate_inputs()
    config = load(CONFIG)
    preserved = [row for row in load(V11_LEDGER) if row.get("status") == "completed"]
    recovery = load(V12_LEDGER)
    schedule = load(COMBINED_SCHEDULE)["schedule"]
    candidate = build_recovery_candidate_artifact(preserved, recovery, schedule, config, root=ROOT)
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    write(CANDIDATES, candidate)
    manifest = {**preflight, "experiment": "acl2027_phase2_formal_history_recovery_preflight_v13", "status": "preflight-passed-correction", "candidate_sha256": sha256_file(CANDIDATES), "candidate": {"history_rows": candidate["history_rows"], "coverage_status": candidate["coverage_status"], "passed": candidate["passed"], "independent_verified_supports": candidate["independent_verified_supports"]}, "bindings": config["bindings"], "aggregate_fingerprint": stable({"config": sha256_file(CONFIG), "v12_manifest": sha256_file(V12_MANIFEST), "candidate": sha256_file(CANDIDATES), "schedule": sha256_file(COMBINED_SCHEDULE)})}
    write(MANIFEST, manifest)
    REPORT.write_text("# Phase 2 Formal History Recovery Preflight v13\n\nZero-network correction replay allows identical answer text across distinct tasks while enforcing unique logical requests, request hashes, provider response IDs, frozen task bindings, and private-gold leakage boundaries.\n\n" + json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2, sort_keys=True))
