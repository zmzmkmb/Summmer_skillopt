#!/usr/bin/env python3
"""Zero-network Phase 2 v14 probe-only preflight."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_integrity_v4 import verify_integrity
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase2_probe_only_preflight_v14.json"
AUTH_CLOSED = ROOT / "configs/acl2027/phase2_probe_only_authorization_closed_v14.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
CANDIDATE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/combined_candidates_v13.json"
V13_MANIFEST = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/run_manifest.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_only_preflight_v14"


class HardStop(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    v4 = load(V4_CONFIG)
    if any(cfg["execution"].get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v14 preflight execution switches must be closed")
    if cfg["stage"] != {
        "authorized_stage": "probe", "authorized_calls": 160, "stage_call_ceiling": 160,
        "stage_cost_ceiling_cny": 7.5, "cumulative_cost_ceiling_cny": 7.5,
        "retries": 0, "max_tokens_present": False, "temperature": 0,
        "model_id": "qwen3.7-plus", "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "request_interval_seconds": 1.0,
    }:
        raise HardStop("v14 stage authorization contract drift")
    if v4["integrity_root"]["expected_aggregate_fingerprint"] != cfg["bindings"]["v4_aggregate_fingerprint"]:
        raise HardStop("v4 aggregate fingerprint drift")
    verify_integrity(V4_CONFIG, V4_MANIFEST, root=ROOT)
    if sha256_file(SCHEDULE) != cfg["bindings"]["v4_schedule_sha256"]:
        raise HardStop("probe schedule hash drift")
    if sha256_file(CANDIDATE) != cfg["bindings"]["v13_candidate_sha256"]:
        raise HardStop("v13 candidate hash drift")
    v13 = load(V13_MANIFEST)
    if v13.get("aggregate_fingerprint") != cfg["bindings"]["v13_aggregate_fingerprint"] or v13.get("status") != "preflight-passed-correction":
        raise HardStop("v13 manifest acceptance drift")
    candidate = load(CANDIDATE)
    if candidate.get("coverage_status") != "coverage-passed" or candidate.get("passed") is not True or candidate.get("history_rows") != 160:
        raise HardStop("formal-history coverage gate not passed")
    rows = load(SCHEDULE)["schedule"]
    probe = [row for row in rows if row.get("partition") == "probe"]
    if len(probe) != 160 or len({row["logical_call_id"] for row in probe}) != 160 or len({row["request_hash"] for row in probe}) != 160:
        raise HardStop("probe schedule is not an exact unique 160-row plan")
    if [row["staged_execution_index"] for row in probe] != list(range(231, 391)):
        raise HardStop("probe schedule is not the frozen exact prefix")
    if any("max_tokens" in row["canonical_request_body"] or row["canonical_request_body"].get("model_id") != "qwen3.7-plus" or row["canonical_request_body"].get("temperature") != 0 for row in probe):
        raise HardStop("probe request contract drift")
    closed = load(AUTH_CLOSED)
    if closed.get("status") != "closed_preflight" or closed.get("authorized_stage") is not None or any(closed.get(k) is not False for k in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("closed authorization drift")
    expected_closed_bindings = {
        "preflight_config_sha256": sha256_file(CONFIG),
        "v4_aggregate_fingerprint": cfg["bindings"]["v4_aggregate_fingerprint"],
        "v13_aggregate_fingerprint": cfg["bindings"]["v13_aggregate_fingerprint"],
        "schedule_sha256": sha256_file(SCHEDULE),
        "candidate_sha256": sha256_file(CANDIDATE),
    }
    if closed.get("bindings") != expected_closed_bindings:
        raise HardStop("closed authorization binding drift")
    return {"status": "preflight-passed-closed", "probe_calls": 160, "coverage_status": candidate["coverage_status"], "v4_aggregate_fingerprint": cfg["bindings"]["v4_aggregate_fingerprint"], "v13_aggregate_fingerprint": cfg["bindings"]["v13_aggregate_fingerprint"], "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0, "aggregate_fingerprint": stable({"config": cfg, "v4_manifest": load(V4_MANIFEST), "v13_manifest": v13, "candidate_sha256": sha256_file(CANDIDATE), "probe_schedule_sha256": sha256_file(SCHEDULE)})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        ARTIFACT.mkdir(parents=True, exist_ok=False)
        manifest = {**result, "schema_version": 14, "experiment": "acl2027_phase2_probe_only_preflight_v14", "bindings": {"config_sha256": sha256_file(CONFIG), "closed_authorization_sha256": sha256_file(AUTH_CLOSED), "preflight_source_sha256": sha256_file(Path(__file__).resolve()), "live_runner_source_sha256": sha256_file(ROOT / "scripts/run_acl2027_phase2_probe_only_live_v14.py"), "preflight_test_sha256": sha256_file(ROOT / "tests/test_acl2027_phase2_probe_only_preflight_v14.py"), "live_test_sha256": sha256_file(ROOT / "tests/test_acl2027_phase2_probe_only_live_v14.py"), "schedule_sha256": sha256_file(SCHEDULE), "candidate_sha256": sha256_file(CANDIDATE)}}
        (ARTIFACT / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
