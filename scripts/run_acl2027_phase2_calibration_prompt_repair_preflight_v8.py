#!/usr/bin/env python3
"""Build the closed zero-network Phase 2 v8 exact-JSON calibration preflight."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import load, sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase2_calibration_prompt_repair_preflight_v8.json"
SOURCE_SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
V6_MANIFEST = ROOT / "artifacts/acl2027_phase2_token_plan_route_preflight_v6/run_manifest.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_calibration_prompt_repair_preflight_v8"
SCHEDULE = ARTIFACT / "calibration_schedule.json"
MANIFEST = ARTIFACT / "run_manifest.json"
SOURCE_FILES = {
    "builder_sha256": ROOT / "scripts/run_acl2027_phase2_calibration_prompt_repair_preflight_v8.py",
    "adapter_sha256": ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py",
    "runner_sha256": ROOT / "scripts/run_acl2027_phase2_calibration_token_plan_v8.py",
    "live_orchestrator_sha256": ROOT / "scripts/run_acl2027_phase2_calibration_token_plan_live_v8.py",
    "audit_sha256": ROOT / "scripts/audit_acl2027_phase2_calibration_v8.py",
    "test_sha256": ROOT / "tests/test_acl2027_phase2_calibration_v8.py",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def validate_config() -> dict[str, Any]:
    config = load(CONFIG)
    if config.get("status") != "preflight_only_closed" or any(config["execution"].values()):
        raise RuntimeError("v8 preflight execution boundary drift")
    route = config["route"]
    exact_route = {
        "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "model_id": "qwen3.7-plus",
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "retries": 0,
        "timeout_seconds": 120,
        "forbidden_request_keys": ["max_tokens"],
    }
    if route != exact_route:
        raise RuntimeError("v8 route drift")
    contract = config["prompt_contract"]
    if contract["version"] != "phase2-prompt-v8-exact-json" or '{"answer":"<short answer>"}' not in contract["system_message"]:
        raise RuntimeError("v8 prompt contract drift")
    if config["diagnosed_v7"]["ledger_sha256"] != sha256_file(ROOT / config["diagnosed_v7"]["ledger_path"]):
        raise RuntimeError("v7 ledger binding drift")
    if config["diagnosed_v7"]["audit_sha256"] != sha256_file(ROOT / config["diagnosed_v7"]["audit_path"]):
        raise RuntimeError("v7 audit binding drift")
    return config


def build_schedule() -> list[dict[str, Any]]:
    config = validate_config()
    source = load(SOURCE_SCHEDULE)["schedule"][:60]
    repaired = []
    for index, original in enumerate(source, start=1):
        row = deepcopy(original)
        body = row["canonical_request_body"]
        body["messages"][0]["content"] = config["prompt_contract"]["system_message"]
        body["prompt_template_version"] = config["prompt_contract"]["version"]
        body["candidate_version"] = "phase2-v8-prompt-repair"
        body["response_format"] = deepcopy(config["route"]["response_format"])
        row["prompt_template_version"] = config["prompt_contract"]["version"]
        row["candidate_version"] = "phase2-v8-prompt-repair"
        row["logical_call_id"] = "phase2-v8:" + row["logical_call_id"].split(":", 1)[1]
        row["request_hash"] = stable(body)
        row["original_call_index"] = index
        row["staged_execution_index"] = index
        repaired.append(row)
    if len(repaired) != 60 or len({row["logical_call_id"] for row in repaired}) != 60:
        raise RuntimeError("v8 schedule identity drift")
    if len({row["request_hash"] for row in repaired}) != 60:
        raise RuntimeError("v8 request hash collision")
    return repaired


def build_manifest() -> dict[str, Any]:
    if not SCHEDULE.exists():
        raise RuntimeError("v8 schedule missing")
    manifest = {
        "schema_version": 8,
        "status": "preflight-passed-closed",
        "config_sha256": sha256_file(CONFIG),
        "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE),
        "v6_route_manifest_sha256": sha256_file(V6_MANIFEST),
        "schedule_sha256": sha256_file(SCHEDULE),
        "logical_calls": 60,
        "prompt_contract_version": "phase2-prompt-v8-exact-json",
        "response_format": {"type": "json_object"},
        "counters": {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0},
    }
    manifest.update({key: sha256_file(path) for key, path in SOURCE_FILES.items()})
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    schedule = build_schedule()
    if args.write_artifact:
        write_json(SCHEDULE, {"schema_version": 8, "schedule": schedule})
        write_json(MANIFEST, build_manifest())
    result = {"status": "preflight-passed-closed", "logical_calls": len(schedule), "network_calls": 0, "provider_calls": 0}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
