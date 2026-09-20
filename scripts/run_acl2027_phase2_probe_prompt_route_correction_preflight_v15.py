#!/usr/bin/env python3
"""Zero-network diagnosis of the v14 probe HTTP-400 contract mismatch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase2_probe_prompt_route_correction_preflight_v15.json"
V14_SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
V14_LEDGER = ROOT / "artifacts/acl2027_phase2_probe_only_live_v14/ledger.json"
V8_SCHEDULE = ROOT / "artifacts/acl2027_phase2_calibration_prompt_repair_preflight_v8/calibration_schedule.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_prompt_route_correction_preflight_v15"


class HardStop(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(cfg["execution"].get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v15 execution switches must remain closed")
    rows = load(V14_SCHEDULE)["schedule"]
    probe = [r for r in rows if r.get("partition") == "probe"]
    ledger = load(V14_LEDGER)
    if len(probe) != 160 or len(ledger) != 1 or ledger[0].get("terminal") is not True:
        raise HardStop("v14 terminal provenance drift")
    spent = ledger[0]["logical_call_id"]
    if spent != probe[0]["logical_call_id"] or cfg["diagnostic"]["spent_v14_logical_request_excluded"] is not True:
        raise HardStop("spent v14 request exclusion drift")
    system_prompts = [r["canonical_request_body"]["messages"][0]["content"] for r in probe]
    if any("JSON object" in prompt or "json_object" in prompt for prompt in system_prompts):
        raise HardStop("unexpected JSON-repaired probe prompt in frozen schedule")
    v8 = load(V8_SCHEDULE)["schedule"]
    v8_prompt = v8[0]["canonical_request_body"]["messages"][0]["content"]
    if "exactly one JSON object" not in v8_prompt or '{"answer":"<short answer>"}' not in v8_prompt:
        raise HardStop("v8 repaired JSON contract binding drift")
    adapter_text = ADAPTER.read_text(encoding="utf-8")
    if '"response_format": {"type": "json_object"}' not in adapter_text or '"enable_thinking": False' not in adapter_text:
        raise HardStop("provider adapter JSON route binding drift")
    if sha256_file(V14_SCHEDULE) != cfg["bindings"]["v14_schedule_sha256"] or sha256_file(V14_LEDGER) != cfg["bindings"]["v14_ledger_sha256"] or sha256_file(V8_SCHEDULE) != cfg["bindings"]["v8_calibration_schedule_sha256"] or sha256_file(ADAPTER) != cfg["bindings"]["provider_adapter_sha256"]:
        raise HardStop("v15 source hash binding drift")
    return {"schema_version": 15, "status": "correction-required", "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0, "spent_v14_logical_call_id": spent, "frozen_probe_rows": 160, "excluded_spent_rows": 1, "v8_json_contract_verified": True, "adapter_json_route_verified": True, "fresh_authorization_required": True, "held_out_authorized": False, "formal_scaling_authorized": False, "aggregate_fingerprint": stable({"config": cfg, "v14_schedule_sha256": sha256_file(V14_SCHEDULE), "v14_ledger_sha256": sha256_file(V14_LEDGER), "v8_schedule_sha256": sha256_file(V8_SCHEDULE), "adapter_sha256": sha256_file(ADAPTER)})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        ARTIFACT.mkdir(parents=True, exist_ok=False)
        (ARTIFACT / "run_manifest.json").write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
