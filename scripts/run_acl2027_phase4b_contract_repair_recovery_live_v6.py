#!/usr/bin/env python3
"""Authorization-gated live runner for the immutable Phase 4B-R4 recovery schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage
from scripts import run_acl2027_phase4b_contract_repair_recovery_preflight_v4 as recovery

VERSION, CALLS = 6, 28
R4_FINGERPRINT = "fc668155d0e1d787fe45bf381f5958d8f9d5d78759be3c0bab3951580254f066"
R5_FINGERPRINT = "4b220ba56d8cf0990ecf86df791f79b8218db427c81a117b6c78a775d58f5a0d"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
STAGE_CEILING, CUMULATIVE_CEILING = 0.30, 15.00
KNOWN_CUMULATIVE, ORPHAN_RESERVE = 12.328920, 0.011136
CONSERVATIVE_PRIOR = round(KNOWN_CUMULATIVE + ORPHAN_RESERVE, 6)
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase4b-contract-repair-recovery-live-v6"

PREFLIGHT = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_live_preflight_v5"
PREFLIGHT_MANIFEST = PREFLIGHT / "run_manifest.json"
PREFLIGHT_REQUEST = PREFLIGHT / "authorization_request.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_preflight_v4/recovery_schedule.json"
R3_STARTS = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3/request_start_ledger.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
RECEIPT = ROOT / "configs/acl2027/phase4b_contract_repair_recovery_user_authorization_receipt_v6.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_live_v6"
AUTH = ARTIFACT / "authorization_open.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
STARTS = ARTIFACT / "request_start_ledger.json"
LEDGER = ARTIFACT / "ledger.json"
AUDIT = ARTIFACT / "run_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def contract() -> dict[str, Any]:
    return {
        "scope": "phase4b_repaired_development_calibration_recovery_only",
        "endpoint": ENDPOINT,
        "authorized_calls": CALLS,
        "max_provider_attempts": CALLS,
        "model_id": "qwen3.7-plus",
        "temperature": 0,
        "enable_thinking": False,
        "retries": 0,
        "max_tokens_present": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "stage_cost_ceiling_cny": STAGE_CEILING,
        "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING,
        "known_cumulative_cost_lower_bound_cny": KNOWN_CUMULATIVE,
        "orphan_usage_reserve_cny": ORPHAN_RESERVE,
        "projected_known_upper_bound_cny": 12.640056,
        "cost_policy": "Reserve the maximum observed completed-response local cost for the unknown orphan; stop before the new stage exceeds CNY 0.30 or cumulative spend exceeds CNY 15.00.",
        "terminal_stop_on_first_failed_attempt": True,
        "authorization_closes_on_completion_or_terminal_stop": True,
        "usage_accounting_required": True,
        "request_start_ledger_required": True,
        "response_ledger_required": True,
        "hash_chain_required": True,
        "exact_prefix_resume_only": True,
    }


def bindings() -> dict[str, str]:
    return {
        "preflight_manifest_sha256": sha256_file(PREFLIGHT_MANIFEST),
        "preflight_request_sha256": sha256_file(PREFLIGHT_REQUEST),
        "schedule_sha256": sha256_file(SCHEDULE),
        "r3_request_start_ledger_sha256": sha256_file(R3_STARTS),
        "adapter_sha256": sha256_file(ADAPTER),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def preflight() -> list[dict[str, Any]]:
    manifest, request = load(PREFLIGHT_MANIFEST), load(PREFLIGHT_REQUEST)
    if manifest.get("aggregate_fingerprint") != R5_FINGERPRINT:
        raise HardStop("R5 preflight fingerprint drift")
    if request.get("preflight_aggregate_fingerprint") != R5_FINGERPRINT or request.get("source_recovery_fingerprint") != R4_FINGERPRINT:
        raise HardStop("R5 authorization request binding drift")
    if request.get("execution_contract") != contract():
        raise HardStop("R5 execution contract drift")
    rows = load(SCHEDULE).get("rows", [])
    if len(rows) != CALLS or len({row.get("logical_call_id") for row in rows}) != CALLS or len({row.get("request_hash") for row in rows}) != CALLS:
        raise HardStop("R4 recovery identity drift")
    spent = load(R3_STARTS)
    spent_logical = {str(row["logical_call_id"]) for row in spent}
    spent_hashes = {str(row["request_hash"]) for row in spent}
    if spent_logical & {str(row["logical_call_id"]) for row in rows} or spent_hashes & {str(row["request_hash"]) for row in rows}:
        raise HardStop("R6 schedule reuses a spent R3 canonical identity")
    for row in rows:
        body = row.get("canonical_request_body", {})
        if row.get("request_hash") != stable(body) or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("enable_thinking") is not False or body.get("response_format") != {"type": "json_object"} or "max_tokens" in body:
            raise HardStop("R6 payload contract drift")
        projection = recovery.repair.transport_projection(body)
        if projection != row.get("transport_projection") or stable(projection) != row.get("transport_payload_hash"):
            raise HardStop("R6 transport projection drift")
    return rows


def receipt() -> dict[str, Any]:
    request = load(PREFLIGHT_REQUEST)
    statement = request["authorization_statement_verbatim"]
    return {
        "schema_version": VERSION,
        "status": "explicit_user_authorization_received_execution_not_open",
        "authorization_source": "user_message_2026-08-18",
        "authorization_statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "authorization_statement_matches_preflight_verbatim": True,
        "source_recovery_fingerprint": R4_FINGERPRINT,
        "live_preflight_fingerprint": R5_FINGERPRINT,
        **contract(),
        "endpoint": ENDPOINT,
        "data_egress_authorized": True,
        "authorized_destination": ENDPOINT,
        "paid_usage_authorized": True,
        "forbidden_stages": ["phase4c", "other_models", "replication", "cross_domain_scaling", "formal_scaling"],
        "bindings": bindings(),
        "execution": {"network_calls_allowed": False, "provider_calls_allowed": False, "paid_api_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False},
    }


def authorize() -> dict[str, Any]:
    rows = preflight()
    if ARTIFACT.exists() or RECEIPT.exists():
        raise HardStop("R6 authorization or execution record already exists")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY missing")
    write(RECEIPT, receipt())
    opened = {
        "schema_version": VERSION, "authorization_id": AUTH_ID, "status": "open",
        "credential_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "receipt_sha256": sha256_file(RECEIPT), "rows": len(rows), **contract(),
        "endpoint": ENDPOINT, "data_egress_authorized": True, "paid_usage_authorized": True,
        "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True,
        "phase4c_allowed": False, "formal_scaling_allowed": False,
    }
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    write(AUTH, opened)
    write(REGISTRY, {"authorization_id": AUTH_ID, "authorization_sha256": sha256_file(AUTH)})
    return opened


def validate_open() -> tuple[list[dict[str, Any]], str]:
    rows = preflight()
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.exists() or not REGISTRY.exists() or CLOSURE.exists():
        raise HardStop("R6 authorization is not open")
    auth = load(AUTH)
    if auth.get("credential_sha256") != hashlib.sha256(key.encode()).hexdigest() or not all(auth.get(key) is True for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        raise HardStop("R6 open authorization drift")
    return rows, sha256_file(AUTH)


def total_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(record.get("local_cost_cny") or 0.0 for record in records), 6)


def call_cost(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * 2 + value["output_tokens"] * 8) / 1_000_000, 6)


def validate_prefix(rows: list[dict[str, Any]], starts: list[dict[str, Any]], records: list[dict[str, Any]], auth_sha: str) -> None:
    if len(starts) != len(records) or len(records) > CALLS:
        raise HardStop("ambiguous R6 request prefix")
    previous_start = previous_record = None
    for row, start, record in zip(rows, starts, records):
        if start.get("logical_call_id") != row["logical_call_id"] or start.get("request_hash") != row["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous_start or start.get("start_entry_sha256") != stable({key: value for key, value in start.items() if key != "start_entry_sha256"}):
            raise HardStop("R6 request-start chain drift")
        if record.get("logical_call_id") != row["logical_call_id"] or record.get("request_hash") != row["request_hash"] or record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous_record or record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("R6 response-ledger chain drift")
        if record.get("terminal"):
            raise HardStop("terminal R6 attempt cannot be resumed")
        previous_start, previous_record = start["start_entry_sha256"], record["ledger_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    rows, auth_sha = validate_open()
    starts = load(STARTS) if STARTS.exists() else []
    records = load(LEDGER) if LEDGER.exists() else []
    validate_prefix(rows, starts, records, auth_sha)
    while len(records) < CALLS:
        if total_cost(records) >= STAGE_CEILING or CONSERVATIVE_PRIOR + total_cost(records) >= CUMULATIVE_CEILING:
            raise HardStop("R6 cost ceiling reached")
        row, body = rows[len(records)], deepcopy(rows[len(records)]["canonical_request_body"])
        if starts:
            remaining = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if remaining > 0:
                time.sleep(remaining / 1_000_000_000)
        start = {
            "sequence": len(starts) + 1, "logical_call_id": row["logical_call_id"],
            "request_hash": row["request_hash"], "request_body_sha256": stable(body),
            "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(),
            "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None,
        }
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(STARTS, starts)
        base = {key: row.get(key) for key in ("logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "condition", "source_sequence", "recovery_kind")}
        base.update({
            "provider_attempt_index": len(records) + 1, "authorization_id": AUTH_ID,
            "authorization_sha256": auth_sha, "model_id": "qwen3.7-plus", "temperature": 0,
            "retries": 0, "max_tokens_present": False,
            "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None,
        })
        try:
            response = provider(body)
            exact = usage(response)
            request_id = response.get("request_id")
            if not request_id or request_id in {record.get("request_id") for record in records}:
                raise HardStop("missing or duplicate R6 provider request id")
            cost = call_cost(exact)
            record = {
                **base, "request_id": request_id, "raw_response": response["content"],
                "raw_response_sha256": stable(response["content"]),
                "raw_provider_response": response.get("raw_provider_response", response),
                "usage": exact, "local_cost_cny": cost,
                "cumulative_local_cost_cny": round(total_cost(records) + cost, 6),
                "terminal": False, "status": "completed", "error": None,
            }
        except Exception as exc:
            record = {
                **base, "request_id": None, "raw_response": None, "raw_response_sha256": stable(None),
                "raw_provider_response": None, "usage": None, "local_cost_cny": None,
                "cumulative_local_cost_cny": None, "terminal": True, "status": "hard_stop",
                "error": f"{type(exc).__name__}: {exc}",
            }
        record["ledger_entry_sha256"] = stable(record)
        records.append(record)
        write(LEDGER, records)
        if record["terminal"]:
            raise HardStop(record["error"])
    return records


def audit() -> dict[str, Any]:
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(STARTS) if STARTS.exists() else []
    known = [record for record in records if isinstance(record.get("usage"), dict)]
    complete = len(records) == CALLS and all(not record.get("terminal") for record in records)
    stage = total_cost(records)
    result = {
        "schema_version": VERSION, "status": "completed" if complete else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete",
        "planned_calls": CALLS, "provider_attempts": len(starts), "completed_calls": len(known),
        "terminal_rows": sum(bool(record.get("terminal")) for record in records),
        "input_tokens": sum(usage(record)["input_tokens"] for record in known),
        "output_tokens": sum(usage(record)["output_tokens"] for record in known),
        "total_tokens": sum(usage(record)["total_tokens"] for record in known),
        "exact_stage_cost_cny": stage if len(known) == len(records) else None,
        "known_cumulative_cost_lower_bound_cny": round(KNOWN_CUMULATIVE + stage, 6),
        "conservative_cumulative_with_orphan_reserve_cny": round(CONSERVATIVE_PRIOR + stage, 6),
        "orphan_usage_reserve_cny": ORPHAN_RESERVE, "retries": 0,
        "request_start_pacing_valid": all(later["request_started_at_unix_ns"] - earlier["request_started_at_unix_ns"] >= INTERVAL_NS for earlier, later in zip(starts, starts[1:])),
        "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts),
        "paid_api_calls": len(starts), "phase4c_calls": 0, "replication_calls": 0,
        "cross_domain_scaling_calls": 0, "formal_scaling_calls": 0,
        "authorization_closed": CLOSURE.exists(),
    }
    write(AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {
        "schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason,
        "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"],
        "known_cumulative_cost_lower_bound_cny": result["known_cumulative_cost_lower_bound_cny"],
        "conservative_cumulative_with_orphan_reserve_cny": result["conservative_cumulative_with_orphan_reserve_cny"],
        "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False,
        "phase4c_allowed": False, "formal_scaling_allowed": False,
    }
    write(CLOSURE, closure)
    result["authorization_closed"] = True
    write(AUDIT, result)
    return closure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = {"rows": len(preflight()), "bindings": bindings(), "network_calls": 0}
    elif args.command == "authorize":
        result = authorize()
    elif args.command == "audit":
        result = audit()
    elif args.command == "close":
        result = close("operator_close")
    else:
        try:
            result = {"rows": len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))), "closure": close("completed_exact_28")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
