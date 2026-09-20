#!/usr/bin/env python3
"""Authorization-gated Phase 2 v14 probe-only live runner."""
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
from scripts.analyze_acl2027_phase2_probe_v3 import build_probe_audit
from scripts.run_acl2027_phase2_probe_only_preflight_v14 import CONFIG, CANDIDATE, SCHEDULE, load, validate as validate_preflight
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage

VERSION = 14
CALLS = 160
COST_CEILING = 7.5
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase2-probe-only-token-plan-v14"
AUTH = ROOT / "configs/acl2027/phase2_probe_only_authorization_v14.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_only_live_v14"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
PROBE_AUDIT = ARTIFACT / "probe_audit.json"
RUN_AUDIT = ARTIFACT / "run_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def probe_rows() -> list[dict[str, Any]]:
    return [row for row in load(SCHEDULE)["schedule"] if row.get("partition") == "probe"]


def authorization_template(key: str) -> dict[str, Any]:
    preflight = validate_preflight()
    return {
        "schema_version": VERSION, "experiment": "acl2027_phase2_probe_only_live_v14",
        "authorization_id": AUTH_ID, "status": "open",
        "bindings": {"preflight_config_sha256": sha256_file(CONFIG), "preflight_aggregate_fingerprint": preflight["aggregate_fingerprint"], "v4_aggregate_fingerprint": preflight["v4_aggregate_fingerprint"], "v13_aggregate_fingerprint": preflight["v13_aggregate_fingerprint"], "schedule_sha256": sha256_file(SCHEDULE), "candidate_sha256": sha256_file(CANDIDATE), "live_runner_sha256": sha256_file(Path(__file__).resolve())},
        "credential_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "user_authorization": {"scope": "phase2_probe_only", "authorized_calls": CALLS, "held_out_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False},
        "authorized_stage": "probe", "authorized_calls": CALLS, "stage_call_ceiling": CALLS,
        "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": COST_CEILING,
        "cumulative_cost_ceiling_cny": COST_CEILING, "model_id": "qwen3.7-plus",
        "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False,
        "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True,
        "formal_scaling_allowed": False, "forbidden_stages": ["held_out", "formal_scaling", "later_phase2_stages"],
    }


def open_authorization() -> dict[str, Any]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY missing")
    if LEDGER.exists() or PACING.exists() or CLOSURE.exists():
        raise HardStop("v14 live artifact already started or closed")
    auth = authorization_template(key)
    if AUTH.exists() and load(AUTH) != auth:
        raise HardStop("existing v14 authorization drift")
    write(AUTH, auth)
    write(REGISTRY, {"schema_version": VERSION, "authorizations": {AUTH_ID: {"path": str(AUTH.relative_to(ARTIFACT.parent.parent)).replace("\\", "/"), "sha256": sha256_file(AUTH)}}})
    return auth


def validate_authorization() -> tuple[dict[str, Any], str]:
    validate_preflight()
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.is_file() or not REGISTRY.is_file() or CLOSURE.exists():
        raise HardStop("v14 live authorization is closed or absent")
    auth = load(AUTH)
    if auth != authorization_template(key):
        raise HardStop("v14 authorization boundary drift")
    item = load(REGISTRY).get("authorizations", {}).get(AUTH_ID)
    if not item or item.get("sha256") != sha256_file(AUTH):
        raise HardStop("v14 authorization registry drift")
    return auth, item["sha256"]


def seal(record: dict[str, Any]) -> None:
    record["ledger_entry_sha256"] = stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"})


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records):
        raise HardStop("v14 ambiguous request start; retry forbidden", records)
    if len({r.get("logical_call_id") for r in records}) != len(records) or len({r.get("request_hash") for r in records}) != len(records):
        raise HardStop("v14 duplicate logical request", records)
    previous = None
    for planned, record in zip(rows, records):
        for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "staged_execution_index"):
            if record.get(key) != planned.get(key):
                raise HardStop("v14 non-prefix probe ledger", records)
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous:
            raise HardStop("v14 authorization or hash-chain drift", records)
        if record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}):
            raise HardStop("v14 ledger hash-chain drift", records)
        if record.get("terminal"):
            raise HardStop("v14 terminal ledger is not resumable", records)
        usage(record)
        previous = record["ledger_entry_sha256"]


