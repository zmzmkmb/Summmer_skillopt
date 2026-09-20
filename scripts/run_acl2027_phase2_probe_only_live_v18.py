#!/usr/bin/env python3
"""Authorization-gated live runner for the v17 replacement probe schedule."""
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
from scripts.analyze_acl2027_phase2_probe_replacement_v18 import build_probe_audit
from scripts.run_acl2027_phase2_probe_identifiable_schedule_preflight_v17 import validate as validate_v17
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage

VERSION = 18
CALLS = 160
COST_CEILING = 7.5
INPUT_CNY_PER_MILLION = 2.0
OUTPUT_CNY_PER_MILLION = 8.0
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase2-probe-only-identifiable-v18"

RECEIPT = ROOT / "configs/acl2027/phase2_probe_only_user_authorization_receipt_v18.json"
REQUEST = ROOT / "configs/acl2027/phase2_probe_only_authorization_request_v17.json"
AUTH = ROOT / "configs/acl2027/phase2_probe_only_live_authorization_v18.json"
AUTH_CLOSED = ROOT / "configs/acl2027/phase2_probe_only_live_authorization_closed_v18.json"
V17_CONFIG = ROOT / "configs/acl2027/phase2_probe_identifiable_schedule_preflight_v17.json"
V17_ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17"
V17_MANIFEST = V17_ARTIFACT / "run_manifest.json"
SCHEDULE = V17_ARTIFACT / "probe_schedule.json"
PRIOR_BUNDLES = V17_ARTIFACT / "prior_bundles.json"
REPLACEMENT_GOLD = V17_ARTIFACT / "replacement_probe_gold.json"
CANDIDATE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/combined_candidates_v13.json"
PROVIDER_ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ANALYZER = ROOT / "scripts/analyze_acl2027_phase2_probe_replacement_v18.py"
TEST = ROOT / "tests/test_acl2027_phase2_probe_only_live_v18.py"

ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_only_live_v18"
PREFLIGHT_AUDIT = ARTIFACT / "zero_network_preflight.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
PROBE_AUDIT = ARTIFACT / "probe_audit.json"
RUN_AUDIT = ARTIFACT / "run_audit.json"
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


def local_cost_from_usage(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * INPUT_CNY_PER_MILLION + value["output_tokens"] * OUTPUT_CNY_PER_MILLION) / 1_000_000, 6)


def known_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(record.get("local_cost_cny") or 0.0 for record in records), 6)


