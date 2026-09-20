#!/usr/bin/env python3
"""Authorization-gated live runner for the immutable Phase 3B activation grid."""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage

VERSION, CALLS = 3, 300
STAGE_CEILING, CUMULATIVE_CEILING, PRIOR_KNOWN_COST = 3.0, 11.0, 7.218738
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase3b-activation-live-v3"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
PAYLOAD_CLASSES = ["frozen_task_prompts", "historical_skill_context"]
RECEIPT = ROOT / "configs/acl2027/phase3b_activation_user_authorization_receipt_v3.json"
PREFLIGHT_CONFIG = ROOT / "configs/acl2027/phase3b_activation_preflight_v1.json"
PREFLIGHT = ROOT / "artifacts/acl2027_phase3b_activation_preflight_v1"
MANIFEST, SCHEDULE = PREFLIGHT / "run_manifest.json", PREFLIGHT / "activation_schedule.json"
GOLD, ANALYSIS_PLAN = PREFLIGHT / "activation_private_gold.json", PREFLIGHT / "analysis_plan.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ANALYZER = ROOT / "scripts/analyze_acl2027_phase3b_activation_live_v3.py"
TEST = ROOT / "tests/test_acl2027_phase3b_activation_live_v3.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3b_activation_live_v3"
PREFLIGHT_AUDIT, REGISTRY = ARTIFACT / "zero_network_preflight.json", ARTIFACT / "authorization_registry.json"
AUTH, AUTH_CLOSED = ARTIFACT / "authorization_open.json", ARTIFACT / "authorization_closed.json"
LEDGER, PACING = ARTIFACT / "ledger.json", ARTIFACT / "request_start_ledger.json"
RUN_AUDIT, CLOSURE = ARTIFACT / "run_audit.json", ARTIFACT / "authorization_closure.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=True, sort_keys=True, indent=2); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()


def cost(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * 2.0 + value["output_tokens"] * 8.0) / 1_000_000, 6)


def known_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(row.get("local_cost_cny") or 0.0 for row in records), 6)