def cost(records: list[dict[str, Any]]) -> float:
    return round(sum(usage(r)["input_tokens"] * 2.0 + usage(r)["output_tokens"] * 8.0 for r in records) / 1_000_000, 6)


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]], *, interrupt_after: int | None = None) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization()
    rows = probe_rows()
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        row = rows[len(records)]
        body = deepcopy(row["canonical_request_body"])
        body["response_format"] = {"type": "json_object"}
        if "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0:
            raise HardStop("v14 request boundary drift", records)
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0:
                time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts) + 1, "request_body_sha256": stable(body), "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start)
        starts.append(start); write(PACING, starts)
        base = {k: row[k] for k in ("logical_call_id", "request_hash", "partition", "task_id", "skill_family", "condition", "payload_hash", "staged_execution_index")}
        base.update(authorization_id=AUTH_ID, authorization_sha256=auth_sha, authorized_stage="probe", retries=0, max_tokens_present=False, previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None)
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            raw = response.get("content")
            if not isinstance(raw, str):
                raise HardStop("v14 provider response missing content")
            record = {**base, "request_id": response.get("request_id"), "raw_response": raw, "raw_response_sha256": stable(raw), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "terminal": False, "status": "completed", "error": None}
        except Exception as exc:
            record = {**base, "request_id": None, "raw_response": response.get("content") if isinstance(response, dict) else None, "raw_response_sha256": stable(response.get("content") if isinstance(response, dict) else None), "raw_provider_response": response.get("raw_provider_response", response) if isinstance(response, dict) else response, "usage": response.get("usage") if isinstance(response, dict) else None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        seal(record); records.append(record); write(LEDGER, records)
        if interrupt_after is not None and len(records) == interrupt_after:
            raise KeyboardInterrupt("simulated interruption after durable append")
        if record["terminal"]:
            raise HardStop(record["error"], records)
        if cost(records) > COST_CEILING:
            records[-1].update(terminal=True, status="hard_stop", error="v14 cost ceiling exceeded"); seal(records[-1]); write(LEDGER, records)
            raise HardStop(records[-1]["error"], records)
    return records


def audit() -> dict[str, Any]:
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    terminal = bool(records and records[-1].get("terminal"))
    if len(starts) != len(records):
        raise HardStop("v14 pacing ledger count drift")
    probe_audit = None
    if len(records) == CALLS and not terminal:
        probe_audit = build_probe_audit(records, load(SCHEDULE)["schedule"], load(CANDIDATE), sha256_file(CANDIDATE), load(V4_CONFIG), root=ROOT)
        write(PROBE_AUDIT, probe_audit)
    known = [r for r in records if isinstance(r.get("usage"), dict)]
    result = {"schema_version": VERSION, "status": "completed" if probe_audit else "terminal_hard_stop" if terminal else "incomplete", "planned_calls": CALLS, "provider_attempts": len(records), "unique_logical_requests": len({r.get("logical_call_id") for r in records}), "completed_calls": sum(r.get("status") == "completed" for r in records), "terminal_rows": sum(bool(r.get("terminal")) for r in records), "input_tokens": sum(usage(r)["input_tokens"] for r in known), "output_tokens": sum(usage(r)["output_tokens"] for r in known), "total_tokens": sum(usage(r)["total_tokens"] for r in known), "exact_local_cost_cny": cost(known), "retries": sum(r.get("retries", 0) for r in records), "duplicates": len(records) - len({r.get("logical_call_id") for r in records}), "max_tokens_present": any(r.get("max_tokens_present") for r in records), "model_id": "qwen3.7-plus", "temperature": 0, "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])), "probe_gate_passed": probe_audit.get("passed") if probe_audit else False, "condition_accuracy": probe_audit.get("condition_accuracy", {}) if probe_audit else {}, "held_out_calls": 0, "formal_scaling_calls": 0, "authorization_closed": CLOSURE.exists()}
    write(RUN_AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None, "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "exact_local_cost_cny": result["exact_local_cost_cny"], "held_out_calls": 0, "formal_scaling_calls": 0, "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}
    write(CLOSURE, closure)
    result["authorization_closed"] = True; write(RUN_AUDIT, result)
    return closure


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = validate_preflight()
    elif args.command == "authorize":
        result = open_authorization()
    elif args.command == "audit":
        result = audit()
    elif args.command == "close":
        result = close("operator_close")
    else:
        try:
            records = execute(QwenTokenPlanProviderAdapter(validate_authorization()[0]))
            result = {"rows": len(records), "closure": close("completed_exact_160")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
