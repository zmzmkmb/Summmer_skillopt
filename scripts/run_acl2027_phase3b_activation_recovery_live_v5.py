#!/usr/bin/env python3
"""Authorization-gated execution of the frozen Phase 3B v4 recovery schedule."""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/run_acl2027_phase3b_activation_live_v3.py"
spec = importlib.util.spec_from_file_location("_phase3b_recovery_v5_base", BASE_PATH)
if spec is None or spec.loader is None: raise RuntimeError("cannot load v3 runner base")
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

VERSION, CALLS = 5, 175
STAGE_CEILING, CUMULATIVE_CEILING, PRIOR_KNOWN_COST = 2.0, 10.0, 7.835778
AUTH_ID = "phase3b-activation-recovery-live-v5"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
PAYLOAD_CLASSES = ["frozen_task_prompts", "historical_skill_context"]
RECEIPT = ROOT / "configs/acl2027/phase3b_activation_recovery_user_authorization_receipt_v5.json"
PREFLIGHT = ROOT / "artifacts/acl2027_phase3b_activation_recovery_preflight_v4"
MANIFEST, SCHEDULE = PREFLIGHT / "run_manifest.json", PREFLIGHT / "recovery_schedule.json"
GOLD, ANALYSIS_PLAN = PREFLIGHT / "recovery_private_gold.json", PREFLIGHT / "analysis_plan.json"
REUSABLE = PREFLIGHT / "reusable_v3_prefix.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ANALYZER = ROOT / "scripts/analyze_acl2027_phase3b_activation_recovery_live_v5.py"
TEST = ROOT / "tests/test_acl2027_phase3b_activation_recovery_live_v5.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3b_activation_recovery_live_v5"
PREFLIGHT_AUDIT, REGISTRY = ARTIFACT / "zero_network_preflight.json", ARTIFACT / "authorization_registry.json"
AUTH, AUTH_CLOSED = ARTIFACT / "authorization_open.json", ARTIFACT / "authorization_closed.json"
LEDGER, PACING = ARTIFACT / "ledger.json", ARTIFACT / "request_start_ledger.json"
RUN_AUDIT, CLOSURE = ARTIFACT / "run_audit.json", ARTIFACT / "authorization_closure.json"

for name, value in {
    "VERSION": VERSION, "CALLS": CALLS, "STAGE_CEILING": STAGE_CEILING, "CUMULATIVE_CEILING": CUMULATIVE_CEILING, "PRIOR_KNOWN_COST": PRIOR_KNOWN_COST,
    "AUTH_ID": AUTH_ID, "RECEIPT": RECEIPT, "PREFLIGHT": PREFLIGHT, "MANIFEST": MANIFEST, "SCHEDULE": SCHEDULE, "GOLD": GOLD, "ANALYSIS_PLAN": ANALYSIS_PLAN,
    "ADAPTER": ADAPTER, "ANALYZER": ANALYZER, "TEST": TEST, "ARTIFACT": ARTIFACT, "PREFLIGHT_AUDIT": PREFLIGHT_AUDIT, "REGISTRY": REGISTRY,
    "AUTH": AUTH, "AUTH_CLOSED": AUTH_CLOSED, "LEDGER": LEDGER, "PACING": PACING, "RUN_AUDIT": RUN_AUDIT, "CLOSURE": CLOSURE,
}.items(): setattr(base, name, value)

load, write = base.load, base.write
HardStop, QwenTokenPlanProviderAdapter = base.HardStop, base.QwenTokenPlanProviderAdapter


def exact_contract() -> dict[str, Any]:
    return {"scope":"phase3b_activation_recovery_only","authorized_stage":"activation_pilot","authorized_calls":CALLS,"max_provider_attempts":CALLS,"model_id":"qwen3.7-plus","temperature":0,"retries":0,"max_tokens_present":False,"enable_thinking":False,"response_format":{"type":"json_object"},"stage_cost_ceiling_cny":STAGE_CEILING,"cumulative_cost_ceiling_cny":CUMULATIVE_CEILING,"known_cumulative_cost_lower_bound_cny":PRIOR_KNOWN_COST,"later_stages_authorized":False,"formal_scaling_authorized":False}