def exact_contract() -> dict[str, Any]:
    return {"scope": "phase3b_activation_pilot_only", "authorized_stage": "activation_pilot", "authorized_calls": CALLS, "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "enable_thinking": False, "response_format": {"type": "json_object"}, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "known_cumulative_cost_lower_bound_cny": PRIOR_KNOWN_COST, "later_stages_authorized": False, "formal_scaling_authorized": False}


def preflight() -> dict[str, Any]:
    cfg, manifest, rows, receipt = load(PREFLIGHT_CONFIG), load(MANIFEST), load(SCHEDULE)["schedule"], load(RECEIPT)
    fingerprint = "fe1bb5316f57e4aa4dba14e19a173a44c60575263bd54018b8b33e6d256de7b8"
    if manifest.get("aggregate_fingerprint") != fingerprint or manifest.get("status") != "design-preflight-passed-closed": raise HardStop("Phase 3B manifest boundary drift")
    if any(value is not False for value in cfg.get("execution", {}).values()): raise HardStop("Phase 3B preflight must remain execution-closed")
    if receipt.get("status") != "explicit_user_authorization_received_execution_not_open" or receipt.get("phase3b_aggregate_fingerprint") != fingerprint or any(receipt.get(k) != v for k, v in exact_contract().items()): raise HardStop("Phase 3B v3 receipt boundary drift")
    if receipt.get("data_egress_authorized") is not True or receipt.get("authorized_destination") != ENDPOINT or receipt.get("authorized_payload_classes") != PAYLOAD_CLASSES or receipt.get("paid_usage_authorized") is not True: raise HardStop("Phase 3B v3 data-egress authorization drift")
    expected = {"phase3b_manifest_sha256": sha256_file(MANIFEST), "phase3b_schedule_sha256": sha256_file(SCHEDULE), "phase3b_gold_sha256": sha256_file(GOLD), "phase3b_analysis_plan_sha256": sha256_file(ANALYSIS_PLAN)}
    if receipt.get("bindings") != expected: raise HardStop("Phase 3B v3 receipt binding drift")
    if any(receipt.get("execution", {}).get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")): raise HardStop("Phase 3B v3 receipt is not execution-closed")
    if len(rows) != CALLS or len({r["logical_call_id"] for r in rows}) != CALLS or len({r["request_hash"] for r in rows}) != CALLS: raise HardStop("Phase 3B schedule identity drift")
    for index, row in enumerate(rows, 1):
        body = row["canonical_request_body"]
        if row.get("staged_execution_index") != index or body.get("stage") != "activation_pilot" or body.get("partition") != "mechanism_bridge_held_out" or row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False: raise HardStop("Phase 3B route/prefix drift")
    bindings = {"receipt_sha256": sha256_file(RECEIPT), "phase3b_config_sha256": sha256_file(PREFLIGHT_CONFIG), **expected, "provider_adapter_sha256": sha256_file(ADAPTER), "analyzer_sha256": sha256_file(ANALYZER), "test_sha256": sha256_file(TEST), "live_runner_sha256": sha256_file(Path(__file__).resolve())}
    return {"schema_version": VERSION, "status": "zero-network-preflight-passed", "phase3b_aggregate_fingerprint": fingerprint, "authorized_calls": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "known_cumulative_cost_lower_bound_cny": PRIOR_KNOWN_COST, "bindings": bindings, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "data_egress_authorized": True, "authorized_destination": ENDPOINT, "authorized_payload_classes": PAYLOAD_CLASSES, "later_stages_authorized": False, "formal_scaling_authorized": False}


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {"schema_version": VERSION, "experiment": "acl2027_phase3b_activation_live_v3", "authorization_id": AUTH_ID, "status": "open", "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": stable(gate)}, "credential_sha256": hashlib.sha256(key.encode()).hexdigest(), **exact_contract(), "endpoint": ENDPOINT, "request_interval_seconds": 1.0, "data_egress_authorized": True, "authorized_payload_classes": PAYLOAD_CLASSES, "paid_usage_authorized": True, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "formal_scaling_allowed": False, "forbidden_stages": load(RECEIPT)["forbidden_stages"]}


def open_authorization() -> dict[str, Any]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key: raise HardStop("DASHSCOPE_API_KEY missing")
    if any(path.exists() for path in (AUTH, AUTH_CLOSED, REGISTRY, LEDGER, PACING, CLOSURE)): raise HardStop("Phase 3B v3 authorization already opened, started, or closed")
    gate = preflight(); write(PREFLIGHT_AUDIT, gate); write(AUTH, authorization_template(key)); write(REGISTRY, {"schema_version": VERSION, "authorizations": {AUTH_ID: {"path": AUTH.name, "sha256": sha256_file(AUTH)}}})
    return load(AUTH)


def validate_authorization() -> tuple[dict[str, Any], str]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.is_file() or not REGISTRY.is_file() or AUTH_CLOSED.exists() or CLOSURE.exists(): raise HardStop("Phase 3B v3 authorization is closed or absent")
    auth = load(AUTH)
    if auth != authorization_template(key): raise HardStop("Phase 3B v3 authorization drift")
    item = load(REGISTRY)["authorizations"].get(AUTH_ID)
    if not item or item.get("sha256") != sha256_file(AUTH): raise HardStop("Phase 3B v3 authorization registry drift")
    return auth, item["sha256"]


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records): raise HardStop("ambiguous request start; retry forbidden")
    previous = previous_start = None; total = 0.0; ids: set[str] = set()
    for planned, record, start in zip(rows, records, starts):
        if start.get("logical_call_id") != planned["logical_call_id"] or start.get("request_hash") != planned["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous_start or start.get("request_body_sha256") != stable(planned["canonical_request_body"]): raise HardStop("request-start binding drift")
        if start.get("start_entry_sha256") != stable({k: v for k, v in start.items() if k != "start_entry_sha256"}): raise HardStop("request-start hash drift")
        for key in ("logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index"):
            if record.get(key) != planned.get(key): raise HardStop("non-prefix ledger")
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous or record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}) or record.get("terminal"): raise HardStop("ledger chain is not resumable")
        request_id = record.get("request_id")
        if not request_id or request_id in ids: raise HardStop("missing or duplicate provider response id")
        ids.add(request_id); call_cost = cost(usage(record)); total = round(total + call_cost, 6)
        if record.get("local_cost_cny") != call_cost or record.get("cumulative_local_cost_cny") != total: raise HardStop("cost accounting drift")
        previous, previous_start = record["ledger_entry_sha256"], start["start_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization(); rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []
    validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        if known_cost(records) >= STAGE_CEILING or PRIOR_KNOWN_COST + known_cost(records) >= CUMULATIVE_CEILING: raise HardStop("cost ceiling reached before next attempt")
        row = rows[len(records)]; body = deepcopy(row["canonical_request_body"])
        if row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False: raise HardStop("request boundary drift")
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0: time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts)+1, "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "request_body_sha256": stable(body), "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start); starts.append(start); write(PACING, starts)
        base = {k: row[k] for k in ("logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index")}
        base.update({"provider_attempt_index": len(records)+1, "authorization_id": AUTH_ID, "authorization_sha256": auth_sha, "authorized_stage": "activation_pilot", "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None})
        try:
            response = provider(body); exact = usage(response); content = response["content"]; call_cost = cost(exact)
            record = {**base, "request_id": response.get("request_id"), "raw_response": content, "raw_response_sha256": stable(content), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "local_cost_cny": call_cost, "cumulative_local_cost_cny": round(known_cost(records)+call_cost, 6), "terminal": False, "status": "completed", "error": None}
            if not record["request_id"] or record["request_id"] in {item.get("request_id") for item in records}: raise HardStop("missing or duplicate provider response id")
        except Exception as exc:
            record = {**base, "request_id": None, "raw_response": None, "raw_response_sha256": stable(None), "raw_provider_response": None, "usage": None, "local_cost_cny": None, "cumulative_local_cost_cny": None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        record["ledger_entry_sha256"] = stable(record); records.append(record); write(LEDGER, records)
        if record["terminal"]: raise HardStop(record["error"])
        if (known_cost(records) >= STAGE_CEILING or PRIOR_KNOWN_COST + known_cost(records) >= CUMULATIVE_CEILING) and len(records) < CALLS: raise HardStop("cost ceiling reached")
    return records


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]; records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []
    auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha: raise HardStop("ledger exists without authorization")
    if auth_sha and records and not records[-1].get("terminal"): validate_prefix(records, starts, rows, auth_sha)
    known = [r for r in records if isinstance(r.get("usage"), dict)]; request_ids = [r.get("request_id") for r in records if r.get("request_id")]
    complete = len(records) == CALLS and not (records and records[-1].get("terminal")); stage_cost = known_cost(records)
    result = {"schema_version": VERSION, "stage": "activation_pilot", "status": "completed" if complete else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete", "planned_calls": CALLS, "provider_attempts": len(starts), "completed_calls": sum(r.get("status") == "completed" for r in records), "unique_logical_requests": len({r.get("logical_call_id") for r in records}), "unique_request_hashes": len({r.get("request_hash") for r in records}), "unique_provider_request_ids": len(set(request_ids)), "terminal_rows": sum(bool(r.get("terminal")) for r in records), "input_tokens": sum(usage(r)["input_tokens"] for r in known), "output_tokens": sum(usage(r)["output_tokens"] for r in known), "total_tokens": sum(usage(r)["total_tokens"] for r in known), "usage_status": "exact" if len(known) == len(records) else "known_lower_bound", "exact_stage_cost_cny": stage_cost if len(known) == len(records) else None, "known_stage_cost_lower_bound_cny": stage_cost, "prior_known_cumulative_cost_lower_bound_cny": PRIOR_KNOWN_COST, "known_cumulative_cost_lower_bound_cny": round(PRIOR_KNOWN_COST+stage_cost, 6), "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "retries": sum(r.get("retries", 0) for r in records), "duplicates": len(records)-len({r.get("logical_call_id") for r in records}), "max_tokens_present": any(r.get("max_tokens_present") for r in records), "model_id": "qwen3.7-plus", "temperature": 0, "request_start_pacing_valid": all(b["request_started_at_unix_ns"]-a["request_started_at_unix_ns"] >= INTERVAL_NS for a,b in zip(starts,starts[1:])), "ledger_hash_chain_valid": True, "request_start_hash_chain_valid": True, "exact_prefix_resume_valid": True, "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts), "activation_calls": len(starts), "later_stage_calls": 0, "formal_scaling_calls": 0, "authorization_closed": AUTH_CLOSED.exists() and CLOSURE.exists()}
    write(RUN_AUDIT, result); return result


def close(reason: str) -> dict[str, Any]:
    result = audit(); closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None, "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "exact_stage_cost_cny": result["exact_stage_cost_cny"], "known_stage_cost_lower_bound_cny": result["known_stage_cost_lower_bound_cny"], "known_cumulative_cost_lower_bound_cny": result["known_cumulative_cost_lower_bound_cny"], "activation_calls": result["provider_attempts"], "later_stage_calls": 0, "formal_scaling_calls": 0, "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}
    write(CLOSURE, closure); write(AUTH_CLOSED, closure); result["authorization_closed"] = True; write(RUN_AUDIT, result); return closure


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close")); args = parser.parse_args()
    if args.command == "preflight": result = preflight(); write(PREFLIGHT_AUDIT, result)
    elif args.command == "authorize": result = open_authorization()
    elif args.command == "audit": result = audit()
    elif args.command == "close": result = close("operator_close")
    else:
        try: result = {"rows": len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))), "closure": close("completed_exact_300")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists(): close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
