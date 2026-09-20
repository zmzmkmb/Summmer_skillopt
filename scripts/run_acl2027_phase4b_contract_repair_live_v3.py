#!/usr/bin/env python3
"""Authorization-gated live runner for the immutable Phase 4B-R1 repaired schedule."""
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

VERSION, CALLS = 3, 100
REPAIR_FINGERPRINT = "a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c"
PREFLIGHT_FINGERPRINT = "94a2e284a4049db12f5e1f1294fa92d4433547ee9be0dd151e6ba848bbc7da28"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
STAGE_CEILING, CUMULATIVE_CEILING, PRIOR_COST = 2.0, 15.0, 11.816126
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase4b-contract-repair-live-v3"
PAYLOAD_CLASSES = ["frozen_task_prompts", "frozen_annotated_contexts", "frozen_procedure_candidate_bundles", "frozen_six_field_response_contract"]
AUTHORIZATION_STATEMENT = (
    "User explicitly authorizes the 100 Phase 4B-R2 repaired development calls bound to repair fingerprint "
    f"{REPAIR_FINGERPRINT} and live preflight fingerprint {PREFLIGHT_FINGERPRINT}, including 80 unique transport "
    "payloads and 20 global_only/contextual_typed equivalent pairs that cannot support a causal contrast. The frozen "
    "qwen3.7-plus Token Plan contract includes paid API/provider calls, temperature 0, disabled thinking, "
    "zero retries, absent max_tokens, JSON-object responses, one-second pacing, CNY 2.00 stage ceiling, "
    "CNY 15.00 cumulative ceiling, first-failure stop, and automatic closure; no other model, later stage, "
    "cross-domain scaling, or formal scaling is authorized."
)

PREFLIGHT = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_preflight_v2"
SCHEDULE = ROOT / "artifacts/acl2027_phase4b_contract_repair_preflight_v1" / "repaired_schedule.json"
PREFLIGHT_MANIFEST = PREFLIGHT / "run_manifest.json"
PREFLIGHT_REQUEST = PREFLIGHT / "authorization_request.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
RECEIPT = ROOT / "configs/acl2027/phase4b_contract_repair_user_authorization_receipt_v3.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3"
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
        "scope": "phase4b_repaired_development_calibration_only",
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
        "known_cumulative_cost_lower_bound_cny": PRIOR_COST,
        "terminal_stop_on_first_failed_attempt": True,
        "authorization_closes_on_completion_or_terminal_stop": True,
        "exact_prefix_resume_only": True,
    }