def preflight() -> dict[str, Any]:
    manifest, rows, receipt = load(MANIFEST), load(SCHEDULE)["schedule"], load(RECEIPT)
    fingerprint = "f0c8170626d43cd97c854399b1c0b8194341b9a4034f2aba4b979d39b125cf36"
    if manifest.get("aggregate_fingerprint") != fingerprint or manifest.get("status") != "recovery-preflight-passed-closed" or manifest.get("recovery_calls") != CALLS: raise HardStop("Phase 3B v4 recovery manifest boundary drift")
    if manifest.get("spent_request_hash_overlap") != 0 or manifest.get("spent_logical_call_overlap") != 0 or manifest.get("combined_rows") != 300: raise HardStop("Phase 3B v4 recovery identity drift")
    if receipt.get("status") != "explicit_user_authorization_received_execution_not_open" or receipt.get("recovery_aggregate_fingerprint") != fingerprint or any(receipt.get(k) != v for k,v in exact_contract().items()): raise HardStop("Phase 3B v5 receipt boundary drift")
    if receipt.get("data_egress_authorized") is not True or receipt.get("authorized_destination") != ENDPOINT or receipt.get("authorized_payload_classes") != PAYLOAD_CLASSES or receipt.get("paid_usage_authorized") is not True: raise HardStop("Phase 3B v5 data-egress authorization drift")
    expected = {"recovery_manifest_sha256": base.sha256_file(MANIFEST), "recovery_schedule_sha256": base.sha256_file(SCHEDULE), "recovery_gold_sha256": base.sha256_file(GOLD), "reusable_v3_prefix_sha256": base.sha256_file(REUSABLE), "analysis_plan_sha256": base.sha256_file(ANALYSIS_PLAN)}
    if receipt.get("bindings") != expected: raise HardStop("Phase 3B v5 receipt binding drift")
    if any(receipt.get("execution", {}).get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")): raise HardStop("Phase 3B v5 receipt is not execution-closed")
    if len(rows) != CALLS or len({r["logical_call_id"] for r in rows}) != CALLS or len({r["request_hash"] for r in rows}) != CALLS: raise HardStop("Phase 3B v5 schedule identity drift")
    for index,row in enumerate(rows,1):
        body=row["canonical_request_body"]
        if row.get("staged_execution_index") != index or row["request_hash"] != base.stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type":"json_object"} or body.get("enable_thinking") is not False: raise HardStop("Phase 3B v5 route drift")
    bindings = {"receipt_sha256": base.sha256_file(RECEIPT), **expected, "provider_adapter_sha256": base.sha256_file(ADAPTER), "analyzer_sha256": base.sha256_file(ANALYZER), "test_sha256": base.sha256_file(TEST), "live_runner_sha256": base.sha256_file(Path(__file__).resolve())}
    return {"schema_version":VERSION,"status":"zero-network-preflight-passed","recovery_aggregate_fingerprint":fingerprint,"authorized_calls":CALLS,"max_provider_attempts":CALLS,"stage_cost_ceiling_cny":STAGE_CEILING,"cumulative_cost_ceiling_cny":CUMULATIVE_CEILING,"known_cumulative_cost_lower_bound_cny":PRIOR_KNOWN_COST,"bindings":bindings,"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0,"authorization_opened":False,"data_egress_authorized":True,"authorized_destination":ENDPOINT,"authorized_payload_classes":PAYLOAD_CLASSES,"later_stages_authorized":False,"formal_scaling_authorized":False}


def authorization_template(key: str) -> dict[str, Any]:
    gate=preflight()
    return {"schema_version":VERSION,"experiment":"acl2027_phase3b_activation_recovery_live_v5","authorization_id":AUTH_ID,"status":"open","bindings":{**gate["bindings"],"zero_network_preflight_aggregate_fingerprint":base.stable(gate)},"credential_sha256":hashlib.sha256(key.encode()).hexdigest(),**exact_contract(),"endpoint":ENDPOINT,"request_interval_seconds":1.0,"data_egress_authorized":True,"authorized_payload_classes":PAYLOAD_CLASSES,"paid_usage_authorized":True,"paid_api_allowed":True,"provider_calls_allowed":True,"qwen_authorization_open":True,"formal_scaling_allowed":False,"forbidden_stages":load(RECEIPT)["forbidden_stages"]}


base.preflight, base.authorization_template, base.exact_contract = preflight, authorization_template, exact_contract
open_authorization, validate_authorization, execute, audit, close = base.open_authorization, base.validate_authorization, base.execute, base.audit, base.close


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("preflight","authorize","execute","audit","close")); args=parser.parse_args()
    if args.command=="preflight": result=preflight(); write(PREFLIGHT_AUDIT,result)
    elif args.command=="authorize": result=open_authorization()
    elif args.command=="audit": result=audit()
    elif args.command=="close": result=close("operator_close")
    else:
        try: result={"rows":len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))),"closure":close("completed_exact_175")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists(): close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result,indent=2,sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
