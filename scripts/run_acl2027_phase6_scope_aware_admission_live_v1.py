#!/usr/bin/env python3
"""Authorization-gated execution for the immutable Phase 6 schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter

CALLS = 240
DESIGN = "aecbd3c11dffd1f6860d663d3fe86fa144da4e8be4048aadf323ccd5b8e26ca6"
PREFLIGHT = "dfe7cbf6c9e4a8ad5da6298e9fe41a9b4b745cf404eb08b3e9c0f3443721fb3d"
MODEL = "qwen3.7-plus"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
STAGE_CEILING = 3.0
CUMULATIVE_CEILING = 15.0
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase6-scope-aware-admission-live-v1"
STATEMENT = (
    "I explicitly authorize ACL 2027 Phase 6 execution, binding design fingerprint "
    + DESIGN
    + " and live preflight fingerprint "
    + PREFLIGHT
    + ", using exactly 240 frozen requests on qwen3.7-plus with temperature 0, thinking disabled, "
    "zero retries, no max_tokens, JSON-object responses, one-second pacing, CNY 3.00 stage and "
    "CNY 15.00 cumulative ceilings, first-failure stop, exact-prefix resume only, durable "
    "request-start/response hash-chain ledgers, and automatic closure. I authorize no replication, "
    "other models, later phases, cross-domain scaling, or formal scaling."
)

PREFLIGHT_DIR = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_live_preflight_v1"
SOURCE_DIR = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_preflight_v1"
ARTIFACT = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_live_v1"
RECEIPT = ROOT / "configs/acl2027/phase6_scope_aware_admission_user_authorization_receipt_v1.json"
AUTH = ARTIFACT / "authorization_open.json"
STARTS = ARTIFACT / "request_start_ledger.json"
LEDGER = ARTIFACT / "ledger.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
AUDIT = ARTIFACT / "run_audit.json"


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
        "scope": "phase6_scope_aware_admission_only",
        "endpoint": ENDPOINT,
        "authorized_calls": CALLS,
        "max_provider_attempts": CALLS,
        "model_id": MODEL,
        "temperature": 0,
        "enable_thinking": False,
        "retries": 0,
        "max_tokens_present": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "stage_cost_ceiling_cny": STAGE_CEILING,
        "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING,
        "terminal_stop_on_first_failed_attempt": True,
        "authorization_closes_on_completion_or_terminal_stop": True,
        "usage_accounting_required": True,
        "request_start_ledger_required": True,
        "response_ledger_required": True,
        "hash_chain_required": True,
        "exact_prefix_resume_only": True,
    }


def schedule() -> list[dict[str, Any]]:
    manifest = load(PREFLIGHT_DIR / "run_manifest.json")
    request = load(PREFLIGHT_DIR / "authorization_request.json")
    rows = load(SOURCE_DIR / "schedule.json")["rows"]
    if manifest.get("aggregate_fingerprint") != PREFLIGHT:
        raise RuntimeError("Phase 6 live-preflight fingerprint drift")
    if request.get("preflight_aggregate_fingerprint") != PREFLIGHT:
        raise RuntimeError("Phase 6 authorization request fingerprint drift")
    if request.get("source_design_fingerprint") != DESIGN:
        raise RuntimeError("Phase 6 design fingerprint drift")
    if request.get("authorization_statement_verbatim") != STATEMENT:
        raise RuntimeError("Phase 6 authorization statement drift")
    if len(rows) != CALLS or [row.get("sequence") for row in rows] != list(range(1, CALLS + 1)):
        raise RuntimeError("Phase 6 schedule coverage drift")
    for field in ("logical_call_id", "request_hash", "transport_payload_hash"):
        if len({row.get(field) for row in rows}) != CALLS:
            raise RuntimeError(f"Phase 6 {field} collision")
    for row in rows:
        body = row.get("canonical_request_body", {})
        request_without_route = {key: value for key, value in body.items() if key not in {"model_id", "temperature", "enable_thinking", "response_format"}}
        if row.get("request_hash") != stable(request_without_route):
            raise RuntimeError("Phase 6 request hash drift")
        if body.get("model_id") != MODEL or body.get("temperature") != 0:
            raise RuntimeError("Phase 6 route drift")
        if body.get("enable_thinking") is not False or body.get("response_format") != {"type": "json_object"}:
            raise RuntimeError("Phase 6 response route drift")
        transport_body = {key: body[key] for key in ("model_id", "temperature", "enable_thinking", "response_format", "messages")}
        if row.get("transport_payload_hash") != stable(transport_body):
            raise RuntimeError("Phase 6 transport payload hash drift")
        if "max_tokens" in body or any(key in body for key in ("target_answer", "counterfactual_answer", "private_gold")):
            raise RuntimeError("Phase 6 private payload or max_tokens drift")
    return rows


def cost(usage: dict[str, int]) -> float:
    return round((usage["input_tokens"] * 2 + usage["output_tokens"] * 8) / 1_000_000, 6)


def total_cost(records: list[dict[str, Any]]) -> float:
    return round(sum(record.get("local_cost_cny") or 0.0 for record in records), 6)


def authorize() -> dict[str, Any]:
    rows = schedule()
    if ARTIFACT.exists() or RECEIPT.exists():
        raise RuntimeError("Phase 6 authorization or execution record already exists")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY missing")
    receipt = {
        "schema_version": 1,
        "status": "explicit_user_authorization_received",
        "authorization_statement_verbatim": STATEMENT,
        "authorization_statement_sha256": hashlib.sha256(STATEMENT.encode()).hexdigest(),
        "source_design_fingerprint": DESIGN,
        "preflight_aggregate_fingerprint": PREFLIGHT,
        **contract(),
        "data_egress_authorized": True,
        "paid_usage_authorized": True,
        "forbidden_scope": ["replication", "other_models", "later_phases", "cross_domain_scaling", "formal_scaling"],
    }
    write(RECEIPT, receipt)
    try:
        ARTIFACT.mkdir(parents=False, exist_ok=False)
    except Exception:
        # The receipt is intentionally left behind: a filesystem failure is terminal and must not be retried.
        raise
    opened = {
        "schema_version": 1,
        "authorization_id": AUTH_ID,
        "status": "open",
        "credential_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "receipt_sha256": sha256_file(RECEIPT),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "rows": len(rows),
        **contract(),
        "data_egress_authorized": True,
        "paid_usage_authorized": True,
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "formal_scaling_allowed": False,
        "source_design_fingerprint": DESIGN,
        "preflight_aggregate_fingerprint": PREFLIGHT,
    }
    write(AUTH, opened)
    return opened


def validate_prefix(rows: list[dict[str, Any]], starts: list[dict[str, Any]], records: list[dict[str, Any]], auth_sha: str) -> None:
    if len(starts) != len(records) or len(records) > CALLS:
        raise RuntimeError("ambiguous request prefix")
    previous_start = previous_record = None
    for row, start, record in zip(rows, starts, records):
        if (
            start.get("logical_call_id") != row["logical_call_id"]
            or start.get("request_hash") != row["request_hash"]
            or start.get("authorization_sha256") != auth_sha
            or start.get("previous_start_entry_sha256") != previous_start
            or start.get("start_entry_sha256") != stable({k: v for k, v in start.items() if k != "start_entry_sha256"})
        ):
            raise RuntimeError("request-start chain drift")
        if (
            record.get("logical_call_id") != row["logical_call_id"]
            or record.get("request_hash") != row["request_hash"]
            or record.get("authorization_sha256") != auth_sha
            or record.get("previous_ledger_entry_sha256") != previous_record
            or record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"})
        ):
            raise RuntimeError("response-ledger chain drift")
        previous_start, previous_record = start["start_entry_sha256"], record["ledger_entry_sha256"]


def execute() -> dict[str, Any]:
    rows = schedule()
    auth = load(AUTH)
    auth_sha = sha256_file(AUTH)
    if auth.get("status") != "open" or not all(auth.get(key) is True for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        raise RuntimeError("Phase 6 authorization is not open")
    starts = load(STARTS) if STARTS.exists() else []
    records = load(LEDGER) if LEDGER.exists() else []
    validate_prefix(rows, starts, records, auth_sha)
    provider = QwenTokenPlanProviderAdapter(auth)
    while len(records) < CALLS:
        if total_cost(records) >= STAGE_CEILING or total_cost(records) >= CUMULATIVE_CEILING:
            raise RuntimeError("Phase 6 cost ceiling reached")
        row = rows[len(records)]
        if starts:
            remaining = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if remaining > 0:
                time.sleep(remaining / 1_000_000_000)
        start = {
            "sequence": len(starts) + 1,
            "logical_call_id": row["logical_call_id"],
            "request_hash": row["request_hash"],
            "request_body_sha256": row["request_hash"],
            "authorization_sha256": auth_sha,
            "request_started_at_unix_ns": time.time_ns(),
            "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None,
        }
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(STARTS, starts)
        base = {key: row.get(key) for key in ("logical_call_id", "request_hash", "task_id", "task_family", "skill_family", "condition")}
        base.update({
            "provider_attempt_index": len(records) + 1,
            "authorization_id": AUTH_ID,
            "authorization_sha256": auth_sha,
            "model_id": MODEL,
            "temperature": 0,
            "retries": 0,
            "max_tokens_present": False,
            "previous_ledger_entry_sha256": records[-1]["ledger_entry_sha256"] if records else None,
        })
        try:
            response = provider(deepcopy(row["canonical_request_body"]))
            usage = response["usage"]
            request_id = response.get("request_id")
            if not request_id or request_id in {record.get("request_id") for record in records}:
                raise RuntimeError("missing or duplicate provider request id")
            local_cost = cost(usage)
            if total_cost(records) + local_cost > STAGE_CEILING or total_cost(records) + local_cost > CUMULATIVE_CEILING:
                raise RuntimeError("response would exceed cost ceiling")
            record = {
                **base,
                "request_id": request_id,
                "raw_response": response["content"],
                "raw_response_sha256": stable(response["content"]),
                "raw_provider_response": response.get("raw_provider_response", response),
                "usage": usage,
                "local_cost_cny": local_cost,
                "cumulative_local_cost_cny": round(total_cost(records) + local_cost, 6),
                "terminal": False,
                "status": "completed",
                "error": None,
            }
        except Exception as exc:
            record = {
                **base,
                "request_id": None,
                "raw_response": None,
                "raw_response_sha256": stable(None),
                "raw_provider_response": None,
                "usage": None,
                "local_cost_cny": None,
                "cumulative_local_cost_cny": None,
                "terminal": True,
                "status": "hard_stop",
                "error": f"{type(exc).__name__}: {exc}",
            }
        record["ledger_entry_sha256"] = stable(record)
        records.append(record)
        write(LEDGER, records)
        if record["terminal"]:
            raise RuntimeError(record["error"])
    return audit()


def audit() -> dict[str, Any]:
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(STARTS) if STARTS.exists() else []
    known = [record for record in records if isinstance(record.get("usage"), dict)]
    result = {
        "schema_version": 1,
        "experiment": "acl2027_phase6_scope_aware_admission_live_v1",
        "status": "completed" if len(records) == CALLS and all(not record.get("terminal") for record in records) else "terminal_hard_stop" if records and records[-1].get("terminal") else "incomplete",
        "planned_calls": CALLS,
        "provider_attempts": len(starts),
        "completed_calls": len(known),
        "terminal_rows": sum(bool(record.get("terminal")) for record in records),
        "input_tokens": sum(record["usage"]["input_tokens"] for record in known),
        "output_tokens": sum(record["usage"]["output_tokens"] for record in known),
        "total_tokens": sum(record["usage"]["total_tokens"] for record in known),
        "known_stage_cost_lower_bound_cny": total_cost(records),
        "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])),
        "network_calls": len(starts),
        "provider_calls": len(starts),
        "model_calls": len(starts),
        "paid_api_calls": len(starts),
        "replication_calls": 0,
        "cross_domain_calls": 0,
        "formal_scaling_calls": 0,
        "authorization_closed": CLOSURE.exists(),
    }
    write(AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {
        "schema_version": 1,
        "authorization_id": AUTH_ID,
        "status": "closed",
        "reason": reason,
        "provider_attempts": result["provider_attempts"],
        "completed_calls": result["completed_calls"],
        "known_stage_cost_lower_bound_cny": result["known_stage_cost_lower_bound_cny"],
        "paid_api_allowed": False,
        "provider_calls_allowed": False,
        "qwen_authorization_open": False,
        "formal_scaling_allowed": False,
    }
    write(CLOSURE, closure)
    result["authorization_closed"] = True
    write(AUDIT, result)
    return closure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    command = parser.parse_args().command
    if command == "preflight":
        result = {"rows": len(schedule()), "network_calls": 0, "aggregate_fingerprint": PREFLIGHT}
    elif command == "authorize":
        result = authorize()
    elif command == "audit":
        result = audit()
    elif command == "close":
        result = close("operator_close")
    else:
        try:
            result = execute()
            close("completed_exact_240")
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