def preflight() -> dict[str, Any]:
    v17 = validate_v17()
    request = load(REQUEST)
    receipt = load(RECEIPT)
    if v17.get("aggregate_fingerprint") != request.get("bindings", {}).get("preflight_aggregate_fingerprint"):
        raise HardStop("v18 v17 aggregate/request binding drift")
    if sha256_file(REQUEST) != receipt.get("request_binding", {}).get("sha256") or receipt.get("request_binding", {}).get("preflight_aggregate_fingerprint") != v17["aggregate_fingerprint"]:
        raise HardStop("v18 user authorization receipt binding drift")
    exact = {
        "scope": "probe_only", "authorized_stage": "probe", "authorized_calls": CALLS,
        "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0,
        "retries": 0, "max_tokens_present": False, "enable_thinking": False,
        "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": COST_CEILING,
        "held_out_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False,
    }
    if any(receipt.get(key) != value for key, value in exact.items()) or receipt.get("status") != "explicit_user_authorization_received_execution_not_open":
        raise HardStop("v18 user authorization boundary drift")
    if any(receipt.get("execution", {}).get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v18 receipt must remain execution-closed")
    expected_files = {
        "preflight_manifest_sha256": V17_MANIFEST,
        "preflight_schedule_sha256": SCHEDULE,
        "preflight_prior_bundles_sha256": PRIOR_BUNDLES,
        "preflight_replacement_gold_sha256": REPLACEMENT_GOLD,
    }
    if any(request["bindings"].get(name) != sha256_file(path) for name, path in expected_files.items()):
        raise HardStop("v18 v17 artifact binding drift")
    rows = load(SCHEDULE)["schedule"]
    if len(rows) != CALLS or len({row["logical_call_id"] for row in rows}) != CALLS or len({row["request_hash"] for row in rows}) != CALLS:
        raise HardStop("v18 schedule cardinality/identity drift")
    if any(
        row.get("staged_execution_index") != index
        or row.get("partition") != "probe"
        or row["request_hash"] != stable(row["canonical_request_body"])
        or "max_tokens" in row["canonical_request_body"]
        or row["canonical_request_body"].get("model_id") != "qwen3.7-plus"
        or row["canonical_request_body"].get("temperature") != 0
        or row["canonical_request_body"].get("response_format") != {"type": "json_object"}
        or row["canonical_request_body"].get("enable_thinking") is not False
        for index, row in enumerate(rows, 1)
    ):
        raise HardStop("v18 request route/prefix drift")
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise HardStop("DASHSCOPE_API_KEY missing")
    result = {
        "schema_version": VERSION,
        "status": "zero-network-preflight-passed",
        "authorized_calls": CALLS,
        "max_provider_attempts": CALLS,
        "stage_cost_ceiling_cny": COST_CEILING,
        "cumulative_cost_ceiling_cny": COST_CEILING,
        "v17_aggregate_fingerprint": v17["aggregate_fingerprint"],
        "bindings": {
            "authorization_receipt_sha256": sha256_file(RECEIPT),
            "authorization_request_sha256": sha256_file(REQUEST),
            "v17_config_sha256": sha256_file(V17_CONFIG),
            "v17_manifest_sha256": sha256_file(V17_MANIFEST),
            "schedule_sha256": sha256_file(SCHEDULE),
            "prior_bundles_sha256": sha256_file(PRIOR_BUNDLES),
            "replacement_gold_sha256": sha256_file(REPLACEMENT_GOLD),
            "candidate_sha256": sha256_file(CANDIDATE),
            "provider_adapter_sha256": sha256_file(PROVIDER_ADAPTER),
            "analyzer_sha256": sha256_file(ANALYZER),
            "live_runner_sha256": sha256_file(Path(__file__).resolve()),
            "live_test_sha256": sha256_file(TEST),
        },
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "authorization_opened": False,
        "held_out_authorized": False,
        "later_stages_authorized": False,
        "formal_scaling_authorized": False,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {
        "schema_version": VERSION,
        "experiment": "acl2027_phase2_probe_only_live_v18",
        "authorization_id": AUTH_ID,
        "status": "open",
        "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": gate["aggregate_fingerprint"]},
        "credential_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "user_authorization": {
            "scope": "phase2_probe_only",
            "authorized_calls": CALLS,
            "authorization_receipt_sha256": sha256_file(RECEIPT),
            "held_out_authorized": False,
            "later_stages_authorized": False,
            "formal_scaling_authorized": False,
        },
        "authorized_stage": "probe",
        "authorized_calls": CALLS,
        "stage_call_ceiling": CALLS,
        "max_provider_attempts": CALLS,
        "stage_cost_ceiling_cny": COST_CEILING,
        "cumulative_cost_ceiling_cny": COST_CEILING,
        "model_id": "qwen3.7-plus",
        "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "retries": 0,
        "max_tokens_present": False,
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "formal_scaling_allowed": False,
        "forbidden_stages": ["held_out", "later_phase2_stages", "formal_scaling"],
    }


def open_authorization() -> dict[str, Any]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY missing")
    if any(path.exists() for path in (AUTH, AUTH_CLOSED, REGISTRY, LEDGER, PACING, CLOSURE)):
        raise HardStop("v18 live authorization already opened, started, or closed")
    gate = preflight()
    write(PREFLIGHT_AUDIT, gate)
    auth = authorization_template(key)
    write(AUTH, auth)
    relative = os.path.relpath(AUTH, REGISTRY.parent).replace("\\", "/")
    write(REGISTRY, {"schema_version": VERSION, "authorizations": {AUTH_ID: {"path": relative, "sha256": sha256_file(AUTH)}}})
    validate_authorization()
    return auth