def bindings() -> dict[str, str]:
    return {
        "preflight_manifest_sha256": sha256_file(PREFLIGHT_MANIFEST),
        "preflight_request_sha256": sha256_file(PREFLIGHT_REQUEST),
        "schedule_sha256": sha256_file(SCHEDULE),
        "adapter_sha256": sha256_file(ADAPTER),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def preflight() -> list[dict[str, Any]]:
    manifest, request = load(PREFLIGHT_MANIFEST), load(PREFLIGHT_REQUEST)
    if manifest.get("aggregate_fingerprint") != PREFLIGHT_FINGERPRINT:
        raise HardStop("Phase 4B preflight fingerprint drift")
    if request.get("phase4b_repair_fingerprint") != REPAIR_FINGERPRINT or request.get("preflight_aggregate_fingerprint") != PREFLIGHT_FINGERPRINT:
        raise HardStop("Phase 4B authorization request binding drift")
    rows = load(SCHEDULE).get("rows", [])
    if len(rows) != CALLS or len({r.get("logical_call_id") for r in rows}) != CALLS or len({r.get("request_hash") for r in rows}) != CALLS:
        raise HardStop("Phase 4B schedule identity drift")
    for row in rows:
        body = row.get("canonical_request_body", {})
        if row.get("request_hash") != stable(body) or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0 or body.get("enable_thinking") is not False or body.get("response_format") != {"type": "json_object"} or "max_tokens" in body:
            raise HardStop("Phase 4B payload contract drift")
        projection = live_projection(body)
        if stable(projection) != row.get("transport_payload_hash") or projection != row.get("transport_projection"):
            raise HardStop("Phase 4B transport projection drift")
        if not all(key in projection["messages"][0]["content"] for key in ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")):
            raise HardStop("Phase 4B six-field contract is not visible in system message")
        if len({sentence.get("id") for block in json.loads(projection["messages"][1]["content"])["context"] for sentence in block["sentences"]}) == 0:
            raise HardStop("Phase 4B evidence IDs are not visible")
    return rows


def live_projection(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": body["model_id"],
        "messages": body["messages"],
        "temperature": body["temperature"],
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
    }


def receipt() -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "status": "explicit_user_authorization_received_execution_not_open",
        "authorization_source": "user_message_2026-08-18",
        "authorization_statement_sha256": hashlib.sha256(AUTHORIZATION_STATEMENT.encode()).hexdigest(),
        "phase4b_repair_fingerprint": REPAIR_FINGERPRINT,
        "phase4b_live_preflight_fingerprint": PREFLIGHT_FINGERPRINT,
        **contract(),
        "endpoint": ENDPOINT,
        "data_egress_authorized": True,
        "authorized_destination": ENDPOINT,
        "authorized_payload_classes": PAYLOAD_CLASSES,
        "paid_usage_authorized": True,
        "forbidden_stages": ["other_models", "later_phase4", "cross_domain_scaling", "formal_scaling"],
        "bindings": bindings(),
        "execution": {"network_calls_allowed": False, "provider_calls_allowed": False, "paid_api_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False},
    }


def authorize() -> dict[str, Any]:
    rows = preflight()
    if ARTIFACT.exists() or RECEIPT.exists():
        raise HardStop("Phase 4B-R3 authorization or execution record already exists")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY missing")
    write(RECEIPT, receipt())
    opened = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "open", "credential_sha256": hashlib.sha256(key.encode()).hexdigest(), "receipt_sha256": sha256_file(RECEIPT), "runner_sha256": sha256_file(Path(__file__).resolve()), "rows": len(rows), **contract(), "endpoint": ENDPOINT, "data_egress_authorized": True, "authorized_payload_classes": PAYLOAD_CLASSES, "paid_usage_authorized": True, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "formal_scaling_allowed": False}
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    write(AUTH, opened)
    write(REGISTRY, {"authorization_id": AUTH_ID, "authorization_sha256": sha256_file(AUTH)})
    return opened


def validate_open() -> tuple[list[dict[str, Any]], str]:
    rows = preflight()
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or not AUTH.exists() or not REGISTRY.exists() or CLOSURE.exists():
        raise HardStop("Phase 4B-R3 authorization is not open")
    auth = load(AUTH)
    if auth.get("credential_sha256") != hashlib.sha256(key.encode()).hexdigest() or not all(auth.get(k) is True for k in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        raise HardStop("Phase 4B-R3 open authorization drift")
    return rows, sha256_file(AUTH)


def total_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(record.get("local_cost_cny") or 0.0 for record in records), 6)


def call_cost(value: dict[str, int]) -> float:
    return round((value["input_tokens"] * 2 + value["output_tokens"] * 8) / 1_000_000, 6)


def validate_prefix(rows: list[dict[str, Any]], starts: list[dict[str, Any]], records: list[dict[str, Any]], auth_sha: str) -> None:
    if len(starts) != len(records) or len(records) > CALLS:
        raise HardStop("ambiguous request prefix")
    previous_start = previous_record = None
    for row, start, record in zip(rows, starts, records):
        if start.get("logical_call_id") != row["logical_call_id"] or start.get("request_hash") != row["request_hash"] or start.get("authorization_sha256") != auth_sha or start.get("previous_start_entry_sha256") != previous_start or start.get("start_entry_sha256") != stable({k: v for k, v in start.items() if k != "start_entry_sha256"}):
            raise HardStop("request-start chain drift")
        if record.get("logical_call_id") != row["logical_call_id"] or record.get("request_hash") != row["request_hash"] or record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous_record or record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}):
            raise HardStop("response-ledger chain drift")
        if record.get("terminal"):
            raise HardStop("terminal attempt cannot be resumed")
        previous_start, previous_record = start["start_entry_sha256"], record["ledger_entry_sha256"]


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    rows, auth_sha = validate_open()
    starts = load(STARTS) if STARTS.exists() else []
    records = load(LEDGER) if LEDGER.exists() else []
    validate_prefix(rows, starts, records, auth_sha)
    while len(records) < CALLS:
        if total_cost(records) >= STAGE_CEILING or PRIOR_COST + total_cost(records) >= CUMULATIVE_CEILING:
            raise HardStop("cost ceiling reached")
        row, body = rows[len(records)], deepcopy(rows[len(records)]["canonical_request_body"])
        if starts:
            remaining = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if remaining > 0:
                time.sleep(remaining / 1_000_000_000)
        start = {"sequence": len(starts) + 1, "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "request_body_sha256": stable(body), "authorization_sha256": auth_sha, "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(STARTS, starts)
        base = {k: row.get(k) for k in ("logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "condition", "staged_execution_index")}
        base.update({"provider_attempt_index": len(records) + 1, "authorization_id": AUTH_ID, "authorization_sha256": auth_sha, "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None})
        try:
            response = provider(body)
            exact = usage(response)
            request_id = response.get("request_id")
            if not request_id or request_id in {r.get("request_id") for r in records}:
                raise HardStop("missing or duplicate provider request id")
            record = {**base, "request_id": request_id, "raw_response": response["content"], "raw_response_sha256": stable(response["content"]), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "local_cost_cny": call_cost(exact), "cumulative_local_cost_cny": round(total_cost(records) + call_cost(exact), 6), "terminal": False, "status": "completed", "error": None}
        except Exception as exc:
            record = {**base, "request_id": None, "raw_response": None, "raw_response_sha256": stable(None), "raw_provider_response": None, "usage": None, "local_cost_cny": None, "cumulative_local_cost_cny": None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        record["ledger_entry_sha256"] = stable(record)
        records.append(record)
        write(LEDGER, records)
        if record["terminal"]:
            raise HardStop(record["error"])
    return records


def audit() -> dict[str, Any]:
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(STARTS) if STARTS.exists() else []
    known = [r for r in records if isinstance(r.get("usage"), dict)]
    complete = len(records) == CALLS and all(not r.get("terminal") for r in records)
    result = {"schema_version": VERSION, "status": "completed" if complete else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete", "planned_calls": CALLS, "provider_attempts": len(starts), "completed_calls": len(known), "terminal_rows": sum(bool(r.get("terminal")) for r in records), "input_tokens": sum(usage(r)["input_tokens"] for r in known), "output_tokens": sum(usage(r)["output_tokens"] for r in known), "total_tokens": sum(usage(r)["total_tokens"] for r in known), "exact_stage_cost_cny": total_cost(records) if len(known) == len(records) else None, "known_stage_cost_lower_bound_cny": total_cost(records), "known_cumulative_cost_lower_bound_cny": round(PRIOR_COST + total_cost(records), 6), "retries": 0, "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])), "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts), "later_stage_calls": 0, "cross_domain_scaling_calls": 0, "formal_scaling_calls": 0, "authorization_closed": CLOSURE.exists()}
    write(AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {"schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason, "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"], "known_stage_cost_lower_bound_cny": result["known_stage_cost_lower_bound_cny"], "known_cumulative_cost_lower_bound_cny": result["known_cumulative_cost_lower_bound_cny"], "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False}
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
            result = {"rows": len(execute(QwenTokenPlanProviderAdapter(load(AUTH)))), "closure": close("completed_exact_100")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
