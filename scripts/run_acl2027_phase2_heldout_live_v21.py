#!/usr/bin/env python3
"""Authorization-gated live runner for the exact v21 held-out schedule."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.run_acl2027_phase2_heldout_activation_preflight_v21 import validate as validate_v21

ENGINE_SPEC = importlib.util.spec_from_file_location("scripts._acl2027_phase2_heldout_engine_v21", ROOT / "scripts/run_acl2027_phase2_probe_only_live_v18.py")
if ENGINE_SPEC is None or ENGINE_SPEC.loader is None:
    raise ImportError("unable to load isolated ledger engine")
engine = importlib.util.module_from_spec(ENGINE_SPEC)
sys.modules[ENGINE_SPEC.name] = engine
ENGINE_SPEC.loader.exec_module(engine)

VERSION = 21
CALLS = 320
COST_CEILING = 3.5
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase2-heldout-only-v21"
RECEIPT = ROOT / "configs/acl2027/phase2_heldout_user_authorization_receipt_v21.json"
REQUEST = ROOT / "configs/acl2027/phase2_heldout_only_authorization_request_v21.json"
AUTH = ROOT / "configs/acl2027/phase2_heldout_live_authorization_v21.json"
AUTH_CLOSED = ROOT / "configs/acl2027/phase2_heldout_live_authorization_closed_v21.json"
PREFLIGHT_CONFIG = ROOT / "configs/acl2027/phase2_heldout_activation_preflight_v21.json"
PREFLIGHT_ARTIFACT = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21"
V21_MANIFEST = PREFLIGHT_ARTIFACT / "run_manifest.json"
SCHEDULE = PREFLIGHT_ARTIFACT / "held_out_schedule.json"
PRIOR_BUNDLES = PREFLIGHT_ARTIFACT / "prior_bundles.json"
PROVIDER_ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
TEST = ROOT / "tests/test_acl2027_phase2_heldout_live_v21.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_heldout_live_v21"
PREFLIGHT_AUDIT = ARTIFACT / "zero_network_preflight.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
RUN_AUDIT = ARTIFACT / "run_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"


def _set_engine_paths() -> None:
    values = {"VERSION": VERSION, "CALLS": CALLS, "COST_CEILING": COST_CEILING, "AUTH_ID": AUTH_ID, "RECEIPT": RECEIPT, "REQUEST": REQUEST, "AUTH": AUTH, "AUTH_CLOSED": AUTH_CLOSED, "V17_CONFIG": PREFLIGHT_CONFIG, "V17_ARTIFACT": PREFLIGHT_ARTIFACT, "V17_MANIFEST": V21_MANIFEST, "SCHEDULE": SCHEDULE, "PRIOR_BUNDLES": PRIOR_BUNDLES, "REPLACEMENT_GOLD": SCHEDULE, "CANDIDATE": V21_MANIFEST, "PROVIDER_ADAPTER": PROVIDER_ADAPTER, "ANALYZER": TEST, "TEST": TEST, "ARTIFACT": ARTIFACT, "PREFLIGHT_AUDIT": PREFLIGHT_AUDIT, "REGISTRY": REGISTRY, "LEDGER": LEDGER, "PACING": PACING, "PROBE_AUDIT": ARTIFACT / "held_out_audit.json", "RUN_AUDIT": RUN_AUDIT, "CLOSURE": CLOSURE, "INTERVAL_NS": INTERVAL_NS}
    for name, value in values.items():
        setattr(engine, name, value)


_set_engine_paths()
load = engine.load
write = engine.write
usage = engine.usage
known_cost = engine.known_cost
local_cost_from_usage = engine.local_cost_from_usage
HardStop = engine.HardStop


def preflight() -> dict[str, Any]:
    gate = validate_v21()
    request, receipt = load(REQUEST), load(RECEIPT)
    if gate["aggregate_fingerprint"] != request["bindings"]["preflight_aggregate_fingerprint"]:
        raise HardStop("v21 preflight/request fingerprint drift")
    if sha256_file(REQUEST) != receipt["request_binding"]["authorization_request_sha256"] or receipt["request_binding"]["preflight_aggregate_fingerprint"] != gate["aggregate_fingerprint"]:
        raise HardStop("v21 receipt binding drift")
    exact = {"scope": "held_out_only", "authorized_stage": "held_out", "authorized_calls": CALLS, "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "enable_thinking": False, "response_format": {"type": "json_object"}, "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": 7.5, "held_out_authorized": True, "later_stages_authorized": False, "formal_scaling_authorized": False}
    if any(receipt.get(key) != value for key, value in exact.items()) or receipt.get("status") != "explicit_user_authorization_received_execution_not_open":
        raise HardStop("v21 user authorization boundary drift")
    if any(receipt.get("execution", {}).get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v21 receipt must remain execution-closed")
    expected = {"preflight_manifest_sha256": V21_MANIFEST, "preflight_schedule_sha256": SCHEDULE, "preflight_prior_bundles_sha256": PRIOR_BUNDLES, "preflight_config_sha256": PREFLIGHT_CONFIG}
    for name, path in expected.items():
        if request["bindings"].get(name) != sha256_file(path):
            raise HardStop(f"v21 binding drift: {name}")
    rows = load(SCHEDULE)["schedule"]
    if len(rows) != CALLS or len({r["logical_call_id"] for r in rows}) != CALLS or len({r["request_hash"] for r in rows}) != CALLS:
        raise HardStop("v21 schedule identity drift")
    if any(r.get("staged_execution_index") != i or r.get("partition") != "held_out" or r["request_hash"] != stable(r["canonical_request_body"] ) or "max_tokens" in r["canonical_request_body"] or r["canonical_request_body"].get("model_id") != "qwen3.7-plus" or r["canonical_request_body"].get("temperature") != 0 or r["canonical_request_body"].get("response_format") != {"type": "json_object"} or r["canonical_request_body"].get("enable_thinking") is not False for i, r in enumerate(rows, 1)):
        raise HardStop("v21 request route/prefix drift")
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise HardStop("DASHSCOPE_API_KEY missing")
    result = {"schema_version": VERSION, "status": "zero-network-preflight-passed", "authorized_calls": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": 7.5, "v21_aggregate_fingerprint": gate["aggregate_fingerprint"], "bindings": {"authorization_receipt_sha256": sha256_file(RECEIPT), "authorization_request_sha256": sha256_file(REQUEST), "preflight_config_sha256": sha256_file(PREFLIGHT_CONFIG), "preflight_manifest_sha256": sha256_file(V21_MANIFEST), "schedule_sha256": sha256_file(SCHEDULE), "prior_bundles_sha256": sha256_file(PRIOR_BUNDLES), "provider_adapter_sha256": sha256_file(PROVIDER_ADAPTER), "live_runner_sha256": sha256_file(Path(__file__).resolve()), "live_test_sha256": sha256_file(TEST)}, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "held_out_authorized": True, "later_stages_authorized": False, "formal_scaling_authorized": False}
    result["aggregate_fingerprint"] = stable(result)
    return result


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {"schema_version": VERSION, "experiment": "acl2027_phase2_heldout_live_v21", "authorization_id": AUTH_ID, "status": "open", "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": gate["aggregate_fingerprint"]}, "credential_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(), "user_authorization": {"scope": "held_out_only", "authorized_calls": CALLS, "authorization_receipt_sha256": sha256_file(RECEIPT), "held_out_authorized": True, "later_stages_authorized": False, "formal_scaling_authorized": False}, "authorized_stage": "held_out", "authorized_calls": CALLS, "stage_call_ceiling": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": 7.5, "model_id": "qwen3.7-plus", "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "formal_scaling_allowed": False, "forbidden_stages": ["calibration", "development_acquisition", "formal_history", "probe", "later_phase2_stages", "formal_scaling"]}


engine.preflight = preflight
engine.authorization_template = authorization_template


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    _, auth_sha = engine.validate_authorization()
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    engine.validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        if known_cost(records) >= COST_CEILING:
            raise HardStop("v21 cost ceiling reached before next attempt", records)
        row = rows[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False:
            raise HardStop("v21 request boundary drift", records)
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0:
                time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts) + 1, "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "request_body_sha256": stable(body), "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(PACING, starts)
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "payload_hash", "staged_execution_index")}
        base.update(provider_attempt_index=len(records) + 1, authorization_id=AUTH_ID, authorization_sha256=auth_sha, authorized_stage="held_out", model_id="qwen3.7-plus", temperature=0, retries=0, max_tokens_present=False, previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None)
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            if not isinstance(response.get("content"), str):
                raise HardStop("v21 provider response missing content")
            cost = local_cost_from_usage(exact)
            record = {**base, "request_id": response.get("request_id"), "raw_response": response["content"], "raw_response_sha256": stable(response["content"]), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "local_cost_cny": cost, "cumulative_local_cost_cny": round(known_cost(records) + cost, 6), "terminal": False, "status": "completed", "error": None}
        except Exception as exc:
            maybe = response.get("usage") if isinstance(response, dict) and isinstance(response.get("usage"), dict) else None
            cost = local_cost_from_usage(usage(response)) if maybe is not None else None
            content = response.get("content") if isinstance(response, dict) else None
            record = {**base, "request_id": response.get("request_id") if isinstance(response, dict) else None, "raw_response": content, "raw_response_sha256": stable(content), "raw_provider_response": response.get("raw_provider_response", response) if isinstance(response, dict) else response, "usage": maybe, "local_cost_cny": cost, "cumulative_local_cost_cny": round(known_cost(records) + (cost or 0), 6) if cost is not None else None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        record["ledger_entry_sha256"] = stable(record)
        records.append(record)
        write(LEDGER, records)
        if record["terminal"]:
            raise HardStop(record["error"], records)
        if known_cost(records) >= COST_CEILING and len(records) < CALLS:
            records[-1].update(terminal=True, status="completed_cost_ceiling_stop", error="v21 cost ceiling reached")
            records[-1]["ledger_entry_sha256"] = stable({k: v for k, v in records[-1].items() if k != "ledger_entry_sha256"})
            write(LEDGER, records)
            raise HardStop(records[-1]["error"], records)
    return records


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha:
        raise HardStop("v21 ledger exists without authorization")
    if auth_sha:
        engine.validate_audit_chain(records, starts, rows, auth_sha)
    known = [r for r in records if isinstance(r.get("usage"), dict)]
    terminal = bool(records and records[-1].get("terminal"))
    statuses = {"completed", "completed_cost_ceiling_stop"}
    completed = [r for r in records if r.get("status") in statuses]
    request_ids = [r.get("request_id") for r in records if r.get("request_id")]
    if len(request_ids) != len(completed) or len(set(request_ids)) != len(request_ids):
        raise HardStop("v21 provider request IDs missing or duplicated")
    result = {"schema_version": VERSION, "stage": "held_out", "status": "completed" if len(records) == CALLS and not terminal else "terminal_hard_stop" if terminal else "incomplete", "planned_calls": CALLS, "provider_attempts": len(starts), "unique_logical_requests": len({r.get("logical_call_id") for r in records}), "unique_request_hashes": len({r.get("request_hash") for r in records}), "unique_provider_request_ids": len(set(request_ids)), "completed_calls": len(completed), "terminal_rows": sum(bool(r.get("terminal")) for r in records), "input_tokens": sum(usage(r)["input_tokens"] for r in known), "output_tokens": sum(usage(r)["output_tokens"] for r in known), "total_tokens": sum(usage(r)["total_tokens"] for r in known), "usage_status": "exact" if len(known) == len(records) else "known_lower_bound", "exact_local_cost_cny": known_cost(records) if len(known) == len(records) else None, "known_local_cost_lower_bound_cny": known_cost(records), "retries": sum(r.get("retries", 0) for r in records), "duplicates": len(records) - len({r.get("logical_call_id") for r in records}), "max_tokens_present": any(r.get("max_tokens_present") for r in records), "model_id": "qwen3.7-plus", "temperature": 0, "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])), "ledger_hash_chain_valid": True, "request_start_hash_chain_valid": True, "exact_prefix_resume_valid": True, "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts), "calibration_calls": 0, "development_calls": 0, "formal_history_calls": 0, "probe_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0, "authorization_closed": CLOSURE.exists() and AUTH_CLOSED.exists()}
    write(RUN_AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None, "authorization_receipt_sha256": sha256_file(RECEIPT), "authorization_request_sha256": sha256_file(REQUEST), "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "usage_status": result["usage_status"], "exact_local_cost_cny": result["exact_local_cost_cny"], "known_local_cost_lower_bound_cny": result["known_local_cost_lower_bound_cny"], "calibration_calls": 0, "development_calls": 0, "formal_history_calls": 0, "probe_calls": 0, "held_out_calls": result["provider_attempts"], "later_stage_calls": 0, "formal_scaling_calls": 0, "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}
    write(CLOSURE, closure)
    write(AUTH_CLOSED, closure)
    result["authorization_closed"] = True
    write(RUN_AUDIT, result)
    return closure


engine.audit = audit
engine.close = close


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = preflight(); write(PREFLIGHT_AUDIT, result)
    elif args.command == "authorize":
        result = engine.open_authorization()
    elif args.command == "audit":
        result = audit()
    elif args.command == "close":
        result = close("operator_close")
    else:
        try:
            records = execute(QwenTokenPlanProviderAdapter(engine.validate_authorization()[0]))
            result = {"rows": len(records), "closure": close("completed_exact_320")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