def validate_authorization() -> tuple[dict[str, Any], str]:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.is_file() or not REGISTRY.is_file() or CLOSURE.exists() or AUTH_CLOSED.exists():
        raise HardStop("v18 live authorization is closed or absent")
    auth = load(AUTH)
    if auth != authorization_template(key):
        raise HardStop("v18 authorization boundary drift")
    item = load(REGISTRY).get("authorizations", {}).get(AUTH_ID)
    if not item or (REGISTRY.parent / item["path"]).resolve() != AUTH.resolve() or item.get("sha256") != sha256_file(AUTH):
        raise HardStop("v18 authorization registry drift")
    return auth, item["sha256"]


def seal(record: dict[str, Any]) -> None:
    record["ledger_entry_sha256"] = stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"})


def validate_start(start: dict[str, Any], planned: dict[str, Any], auth_sha: str, previous: str | None) -> None:
    if start.get("logical_call_id") != planned["logical_call_id"] or start.get("request_hash") != planned["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous:
        raise HardStop("v18 request-start binding drift")
    if start.get("request_body_sha256") != stable(planned["canonical_request_body"]):
        raise HardStop("v18 request-start body binding drift")
    if start.get("start_entry_sha256") != stable({key: value for key, value in start.items() if key != "start_entry_sha256"}):
        raise HardStop("v18 request-start hash-chain drift")


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records):
        raise HardStop("v18 ambiguous request start; retry forbidden", records)
    if len({record.get("logical_call_id") for record in records}) != len(records) or len({record.get("request_hash") for record in records}) != len(records):
        raise HardStop("v18 duplicate logical/request identity", records)
    previous_ledger = None
    previous_start = None
    cumulative_cost = 0.0
    for planned, record, start in zip(rows, records, starts):
        validate_start(start, planned, auth_sha, previous_start)
        for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "payload_hash", "staged_execution_index"):
            if record.get(key) != planned.get(key):
                raise HardStop("v18 non-prefix probe ledger", records)
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous_ledger:
            raise HardStop("v18 authorization or ledger-chain drift", records)
        if record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("v18 ledger entry hash drift", records)
        if record.get("terminal"):
            raise HardStop("v18 terminal ledger is not resumable", records)
        exact = usage(record)
        if record.get("local_cost_cny") != local_cost_from_usage(exact):
            raise HardStop("v18 per-call cost drift", records)
        cumulative_cost = round(cumulative_cost + record["local_cost_cny"], 6)
        if record.get("cumulative_local_cost_cny") != cumulative_cost:
            raise HardStop("v18 cumulative cost drift", records)
        previous_ledger = record["ledger_entry_sha256"]
        previous_start = start["start_entry_sha256"]


