#!/usr/bin/env python3
"""Authorization-gated live runner for the immutable v24 replication schedule."""
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
VERSION = 25
CALLS = 320
STAGE_CEILING = 3.5
CUMULATIVE_CEILING = 3.5
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase2-post-v23-replication-only-v25"
CONFIG = ROOT / "configs/acl2027/phase2_post_v23_replication_design_preflight_v24.json"
RECEIPT = ROOT / "configs/acl2027/phase2_post_v23_replication_user_authorization_receipt_v25.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v23_replication_live_v25"
PREFLIGHT_AUDIT = ARTIFACT / "zero_network_preflight.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
AUTH = ARTIFACT / "authorization_open.json"
AUTH_CLOSED = ARTIFACT / "authorization_closed.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
RUN_AUDIT = ARTIFACT / "run_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
MANIFEST = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24/run_manifest.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24/replication_schedule.json"
PRIOR_BUNDLES = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24/prior_bundles.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"


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
        if os.path.exists(temp): os.unlink(temp)


def cost(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * 2.0 + value["output_tokens"] * 8.0) / 1_000_000, 6)


def known_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(row.get("local_cost_cny") or 0.0 for row in records), 6)


def exact_contract() -> dict[str, Any]:
    return {"scope": "post_v23_replication_only", "authorized_stage": "post_v23_replication", "authorized_calls": CALLS, "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "enable_thinking": False, "response_format": {"type": "json_object"}, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "later_stages_authorized": False, "formal_scaling_authorized": False}


def preflight() -> dict[str, Any]:
    cfg, manifest, rows = load(CONFIG), load(MANIFEST), load(SCHEDULE)["schedule"]
    receipt = load(RECEIPT)
    if manifest.get("aggregate_fingerprint") != "9096f3ac47dc01248146cecf2754914f7ddb2896f6e7be46f715c609249b5407": raise HardStop("v24 fingerprint drift")
    if manifest.get("status") != "design-preflight-passed-closed" or manifest.get("logical_calls_proposed") != CALLS: raise HardStop("v24 manifest boundary drift")
    if cfg.get("execution", {}).get("provider_calls_allowed") is not False: raise HardStop("v24 must remain closed")
    if any(receipt.get(k) != v for k, v in exact_contract().items()) or receipt.get("status") != "explicit_user_authorization_received_execution_not_open": raise HardStop("v25 receipt boundary drift")
    if any(receipt.get("execution", {}).get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")): raise HardStop("v25 receipt is not execution-closed")
    if len(rows) != CALLS or len({r["logical_call_id"] for r in rows}) != CALLS or len({r["request_hash"] for r in rows}) != CALLS: raise HardStop("v24 schedule identity drift")
    for index, row in enumerate(rows, 1):
        body = row["canonical_request_body"]
        if row.get("staged_execution_index") != index or row.get("partition") != "replication_held_out" or row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False: raise HardStop("v24 request route/prefix drift")
    return {"schema_version": VERSION, "status": "zero-network-preflight-passed", "v24_aggregate_fingerprint": manifest["aggregate_fingerprint"], "authorized_calls": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "bindings": {"receipt_sha256": sha256_file(RECEIPT), "v24_config_sha256": sha256_file(CONFIG), "v24_manifest_sha256": sha256_file(MANIFEST), "v24_schedule_sha256": sha256_file(SCHEDULE), "v24_prior_bundles_sha256": sha256_file(PRIOR_BUNDLES), "provider_adapter_sha256": sha256_file(ADAPTER), "live_runner_sha256": sha256_file(Path(__file__).resolve())}, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "later_stages_authorized": False, "formal_scaling_authorized": False}


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {"schema_version": VERSION, "experiment": "acl2027_phase2_post_v23_replication_live_v25", "authorization_id": AUTH_ID, "status": "open", "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": stable(gate)}, "credential_sha256": hashlib.sha256(key.encode()).hexdigest(), **exact_contract(), "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "request_interval_seconds": 1.0, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "formal_scaling_allowed": False, "forbidden_stages": ["calibration", "development_acquisition", "formal_history", "probe", "held_out", "later_phase2_stages", "formal_scaling"]}


def open_authorization() -> dict[str, Any]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key: raise HardStop("DASHSCOPE_API_KEY missing")
    if any(path.exists() for path in (AUTH, AUTH_CLOSED, REGISTRY, LEDGER, PACING, CLOSURE)): raise HardStop("v25 authorization already opened, started, or closed")
    gate = preflight(); write(PREFLIGHT_AUDIT, gate); write(AUTH, authorization_template(key)); write(REGISTRY, {"schema_version": VERSION, "authorizations": {AUTH_ID: {"path": AUTH.name, "sha256": sha256_file(AUTH)}}}); return load(AUTH)


def validate_authorization() -> tuple[dict[str, Any], str]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.is_file() or not REGISTRY.is_file() or AUTH_CLOSED.exists() or CLOSURE.exists(): raise HardStop("v25 authorization is closed or absent")
    auth = load(AUTH)
    if auth != authorization_template(key): raise HardStop("v25 authorization drift")
    item = load(REGISTRY)["authorizations"].get(AUTH_ID)
    if not item or item.get("sha256") != sha256_file(AUTH): raise HardStop("v25 authorization registry drift")
    return auth, item["sha256"]


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records): raise HardStop("ambiguous request start; retry forbidden")
    previous = None; previous_start = None; total = 0.0
    for planned, record, start in zip(rows, records, starts):
        if start.get("logical_call_id") != planned["logical_call_id"] or start.get("request_hash") != planned["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous_start or start.get("request_body_sha256") != stable(planned["canonical_request_body"]): raise HardStop("request-start binding drift")
        if start.get("start_entry_sha256") != stable({k:v for k,v in start.items() if k != "start_entry_sha256"}): raise HardStop("request-start hash drift")
        for key in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index"):
            if record.get(key) != planned.get(key): raise HardStop("non-prefix ledger")
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous or record.get("ledger_entry_sha256") != stable({k:v for k,v in record.items() if k != "ledger_entry_sha256"}) or record.get("terminal"): raise HardStop("ledger chain is not resumable")
        exact = usage(record); call_cost = cost(exact)
        if record.get("local_cost_cny") != call_cost: raise HardStop("per-call cost drift")
        total = round(total + call_cost, 6)
        if record.get("cumulative_local_cost_cny") != total: raise HardStop("cumulative cost drift")
        previous, previous_start = record["ledger_entry_sha256"], start["start_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization(); rows = load(SCHEDULE)["schedule"]; records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []; validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        if known_cost(records) >= min(STAGE_CEILING, CUMULATIVE_CEILING): raise HardStop("cost ceiling reached before next attempt")
        row = rows[len(records)]; body = deepcopy(row["canonical_request_body"])
        if row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type":"json_object"}: raise HardStop("request boundary drift")
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0: time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts)+1, "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "request_body_sha256": stable(body), "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}; start["start_entry_sha256"] = stable(start); starts.append(start); write(PACING, starts)
        base = {k: row[k] for k in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index")}; base.update({"provider_attempt_index": len(records)+1, "authorization_id": AUTH_ID, "authorization_sha256": auth_sha, "authorized_stage": "post_v23_replication", "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None})
        try:
            response = provider(body); exact = usage(response); content = response["content"]; call_cost = cost(exact); record = {**base, "request_id": response.get("request_id"), "raw_response": content, "raw_response_sha256": stable(content), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "local_cost_cny": call_cost, "cumulative_local_cost_cny": round(known_cost(records)+call_cost, 6), "terminal": False, "status": "completed", "error": None}
        except Exception as exc:
            response = locals().get("response"); maybe = response.get("usage") if isinstance(response, dict) and isinstance(response.get("usage"), dict) else None; record = {**base, "request_id": response.get("request_id") if isinstance(response, dict) else None, "raw_response": response.get("content") if isinstance(response, dict) else None, "raw_response_sha256": stable(response.get("content") if isinstance(response, dict) else None), "raw_provider_response": response, "usage": maybe, "local_cost_cny": cost(maybe) if maybe else None, "cumulative_local_cost_cny": round(known_cost(records)+(cost(maybe) if maybe else 0), 6) if maybe else None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        record["ledger_entry_sha256"] = stable(record); records.append(record); write(LEDGER, records)
        if record["terminal"]: raise HardStop(record["error"])
        if known_cost(records) >= min(STAGE_CEILING, CUMULATIVE_CEILING) and len(records) < CALLS: raise HardStop("cost ceiling reached")
    return records


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]; records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []; auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha: raise HardStop("ledger exists without authorization")
    if auth_sha: validate_prefix(records, starts, rows, auth_sha) if records and not records[-1].get("terminal") else None
    known = [r for r in records if isinstance(r.get("usage"), dict)]; request_ids = [r.get("request_id") for r in records if r.get("request_id")]
    result = {"schema_version": VERSION, "stage": "post_v23_replication", "status": "completed" if len(records)==CALLS and not (records and records[-1].get("terminal")) else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete", "planned_calls": CALLS, "provider_attempts": len(starts), "completed_calls": sum(r.get("status")=="completed" for r in records), "unique_logical_requests": len({r.get("logical_call_id") for r in records}), "unique_request_hashes": len({r.get("request_hash") for r in records}), "unique_provider_request_ids": len(set(request_ids)), "terminal_rows": sum(bool(r.get("terminal")) for r in records), "input_tokens": sum(usage(r)["input_tokens"] for r in known), "output_tokens": sum(usage(r)["output_tokens"] for r in known), "total_tokens": sum(usage(r)["total_tokens"] for r in known), "usage_status": "exact" if len(known)==len(records) else "known_lower_bound", "exact_local_cost_cny": known_cost(records) if len(known)==len(records) else None, "known_local_cost_lower_bound_cny": known_cost(records), "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "retries": sum(r.get("retries",0) for r in records), "duplicates": len(records)-len({r.get("logical_call_id") for r in records}), "max_tokens_present": any(r.get("max_tokens_present") for r in records), "model_id": "qwen3.7-plus", "temperature": 0, "request_start_pacing_valid": all(b["request_started_at_unix_ns"]-a["request_started_at_unix_ns"] >= INTERVAL_NS for a,b in zip(starts,starts[1:])), "ledger_hash_chain_valid": True, "request_start_hash_chain_valid": True, "exact_prefix_resume_valid": True, "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts), "calibration_calls": 0, "development_calls": 0, "formal_history_calls": 0, "probe_calls": 0, "held_out_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0, "authorization_closed": AUTH_CLOSED.exists() and CLOSURE.exists()}
    write(RUN_AUDIT, result); return result


def close(reason: str) -> dict[str, Any]:
    result = audit(); closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None, "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "exact_local_cost_cny": result["exact_local_cost_cny"], "known_local_cost_lower_bound_cny": result["known_local_cost_lower_bound_cny"], "post_v23_replication_calls": result["provider_attempts"], "calibration_calls": 0, "development_calls": 0, "formal_history_calls": 0, "probe_calls": 0, "held_out_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0, "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}; write(CLOSURE, closure); write(AUTH_CLOSED, closure); result["authorization_closed"] = True; write(RUN_AUDIT, result); return closure


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close")); args = parser.parse_args()
    if args.command == "preflight": result = preflight(); write(PREFLIGHT_AUDIT, result)
    elif args.command == "authorize": result = open_authorization()
    elif args.command == "audit": result = audit()
    elif args.command == "close": result = close("operator_close")
    else:
        try: result = {"rows": len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))), "closure": close("completed_exact_320")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists(): close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
