#!/usr/bin/env python3
"""Zero-network route preflight for Phase 2 Token Plan calibration v6."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase2_token_plan_route_preflight_v6.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
V5_LEDGER = ROOT / "artifacts/acl2027_phase2_calibration_live_v5/ledger.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_token_plan_route_preflight_v6"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v6.py"
RUNNER = ROOT / "scripts/run_acl2027_phase2_calibration_token_plan_v6.py"
ROUTE_TEST = ROOT / "tests/test_acl2027_phase2_token_plan_route_preflight_v6.py"
RUNNER_TEST = ROOT / "tests/test_acl2027_phase2_calibration_token_plan_v6.py"


class PreflightError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def validate_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load(CONFIG)
    if config.get("status") != "preflight_only_closed":
        raise PreflightError("route preflight status drift")
    if any(config["execution"].get(key) is not False for key in (
        "network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed"
    )):
        raise PreflightError("route preflight execution switch drift")
    route = config["token_plan_route"]
    expected = {
        "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "model_id": "qwen3.7-plus",
        "temperature": 0,
        "enable_thinking": False,
        "request_interval_seconds": 1.0,
        "retries": 0,
        "timeout_seconds": 120,
        "forbidden_request_keys": ["max_tokens"],
    }
    if route != expected:
        raise PreflightError("Token Plan route drift")
    if load(V4_MANIFEST)["aggregate_fingerprint"] != config["parent_v4"]["aggregate_fingerprint"]:
        raise PreflightError("v4 aggregate binding drift")
    if sha256_file(V5_LEDGER) != config["preserved_v5"]["ledger_sha256"]:
        raise PreflightError("v5 terminal ledger drift")
    boundary = config["future_calibration_boundary"]
    if boundary["logical_calls"] != 60 or boundary["max_provider_attempts"] != 60:
        raise PreflightError("future calibration call boundary drift")
    if boundary["stage_cost_ceiling_cny"] != 0.5 or boundary["cumulative_cost_ceiling_cny"] != 0.5:
        raise PreflightError("future calibration cost boundary drift")
    if set(boundary["forbidden_stages"]) != {"development_acquisition", "formal_history", "probe", "held_out", "formal_scaling"}:
        raise PreflightError("future calibration scope drift")
    return config


def build_manifest() -> dict[str, Any]:
    config = validate_config()
    return {
        "schema_version": 6,
        "status": "preflight-passed-closed",
        "config_sha256": sha256_file(CONFIG),
        "adapter_sha256": sha256_file(ADAPTER),
        "runner_sha256": sha256_file(RUNNER),
        "route_test_sha256": sha256_file(ROUTE_TEST),
        "runner_test_sha256": sha256_file(RUNNER_TEST),
        "v4_aggregate_fingerprint": config["parent_v4"]["aggregate_fingerprint"],
        "v5_ledger_sha256": sha256_file(V5_LEDGER),
        "route": config["token_plan_route"],
        "future_calibration_boundary": config["future_calibration_boundary"],
        "counters": {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    if args.write_artifact:
        write_json(ARTIFACT / "run_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