def validate_audit_chain(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records):
        raise HardStop("v18 audit pacing/ledger count drift", records)
    if len({record.get("logical_call_id") for record in records}) != len(records) or len({record.get("request_hash") for record in records}) != len(records):
        raise HardStop("v18 audit duplicate logical/request identity", records)
    previous_ledger = None
    previous_start = None
    cumulative_cost = 0.0
    for index, (planned, record, start) in enumerate(zip(rows, records, starts)):
        validate_start(start, planned, auth_sha, previous_start)
        for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "payload_hash", "staged_execution_index"):
            if record.get(key) != planned.get(key):
                raise HardStop("v18 audit non-prefix probe ledger", records)
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous_ledger:
            raise HardStop("v18 audit authorization or ledger-chain drift", records)
        if record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("v18 audit ledger entry hash drift", records)
        if record.get("terminal") and index != len(records) - 1:
            raise HardStop("v18 terminal row must be the final prefix row", records)
        if isinstance(record.get("usage"), dict):
            exact = usage(record)
            call_cost = local_cost_from_usage(exact)
            if record.get("local_cost_cny") != call_cost:
                raise HardStop("v18 audit per-call cost drift", records)
            cumulative_cost = round(cumulative_cost + call_cost, 6)
            if record.get("cumulative_local_cost_cny") != cumulative_cost:
                raise HardStop("v18 audit cumulative cost drift", records)
        elif not record.get("terminal") or record.get("local_cost_cny") is not None or record.get("cumulative_local_cost_cny") is not None:
            raise HardStop("v18 unknown usage is allowed only on the terminal row", records)
        if record.get("model_id") != "qwen3.7-plus" or record.get("temperature") != 0 or record.get("retries") != 0 or record.get("max_tokens_present") is not False:
            raise HardStop("v18 audit route/accounting boundary drift", records)
        previous_ledger = record["ledger_entry_sha256"]
        previous_start = start["start_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]], *, interrupt_after: int | None = None) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization()
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        if known_cost(records) >= COST_CEILING:
            raise HardStop("v18 cost ceiling reached before next attempt", records)
        row = rows[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if row["request_hash"] != stable(body) or "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("response_format") != {"type": "json_object"} or body.get("enable_thinking") is not False:
            raise HardStop("v18 request boundary drift", records)
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0:
                time.sleep(wait / 1_000_000_000)
        start = {
            "sequence": len(starts) + 1,
            "logical_call_id": row["logical_call_id"],
            "request_hash": row["request_hash"],
            "request_body_sha256": stable(body),
            "authorization_sha256": auth_sha,
            "request_started_at_unix_ns": time.time_ns(),
            "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None,
        }
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(PACING, starts)
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "payload_hash", "staged_execution_index")}
        base.update(
            provider_attempt_index=len(records) + 1,
            authorization_id=AUTH_ID,
            authorization_sha256=auth_sha,
            authorized_stage="probe",
            model_id="qwen3.7-plus",
            temperature=0,
            retries=0,
            max_tokens_present=False,
            previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None,
        )
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            raw = response.get("content")
            if not isinstance(raw, str):
                raise HardStop("v18 provider response missing content")
            call_cost = local_cost_from_usage(exact)
            record = {
                **base,
                "request_id": response.get("request_id"),
                "raw_response": raw,
                "raw_response_sha256": stable(raw),
                "raw_provider_response": response.get("raw_provider_response", response),
                "usage": exact,
                "local_cost_cny": call_cost,
                "cumulative_local_cost_cny": round(known_cost(records) + call_cost, 6),
                "terminal": False,
                "status": "completed",
                "error": None,
            }
        except Exception as exc:
            maybe_usage = response.get("usage") if isinstance(response, dict) and isinstance(response.get("usage"), dict) else None
            call_cost = None
            if maybe_usage is not None:
                try:
                    call_cost = local_cost_from_usage(usage(response))
                except Exception:
                    call_cost = None
            record = {
                **base,
                "request_id": response.get("request_id") if isinstance(response, dict) else None,
                "raw_response": response.get("content") if isinstance(response, dict) else None,
                "raw_response_sha256": stable(response.get("content") if isinstance(response, dict) else None),
                "raw_provider_response": response.get("raw_provider_response", response) if isinstance(response, dict) else response,
                "usage": maybe_usage,
                "local_cost_cny": call_cost,
                "cumulative_local_cost_cny": round(known_cost(records) + (call_cost or 0.0), 6) if call_cost is not None else None,
                "terminal": True,
                "status": "hard_stop",
                "error": f"{type(exc).__name__}: {exc}",
            }
        seal(record)
        records.append(record)
        write(LEDGER, records)
        if interrupt_after is not None and len(records) == interrupt_after:
            raise KeyboardInterrupt("simulated interruption after durable append")
        if record["terminal"]:
            raise HardStop(record["error"], records)
        if known_cost(records) >= COST_CEILING and len(records) < CALLS:
            records[-1].update(terminal=True, status="completed_cost_ceiling_stop", error="v18 cost ceiling reached")
            seal(records[-1])
            write(LEDGER, records)
            raise HardStop(records[-1]["error"], records)
    return records


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    terminal = bool(records and records[-1].get("terminal"))
    auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha:
        raise HardStop("v18 ledger exists without authorization")
    if auth_sha:
        validate_audit_chain(records, starts, rows, auth_sha)
    known = [record for record in records if isinstance(record.get("usage"), dict)]
    exact_usage_complete = len(known) == len(records)
    probe = None
    if len(records) == CALLS and not terminal:
        probe = build_probe_audit(records, rows, load(CANDIDATE), sha256_file(CANDIDATE), REPLACEMENT_GOLD)
        write(PROBE_AUDIT, probe)
    request_ids = [record.get("request_id") for record in records if record.get("request_id")]
    completed_statuses = {"completed", "completed_cost_ceiling_stop"}
    completed = [record for record in records if record.get("status") in completed_statuses]
    if len(request_ids) != len(completed) or len(set(request_ids)) != len(request_ids):
        raise HardStop("v18 completed provider request IDs are missing or duplicated")
    result = {
        "schema_version": VERSION,
        "status": "completed" if probe else "terminal_hard_stop" if terminal else "incomplete",
        "planned_calls": CALLS,
        "provider_attempts": len(starts),
        "unique_logical_requests": len({record.get("logical_call_id") for record in records}),
        "unique_request_hashes": len({record.get("request_hash") for record in records}),
        "unique_provider_request_ids": len(set(request_ids)),
        "completed_calls": sum(record.get("status") in completed_statuses for record in records),
        "terminal_rows": sum(bool(record.get("terminal")) for record in records),
        "skipped_requests": 0,
        "out_of_bounds_requests": 0,
        "input_tokens": sum(usage(record)["input_tokens"] for record in known),
        "output_tokens": sum(usage(record)["output_tokens"] for record in known),
        "total_tokens": sum(usage(record)["total_tokens"] for record in known),
        "usage_status": "exact" if exact_usage_complete else "known_lower_bound",
        "exact_local_cost_cny": known_cost(records) if exact_usage_complete else None,
        "known_local_cost_lower_bound_cny": known_cost(records),
        "retries": sum(record.get("retries", 0) for record in records),
        "duplicates": len(records) - len({record.get("logical_call_id") for record in records}),
        "max_tokens_present": any(record.get("max_tokens_present") for record in records),
        "model_id": "qwen3.7-plus",
        "temperature": 0,
        "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])),
        "ledger_hash_chain_valid": True,
        "request_start_hash_chain_valid": True,
        "exact_prefix_resume_valid": True,
        "v17_aggregate_fingerprint": load(V17_MANIFEST)["aggregate_fingerprint"],
        "probe_gate_passed": probe.get("passed") if probe else False,
        "condition_accuracy": probe.get("condition_accuracy", {}) if probe else {},
        "primary_paired_comparison": probe.get("primary_paired_comparison", {}) if probe else {},
        "network_calls": len(starts),
        "provider_calls": len(starts),
        "model_calls": len(starts),
        "paid_api_calls": len(starts),
        "held_out_calls": 0,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "authorization_closed": CLOSURE.exists() and AUTH_CLOSED.exists(),
    }
    write(RUN_AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {
        "schema_version": VERSION,
        "authorization_id": AUTH_ID,
        "status": "closed",
        "reason": reason,
        "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None,
        "authorization_receipt_sha256": sha256_file(RECEIPT),
        "authorization_request_sha256": sha256_file(REQUEST),
        "provider_attempts": result["provider_attempts"],
        "completed_calls": result["completed_calls"],
        "usage_status": result["usage_status"],
        "exact_local_cost_cny": result["exact_local_cost_cny"],
        "known_local_cost_lower_bound_cny": result["known_local_cost_lower_bound_cny"],
        "held_out_calls": 0,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "paid_api_allowed": False,
        "provider_calls_allowed": False,
        "qwen_authorization_open": False,
        "formal_scaling_allowed": False,
    }
    write(CLOSURE, closure)
    write(AUTH_CLOSED, closure)
    result["authorization_closed"] = True
    write(RUN_AUDIT, result)
    return closure


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
