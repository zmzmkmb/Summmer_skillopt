#!/usr/bin/env python3
"""Authorization-gated live runner for the immutable v28 recovery schedule."""
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

VERSION = 29
CALLS = 528
STAGE_CEILING = 3.0
CUMULATIVE_CEILING = 8.0
V27_KNOWN_COST_LOWER = 4.6268
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase2-post-v25-failure-analysis-recovery-v29"
RECEIPT = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_recovery_user_authorization_receipt_v29.json"
V28_CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_recovery_preflight_v28.json"
V28_ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v28"
MANIFEST = V28_ARTIFACT / "run_manifest.json"
SCHEDULE = V28_ARTIFACT / "failure_analysis_recovery_schedule.json"
GOLD = V28_ARTIFACT / "combined_private_gold.json"
V27_LEDGER = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27/ledger.json"
V27_CLOSURE = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27/authorization_closure.json"
V27_CORRECTED = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27/run_audit_v27_1.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ANALYZER = ROOT / "scripts/analyze_acl2027_phase2_post_v25_failure_analysis_recovery_v29.py"
TEST = ROOT / "tests/test_acl2027_phase2_post_v25_failure_analysis_recovery_live_v29.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_live_v29"
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
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def cost(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * 2.0 + value["output_tokens"] * 8.0) / 1_000_000, 6)


def known_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(row.get("local_cost_cny") or 0.0 for row in records), 6)


