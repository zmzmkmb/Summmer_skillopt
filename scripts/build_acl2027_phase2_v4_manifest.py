#!/usr/bin/env python3
"""Build the v4 manifest entirely from current on-disk bytes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_HINT = Path(__file__).resolve().parents[1]
if str(ROOT_HINT) not in sys.path:
    sys.path.insert(0, str(ROOT_HINT))

from scripts.acl2027_phase2_integrity_v4 import ROOT, sha256_file, stable

OUTPUT = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
BINDING_PATHS = {
    "runner_source": "scripts/run_acl2027_phase2_staged_live_runner_preflight_v4.py",
    "integrity_source": "scripts/acl2027_phase2_integrity_v4.py",
    "manifest_builder_source": "scripts/build_acl2027_phase2_v4_manifest.py",
    "provider_adapter_source": "scripts/acl2027_phase2_provider_adapter_v3.py",
    "materializer_source": "scripts/materialize_acl2027_phase2_candidates_v3.py",
    "verifier_source": "scripts/acl2027_phase2_response_verifier_v3.py",
    "probe_analyzer_source": "scripts/analyze_acl2027_phase2_probe_v3.py",
    "test_source": "tests/test_acl2027_phase2_staged_live_runner_preflight_v4.py",
    "candidate_schema": "configs/acl2027/phase2_candidate_materialization_schema_v3.json",
    "probe_schema": "configs/acl2027/phase2_probe_audit_schema_v3.json",
    "freeze_config": "configs/acl2027/phase2_expansion_freeze_v2.json",
    "request_plan": "artifacts/acl2027_phase2_expansion_freeze_v2/request_plan.json",
    "partition_audit": "artifacts/acl2027_phase2_expansion_freeze_v2/partition_audit.json",
    "staged_schedule": "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json",
    "formal_history_gold": "data/searchqa_phase2_verified/formal_history.json",
    "probe_gold": "data/searchqa_phase2_verified/probe.json",
}


def build_manifest(*, root: Path = ROOT) -> dict:
    bindings = {name: {"path": relative, "sha256": sha256_file(root / relative)} for name, relative in BINDING_PATHS.items()}
    payload = {
        "schema_version": 4,
        "artifact": "acl2027_phase2_staged_live_runner_preflight_v4",
        "status": "immutable_preflight_passed_authorization_closed",
        "binding_model": "disk_manifest_rooted_by_config_and_explicit_authorization",
        "bindings": bindings,
        "calls": {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0},
        "authorization_opened": False,
    }
    return {**payload, "aggregate_fingerprint": stable(payload)}


def main() -> int:
    manifest = build_manifest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(OUTPUT.relative_to(ROOT)), "bindings": len(manifest["bindings"]), "aggregate_fingerprint": manifest["aggregate_fingerprint"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
