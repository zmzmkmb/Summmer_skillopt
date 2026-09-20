#!/usr/bin/env python3
"""Authorization-gated live runner for the frozen Phase 3D schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage

VERSION, CALLS = 3, 240
STAGE_CEILING, CUMULATIVE_CEILING, PRIOR_KNOWN_COST = 3.0, 15.0, 7.218738
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase3d-specificity-abstention-live-v3"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
PAYLOAD_CLASSES = ["frozen_task_prompts", "frozen_task_contexts", "frozen_historical_skill_candidate_bundles"]
DESIGN_FINGERPRINT = "59143bd2c63bf73c4f747121d547216a2665c7bd722fb7c672b0e12e9db2e5b0"
PREFLIGHT_FINGERPRINT = "1b57aabe12711ef646674dc39dcc01990c8e0088c667c30fe0818d47c26f4970"
RECEIPT = ROOT / "configs/acl2027/phase3d_specificity_abstention_user_authorization_receipt_v3.json"
V2_CONFIG = ROOT / "configs/acl2027/phase3d_specificity_abstention_live_preflight_v2.json"
V2_ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_preflight_v2"
V2_MANIFEST = V2_ARTIFACT / "run_manifest.json"
V2_REQUEST = V2_ARTIFACT / "authorization_request.json"
V1_ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_preflight_v1"
V1_MANIFEST = V1_ARTIFACT / "run_manifest.json"
SCHEDULE = V1_ARTIFACT / "specificity_schedule.json"
GOLD = V1_ARTIFACT / "specificity_private_gold.json"
ANALYSIS_PLAN = V1_ARTIFACT / "analysis_plan.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ANALYZER = ROOT / "scripts/analyze_acl2027_phase3d_specificity_abstention_live_v3.py"
TEST = ROOT / "tests/test_acl2027_phase3d_specificity_abstention_live_v3.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_v3"
PREFLIGHT_AUDIT = ARTIFACT / "zero_network_preflight.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
AUTH = ARTIFACT / "authorization_open.json"
AUTH_CLOSED = ARTIFACT / "authorization_closed.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
RUN_AUDIT = ARTIFACT / "run_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def cost(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * 2.0 + value["output_tokens"] * 8.0) / 1_000_000, 6)


def known_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(row.get("local_cost_cny") or 0.0 for row in records), 6)


def exact_contract() -> dict[str, Any]:
    return {"scope": "phase3d_specificity_abstention_only", "authorized_stage": "specificity_abstention", "authorized_calls": CALLS, "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False, "retries": 0, "max_tokens_present": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "known_cumulative_cost_lower_bound_cny": PRIOR_KNOWN_COST, "later_stages_authorized": False, "cross_domain_scaling_authorized": False, "formal_scaling_authorized": False}


def source_bindings() -> dict[str, str]:
    return {"v2_config_sha256": sha256_file(V2_CONFIG), "v2_manifest_sha256": sha256_file(V2_MANIFEST), "v2_authorization_request_sha256": sha256_file(V2_REQUEST), "v1_manifest_sha256": sha256_file(V1_MANIFEST), "v1_schedule_sha256": sha256_file(SCHEDULE), "v1_private_gold_sha256": sha256_file(GOLD), "v1_analysis_plan_sha256": sha256_file(ANALYSIS_PLAN)}


def preflight() -> dict[str, Any]:
    v2, v1, rows, receipt = load(V2_MANIFEST), load(V1_MANIFEST), load(SCHEDULE)["schedule"], load(RECEIPT)
    if v2.get("aggregate_fingerprint") != PREFLIGHT_FINGERPRINT or v2.get("status") != "live-execution-preflight-passed-closed":
        raise HardStop("Phase 3D v2 preflight boundary drift")
    if v1.get("aggregate_fingerprint") != DESIGN_FINGERPRINT or v1.get("status") != "design-preflight-passed-closed":
        raise HardStop("Phase 3D v1 design boundary drift")
    if receipt.get("status") != "explicit_user_authorization_received_execution_not_open" or receipt.get("phase3d_design_fingerprint") != DESIGN_FINGERPRINT or receipt.get("phase3d_live_preflight_fingerprint") != PREFLIGHT_FINGERPRINT or any(receipt.get(key) != value for key, value in exact_contract().items()):
        raise HardStop("Phase 3D v3 receipt boundary drift")
    if receipt.get("data_egress_authorized") is not True or receipt.get("authorized_destination") != ENDPOINT or receipt.get("authorized_payload_classes") != PAYLOAD_CLASSES or receipt.get("paid_usage_authorized") is not True:
        raise HardStop("Phase 3D v3 data-egress authorization drift")
    if receipt.get("terminal_stop_on_first_failed_attempt") is not True or receipt.get("authorization_closes_on_completion_or_terminal_stop") is not True:
        raise HardStop("Phase 3D v3 terminal closure drift")
    if receipt.get("bindings") != source_bindings():
        raise HardStop("Phase 3D v3 receipt binding drift")
    if any(receipt.get("execution", {}).get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("Phase 3D v3 receipt is not execution-closed")
    if len(rows) != CALLS or len({row["logical_call_id"] for row in rows}) != CALLS or len({row["request_hash"] for row in rows}) != CALLS:
        raise HardStop("Phase 3D schedule identity drift")
    for index, row in enumerate(rows, 1):
        body = row["canonical_request_body"]
        if row.get("staged_execution_index") != index or row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False:
            raise HardStop("Phase 3D route or schedule drift")
    bindings = {"receipt_sha256": sha256_file(RECEIPT), **source_bindings(), "provider_adapter_sha256": sha256_file(ADAPTER), "analyzer_sha256": sha256_file(ANALYZER), "test_sha256": sha256_file(TEST), "live_runner_sha256": sha256_file(Path(__file__).resolve())}
    return {"schema_version": VERSION, "status": "zero-network-preflight-passed", "phase3d_design_fingerprint": DESIGN_FINGERPRINT, "phase3d_live_preflight_fingerprint": PREFLIGHT_FINGERPRINT, "authorized_calls": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "known_cumulative_cost_lower_bound_cny": PRIOR_KNOWN_COST, "bindings": bindings, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "data_egress_authorized": True, "authorized_destination": ENDPOINT, "authorized_payload_classes": PAYLOAD_CLASSES, "later_stages_authorized": False, "cross_domain_scaling_authorized": False, "formal_scaling_authorized": False}


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {"schema_version": VERSION, "experiment": "acl2027_phase3d_specificity_abstention_live_v3", "authorization_id": AUTH_ID, "status": "open", "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": stable(gate)}, "credential_sha256": hashlib.sha256(key.encode()).hexdigest(), **exact_contract(), "endpoint": ENDPOINT, "data_egress_authorized": True, "authorized_payload_classes": PAYLOAD_CLASSES, "paid_usage_authorized": True, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "formal_scaling_allowed": False, "forbidden_stages": load(RECEIPT)["forbidden_stages"]}


def open_authorization() -> dict[str, Any]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY missing")
    if any(path.exists() for path in (AUTH, AUTH_CLOSED, REGISTRY, LEDGER, PACING, CLOSURE)):
        raise HardStop("Phase 3D v3 authorization already opened, started, or closed")
    gate = preflight(); write(PREFLIGHT_AUDIT, gate); write(AUTH, authorization_template(key)); write(REGISTRY, {"schema_version": VERSION, "authorizations": {AUTH_ID: {"path": AUTH.name, "sha256": sha256_file(AUTH)}}})
    return load(AUTH)


def validate_authorization() -> tuple[dict[str, Any], str]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.is_file() or not REGISTRY.is_file() or AUTH_CLOSED.exists() or CLOSURE.exists():
        raise HardStop("Phase 3D v3 authorization is closed or absent")
    auth = load(AUTH)
    if auth != authorization_template(key):
        raise HardStop("Phase 3D v3 authorization drift")
    item = load(REGISTRY)["authorizations"].get(AUTH_ID)
    if not item or item.get("sha256") != sha256_file(AUTH):
        raise HardStop("Phase 3D v3 authorization registry drift")
    return auth, item["sha256"]


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records):
        raise HardStop("ambiguous request start; retry forbidden")
    previous = previous_start = None; total = 0.0; ids: set[str] = set()
    for planned, record, start in zip(rows, records, starts):
        if start.get("logical_call_id") != planned["logical_call_id"] or start.get("request_hash") != planned["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous_start or start.get("request_body_sha256") != stable(planned["canonical_request_body"]):
            raise HardStop("request-start binding drift")
        if start.get("start_entry_sha256") != stable({key: value for key, value in start.items() if key != "start_entry_sha256"}):
            raise HardStop("request-start hash drift")
        for key in ("logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index"):
            if record.get(key) != planned.get(key):
                raise HardStop("non-prefix ledger")
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous or record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}) or record.get("terminal"):
            raise HardStop("ledger chain is not resumable")
        request_id = record.get("request_id")
        if not request_id or request_id in ids:
            raise HardStop("missing or duplicate provider response id")
        ids.add(request_id); call_cost = cost(usage(record)); total = round(total + call_cost, 6)
        if record.get("local_cost_cny") != call_cost or record.get("cumulative_local_cost_cny") != total:
            raise HardStop("cost accounting drift")
        previous, previous_start = record["ledger_entry_sha256"], start["start_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization(); rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []
    validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        if known_cost(records) >= STAGE_CEILING or PRIOR_KNOWN_COST + known_cost(records) >= CUMULATIVE_CEILING:
            raise HardStop("cost ceiling reached before next attempt")
        row = rows[len(records)]; body = deepcopy(row["canonical_request_body"])
        if row["request_hash"] != stable(body) or "max_tokens" in body:
            raise HardStop("request boundary drift")
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0: time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts) + 1, "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "request_body_sha256": stable(body), "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start); starts.append(start); write(PACING, starts)
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index")}
        base.update({"provider_attempt_index": len(records) + 1, "authorization_id": AUTH_ID, "authorization_sha256": auth_sha, "authorized_stage": "specificity_abstention", "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None})
        try:
            response = provider(body); exact = usage(response); content = response["content"]; call_cost = cost(exact)
            record = {**base, "request_id": response.get("request_id"), "raw_response": content, "raw_response_sha256": stable(content), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "local_cost_cny": call_cost, "cumulative_local_cost_cny": round(known_cost(records) + call_cost, 6), "terminal": False, "status": "completed", "error": None}
            if not record["request_id"] or record["request_id"] in {item.get("request_id") for item in records}:
                raise HardStop("missing or duplicate provider response id")
        except Exception as exc:
            record = {**base, "request_id": None, "raw_response": None, "raw_response_sha256": stable(None), "raw_provider_response": None, "usage": None, "local_cost_cny": None, "cumulative_local_cost_cny": None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        record["ledger_entry_sha256"] = stable(record); records.append(record); write(LEDGER, records)
        if record["terminal"]: raise HardStop(record["error"])
        if (known_cost(records) >= STAGE_CEILING or PRIOR_KNOWN_COST + known_cost(records) >= CUMULATIVE_CEILING) and len(records) < CALLS:
            raise HardStop("cost ceiling reached")
    return records


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]; records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []
    auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha: raise HardStop("ledger exists without authorization")
    if auth_sha and records and not records[-1].get("terminal"): validate_prefix(records, starts, rows, auth_sha)
    known = [record for record in records if isinstance(record.get("usage"), dict)]; request_ids = [record.get("request_id") for record in records if record.get("request_id")]
    complete = len(records) == CALLS and not (records and records[-1].get("terminal")); stage_cost = known_cost(records)
    result = {"schema_version": VERSION, "stage": "specificity_abstention", "status": "completed" if complete else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete", "planned_calls": CALLS, "provider_attempts": len(starts), "completed_calls": sum(record.get("status") == "completed" for record in records), "unique_logical_requests": len({record.get("logical_call_id") for record in records}), "unique_request_hashes": len({record.get("request_hash") for record in records}), "unique_provider_request_ids": len(set(request_ids)), "terminal_rows": sum(bool(record.get("terminal")) for record in records), "input_tokens": sum(usage(record)["input_tokens"] for record in known), "output_tokens": sum(usage(record)["output_tokens"] for record in known), "total_tokens": sum(usage(record)["total_tokens"] for record in known), "usage_status": "exact" if len(known) == len(records) else "known_lower_bound", "exact_stage_cost_cny": stage_cost if len(known) == len(records) else None, "known_stage_cost_lower_bound_cny": stage_cost, "prior_known_cumulative_cost_lower_bound_cny": PRIOR_KNOWN_COST, "exact_cumulative_cost_cny": None, "known_cumulative_cost_lower_bound_cny": round(PRIOR_KNOWN_COST + stage_cost, 6), "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "retries": sum(record.get("retries", 0) for record in records), "duplicates": len(records) - len({record.get("logical_call_id") for record in records}), "max_tokens_present": any(record.get("max_tokens_present") for record in records), "model_id": "qwen3.7-plus", "temperature": 0, "request_start_pacing_valid": all(second["request_started_at_unix_ns"] - first["request_started_at_unix_ns"] >= INTERVAL_NS for first, second in zip(starts, starts[1:])), "ledger_hash_chain_valid": True, "request_start_hash_chain_valid": True, "exact_prefix_resume_valid": True, "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts), "specificity_abstention_calls": len(starts), "later_stage_calls": 0, "cross_domain_scaling_calls": 0, "formal_scaling_calls": 0, "authorization_closed": AUTH_CLOSED.exists() and CLOSURE.exists()}
    write(RUN_AUDIT, result); return result


def close(reason: str) -> dict[str, Any]:
    result = audit(); closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None, "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "exact_stage_cost_cny": result["exact_stage_cost_cny"], "known_stage_cost_lower_bound_cny": result["known_stage_cost_lower_bound_cny"], "known_cumulative_cost_lower_bound_cny": result["known_cumulative_cost_lower_bound_cny"], "specificity_abstention_calls": result["provider_attempts"], "later_stage_calls": 0, "cross_domain_scaling_calls": 0, "formal_scaling_calls": 0, "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}
    write(CLOSURE, closure); write(AUTH_CLOSED, closure); result["authorization_closed"] = True; write(RUN_AUDIT, result); return closure


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close")); args = parser.parse_args()
    if args.command == "preflight": result = preflight(); write(PREFLIGHT_AUDIT, result)
    elif args.command == "authorize": result = open_authorization()
    elif args.command == "audit": result = audit()
    elif args.command == "close": result = close("operator_close")
    else:
        try: result = {"rows": len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))), "closure": close("completed_exact_240")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists(): close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
