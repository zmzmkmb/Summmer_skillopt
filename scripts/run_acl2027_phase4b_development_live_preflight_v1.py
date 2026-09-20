"""Bind the Phase 4A development split to a closed live-execution proposal."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase4b_development_live_preflight_v1.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase4b_development_live_preflight_v1.py"
TEST = ROOT / "tests/test_acl2027_phase4b_development_live_preflight_v1.py"
SOURCE = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_development_live_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase4b_development_live_preflight_v1.md"
CONDITIONS = ("cold", "global_only", "contextual_typed", "shuffled_typed", "incompatible_control")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows() -> list[dict[str, Any]]:
    values = load(SOURCE / "design_schedule.json")["rows"]
    return [row for row in values if row["split"] == "development"]


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load(CONFIG)
    source = load(SOURCE / "run_manifest.json")
    if source["aggregate_fingerprint"] != cfg["source_design_fingerprint"]:
        raise RuntimeError("Phase 4A fingerprint drift")
    if any(cfg["execution"].values()):
        raise RuntimeError("Phase 4B preflight must remain closed")
    selected = rows()
    ids = [row["logical_call_id"] for row in selected]
    hashes = [row["request_hash"] for row in selected]
    if len(selected) != 100 or len(set(ids)) != 100 or len(set(hashes)) != 100:
        raise RuntimeError("Phase 4B development schedule identity drift")
    if Counter(row["condition"] for row in selected) != Counter({condition: 20 for condition in CONDITIONS}):
        raise RuntimeError("Phase 4B condition balance drift")
    for row in selected:
        body = row["canonical_request_body"]
        if stable(body) != row["request_hash"] or body["model_id"] != "qwen3.7-plus" or body["temperature"] != 0 or body["enable_thinking"] is not False or body["response_format"] != {"type": "json_object"} or "max_tokens" in body:
            raise RuntimeError("Phase 4B payload contract drift")
    contract = cfg["execution_contract"]
    result = {"schema_version": 1, "experiment": cfg["experiment"], "status": "live-execution-preflight-passed-closed", "authorization_status": "fresh-exact-explicit-user-authorization-required", "source_design_fingerprint": source["aggregate_fingerprint"], "schedule_audit": {"rows": 100, "tasks": len({row["task_id"] for row in selected}), "condition_counts": dict(Counter(row["condition"] for row in selected)), "schedule_sha256": stable(selected)}, "execution_contract": contract, "bindings": {"config_sha256": sha256_file(CONFIG), "script_sha256": sha256_file(SCRIPT), "test_sha256": sha256_file(TEST), "source_manifest_sha256": sha256_file(SOURCE / "run_manifest.json"), "source_schedule_sha256": sha256_file(SOURCE / "design_schedule.json")}, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "formal_scaling_calls": 0}
    result["aggregate_fingerprint"] = stable(result)
    request = {"schema_version": 1, "status": "awaiting_exact_explicit_user_authorization", "phase4a_design_fingerprint": source["aggregate_fingerprint"], "phase4b_live_preflight_fingerprint": result["aggregate_fingerprint"], "execution_contract": contract, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    return result, request


def write_artifact(result: dict[str, Any], request: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    selected = rows()
    for name, value in {"development_schedule.json": {"rows": selected}, "authorization_request.json": request, "run_manifest.json": result, "completion_manifest.json": {"schema_version": 1, "experiment": result["experiment"], "status": "complete", "completion_kind": "zero_network_live_execution_preflight", "proposed_calls": 100, "completed_calls": 100, "rows": 100, "provider_calls_executed": 0, "authorization_status": result["authorization_status"], "aggregate_fingerprint": result["aggregate_fingerprint"]}}.items():
        (ARTIFACT / name).write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(f"# Phase 4B development live-execution preflight\n\nFrozen 100 Phase 4A development-split rows, 20 per condition, for qwen3.7-plus at the Token Plan Beijing endpoint. The contract fixes temperature 0, disabled thinking, zero retries, absent `max_tokens`, JSON-object responses, one-second pacing, CNY 2.00 stage ceiling, CNY 15.00 cumulative ceiling, terminal first-failure stop, exact-prefix resume, and automatic closure. No network, provider, model, or paid call occurred.\n\nPreflight fingerprint: `{result['aggregate_fingerprint']}`.\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write-artifact", action="store_true"); args = parser.parse_args()
    result, request = validate()
    if args.write_artifact: write_artifact(result, request)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