def exact_contract() -> dict[str, Any]:
    return {"scope": "post_v25_failure_analysis_recovery_only", "authorized_stage": "post_v25_failure_analysis_recovery", "authorized_calls": CALLS, "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "enable_thinking": False, "response_format": {"type": "json_object"}, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "v27_known_cost_lower_bound_cny": V27_KNOWN_COST_LOWER, "later_stages_authorized": False, "formal_scaling_authorized": False}


def preflight() -> dict[str, Any]:
    cfg, manifest, rows, receipt = load(V28_CONFIG), load(MANIFEST), load(SCHEDULE)["schedule"], load(RECEIPT)
    expected_fingerprint = "63f64eb6d3854198c03f0cfdfd0905f803a78ed10d6d4a2d150f351323006640"
    if manifest.get("aggregate_fingerprint") != expected_fingerprint or manifest.get("status") != "preflight-passed-recovery-plan-closed":
        raise HardStop("v28 manifest boundary drift")
    if any(value is not False for value in cfg.get("execution", {}).values()):
        raise HardStop("v28 must remain execution-closed")
    if receipt.get("status") != "explicit_user_authorization_received_execution_not_open" or receipt.get("v28_aggregate_fingerprint") != expected_fingerprint or any(receipt.get(key) != value for key, value in exact_contract().items()):
        raise HardStop("v29 receipt boundary drift")
    expected_bindings = {"v28_manifest_sha256": sha256_file(MANIFEST), "v28_schedule_sha256": sha256_file(SCHEDULE), "v28_gold_sha256": sha256_file(GOLD)}
    if receipt.get("bindings") != expected_bindings:
        raise HardStop("v29 receipt binding drift")
    if any(receipt.get("execution", {}).get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v29 receipt is not execution-closed")
    if len(rows) != CALLS or len({row["logical_call_id"] for row in rows}) != CALLS or len({row["request_hash"] for row in rows}) != CALLS:
        raise HardStop("v28 recovery schedule identity drift")
    spent = load(V27_LEDGER)
    if {row["logical_call_id"] for row in rows} & {row["logical_call_id"] for row in spent} or {row["request_hash"] for row in rows} & {row["request_hash"] for row in spent}:
        raise HardStop("v29 retries a spent v27 request")
    if load(V27_CLOSURE).get("status") != "closed" or load(V27_CORRECTED).get("analysis_gate_reached") is not False:
        raise HardStop("v27 terminal provenance drift")
    for index, row in enumerate(rows, 1):
        body = row["canonical_request_body"]
        if row.get("staged_execution_index") != index or row.get("partition") != "independent_failure_analysis_held_out_recovery" or row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False:
            raise HardStop("v28 recovery route/prefix drift")
    bindings = {"receipt_sha256": sha256_file(RECEIPT), "v28_config_sha256": sha256_file(V28_CONFIG), "v28_manifest_sha256": sha256_file(MANIFEST), "v28_schedule_sha256": sha256_file(SCHEDULE), "v28_gold_sha256": sha256_file(GOLD), "v27_ledger_sha256": sha256_file(V27_LEDGER), "v27_closure_sha256": sha256_file(V27_CLOSURE), "v27_corrected_audit_sha256": sha256_file(V27_CORRECTED), "provider_adapter_sha256": sha256_file(ADAPTER), "analyzer_sha256": sha256_file(ANALYZER), "test_sha256": sha256_file(TEST), "live_runner_sha256": sha256_file(Path(__file__).resolve())}
    return {"schema_version": VERSION, "status": "zero-network-preflight-passed", "v28_aggregate_fingerprint": expected_fingerprint, "authorized_calls": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "v27_known_cost_lower_bound_cny": V27_KNOWN_COST_LOWER, "bindings": bindings, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "later_stages_authorized": False, "formal_scaling_authorized": False}


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {"schema_version": VERSION, "experiment": "acl2027_phase2_post_v25_failure_analysis_recovery_live_v29", "authorization_id": AUTH_ID, "status": "open", "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": stable(gate)}, "credential_sha256": hashlib.sha256(key.encode()).hexdigest(), **exact_contract(), "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "request_interval_seconds": 1.0, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "formal_scaling_allowed": False, "forbidden_stages": ["calibration", "development_acquisition", "formal_history", "probe", "held_out", "other_models", "later_phase2_stages", "formal_scaling"]}


def open_authorization() -> dict[str, Any]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY missing")
    if any(path.exists() for path in (AUTH, AUTH_CLOSED, REGISTRY, LEDGER, PACING, CLOSURE)):
        raise HardStop("v29 authorization already opened, started, or closed")
    gate = preflight()
    write(PREFLIGHT_AUDIT, gate)
    write(AUTH, authorization_template(key))
    write(REGISTRY, {"schema_version": VERSION, "authorizations": {AUTH_ID: {"path": AUTH.name, "sha256": sha256_file(AUTH)}}})
    return load(AUTH)


def validate_authorization() -> tuple[dict[str, Any], str]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.is_file() or not REGISTRY.is_file() or AUTH_CLOSED.exists() or CLOSURE.exists():
        raise HardStop("v29 authorization is closed or absent")
    auth = load(AUTH)
    if auth != authorization_template(key):
        raise HardStop("v29 authorization drift")
    item = load(REGISTRY)["authorizations"].get(AUTH_ID)
    if not item or item.get("sha256") != sha256_file(AUTH):
        raise HardStop("v29 authorization registry drift")
    return auth, item["sha256"]


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records):
        raise HardStop("ambiguous request start; retry forbidden")
    previous = previous_start = None
    total = 0.0
    provider_ids: set[str] = set()
    for planned, record, start in zip(rows, records, starts):
        if start.get("logical_call_id") != planned["logical_call_id"] or start.get("request_hash") != planned["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous_start or start.get("request_body_sha256") != stable(planned["canonical_request_body"]):
            raise HardStop("request-start binding drift")
        if start.get("start_entry_sha256") != stable({key: value for key, value in start.items() if key != "start_entry_sha256"}):
            raise HardStop("request-start hash drift")
        for key in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index"):
            if record.get(key) != planned.get(key):
                raise HardStop("non-prefix ledger")
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous or record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}) or record.get("terminal"):
            raise HardStop("ledger chain is not resumable")
        request_id = record.get("request_id")
        if not request_id or request_id in provider_ids:
            raise HardStop("missing or duplicate provider response id")
        provider_ids.add(request_id)
        exact = usage(record)
        call_cost = cost(exact)
        if record.get("local_cost_cny") != call_cost:
            raise HardStop("per-call cost drift")
        total = round(total + call_cost, 6)
        if record.get("cumulative_local_cost_cny") != total:
            raise HardStop("cumulative cost drift")
        previous, previous_start = record["ledger_entry_sha256"], start["start_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization()
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        if known_cost(records) >= STAGE_CEILING or V27_KNOWN_COST_LOWER + known_cost(records) >= CUMULATIVE_CEILING:
            raise HardStop("cost ceiling reached before next attempt")
        row = rows[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"}:
            raise HardStop("request boundary drift")
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0:
                time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts) + 1, "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "request_body_sha256": stable(body), "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(PACING, starts)
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index")}
        base.update({"provider_attempt_index": len(records) + 1, "authorization_id": AUTH_ID, "authorization_sha256": auth_sha, "authorized_stage": "post_v25_failure_analysis_recovery", "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None})
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            content = response["content"]
            call_cost = cost(exact)
            record = {**base, "request_id": response.get("request_id"), "raw_response": content, "raw_response_sha256": stable(content), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "local_cost_cny": call_cost, "cumulative_local_cost_cny": round(known_cost(records) + call_cost, 6), "terminal": False, "status": "completed", "error": None}
            if not record["request_id"] or record["request_id"] in {item.get("request_id") for item in records}:
                raise HardStop("missing or duplicate provider response id")
        except Exception as exc:
            record = {**base, "request_id": None, "raw_response": None, "raw_response_sha256": stable(None), "raw_provider_response": None, "usage": None, "local_cost_cny": None, "cumulative_local_cost_cny": None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        record["ledger_entry_sha256"] = stable(record)
        records.append(record)
        write(LEDGER, records)
        if record["terminal"]:
            raise HardStop(record["error"])
        if (known_cost(records) >= STAGE_CEILING or V27_KNOWN_COST_LOWER + known_cost(records) >= CUMULATIVE_CEILING) and len(records) < CALLS:
            raise HardStop("cost ceiling reached")
    return records


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha:
        raise HardStop("ledger exists without authorization")
    if auth_sha and records and not records[-1].get("terminal"):
        validate_prefix(records, starts, rows, auth_sha)
    known = [record for record in records if isinstance(record.get("usage"), dict)]
    request_ids = [record.get("request_id") for record in records if record.get("request_id")]
    complete = len(records) == CALLS and not (records and records[-1].get("terminal"))
    result = {"schema_version": VERSION, "stage": "post_v25_failure_analysis_recovery", "status": "completed" if complete else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete", "planned_calls": CALLS, "provider_attempts": len(starts), "completed_calls": sum(record.get("status") == "completed" for record in records), "unique_logical_requests": len({record.get("logical_call_id") for record in records}), "unique_request_hashes": len({record.get("request_hash") for record in records}), "unique_provider_request_ids": len(set(request_ids)), "terminal_rows": sum(bool(record.get("terminal")) for record in records), "input_tokens": sum(usage(record)["input_tokens"] for record in known), "output_tokens": sum(usage(record)["output_tokens"] for record in known), "total_tokens": sum(usage(record)["total_tokens"] for record in known), "usage_status": "exact" if len(known) == len(records) else "known_lower_bound", "exact_stage_cost_cny": known_cost(records) if len(known) == len(records) else None, "known_stage_cost_lower_bound_cny": known_cost(records), "v27_known_cost_lower_bound_cny": V27_KNOWN_COST_LOWER, "exact_cumulative_cost_cny": None, "known_cumulative_cost_lower_bound_cny": round(V27_KNOWN_COST_LOWER + known_cost(records), 6), "stage_cost_ceiling_cny": STAGE_CEILING, "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING, "retries": sum(record.get("retries", 0) for record in records), "duplicates": len(records) - len({record.get("logical_call_id") for record in records}), "max_tokens_present": any(record.get("max_tokens_present") for record in records), "model_id": "qwen3.7-plus", "temperature": 0, "request_start_pacing_valid": all(second["request_started_at_unix_ns"] - first["request_started_at_unix_ns"] >= INTERVAL_NS for first, second in zip(starts, starts[1:])), "ledger_hash_chain_valid": True, "request_start_hash_chain_valid": True, "exact_prefix_resume_valid": True, "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts), "recovery_calls": len(starts), "later_stage_calls": 0, "formal_scaling_calls": 0, "authorization_closed": AUTH_CLOSED.exists() and CLOSURE.exists()}
    write(RUN_AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None, "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "exact_stage_cost_cny": result["exact_stage_cost_cny"], "known_stage_cost_lower_bound_cny": result["known_stage_cost_lower_bound_cny"], "known_cumulative_cost_lower_bound_cny": result["known_cumulative_cost_lower_bound_cny"], "recovery_calls": result["provider_attempts"], "later_stage_calls": 0, "formal_scaling_calls": 0, "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}
    write(CLOSURE, closure)
    write(AUTH_CLOSED, closure)
    result["authorization_closed"] = True
    write(RUN_AUDIT, result)
    return closure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = preflight()
        write(PREFLIGHT_AUDIT, result)
    elif args.command == "authorize":
        result = open_authorization()
    elif args.command == "audit":
        result = audit()
    elif args.command == "close":
        result = close("operator_close")
    else:
        try:
            result = {"rows": len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))), "closure": close("completed_exact_528")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
