#!/usr/bin/env python3
"""Authorization-gated live orchestrator for Phase 2 recovery v12."""
from __future__ import annotations

import argparse
import hashlib
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
from scripts.materialize_acl2027_phase2_candidates_recovery_v12 import build_recovery_candidate_artifact
from scripts.run_acl2027_phase2_formal_history_recovery_preflight_v12 import (
    COMBINED_SCHEDULE,
    CONFIG,
    MANIFEST,
    RECOVERY_SCHEDULE,
    validate as validate_preflight,
)
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage

VERSION = 12
CALLS = 128
COST_CEILING = 1.64
INTERVAL_NS = 1_000_000_000
AUTH_ID = "phase2-formal-history-recovery-token-plan-v12"
AUTH = ROOT / "configs/acl2027/phase2_formal_history_recovery_authorization_v12.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_live_v12"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
CANDIDATES = ARTIFACT / "candidate_materialization.json"
AUDIT = ARTIFACT / "recovery_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
REPORT = ROOT / "paper/acl2027/results/phase2_formal_history_recovery_live_v12.md"
V11_LEDGER = ROOT / "artifacts/acl2027_phase2_formal_history_v11/ledger.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def authorization_template(key: str) -> dict[str, Any]:
    return {
        "schema_version": VERSION, "authorization_id": AUTH_ID, "status": "open",
        "bindings": {"preflight_config_sha256": sha256_file(CONFIG), "preflight_manifest_sha256": sha256_file(MANIFEST), "recovery_schedule_sha256": sha256_file(RECOVERY_SCHEDULE), "combined_schedule_sha256": sha256_file(COMBINED_SCHEDULE), "live_runner_sha256": sha256_file(Path(__file__).resolve())},
        "credential_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "user_authorization": {"scope": "phase2_formal_history_recovery_only", "authorized_calls": CALLS, "probe_authorized": False, "held_out_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False},
        "authorized_stage": "formal_history_recovery", "authorized_calls": CALLS, "stage_call_ceiling": CALLS, "max_provider_attempts": CALLS,
        "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": COST_CEILING,
        "model_id": "qwen3.7-plus", "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0,
        "retries": 0, "max_tokens_present": False, "formal_scaling_allowed": False,
        "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True,
        "forbidden_stages": ["probe", "held_out", "formal_scaling"],
    }


def validate_authorization() -> tuple[dict[str, Any], str]:
    validate_preflight()
    if not AUTH.is_file() or not REGISTRY.is_file():
        raise HardStop("v12 live authorization is closed or absent")
    registry = load(REGISTRY)
    item = registry.get("authorizations", {}).get(AUTH_ID)
    if not item or (REGISTRY.parent / item["path"]).resolve() != AUTH.resolve() or item.get("sha256") != sha256_file(AUTH):
        raise HardStop("v12 authorization registry drift")
    key = os.environ.get("DASHSCOPE_API_KEY")
    auth = load(AUTH)
    if not key or auth != authorization_template(key):
        raise HardStop("v12 authorization boundary drift")
    return auth, item["sha256"]


def seal(record: dict[str, Any]) -> None:
    record["ledger_entry_sha256"] = stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"})


def validate_prefix(records: list[dict[str, Any]], starts: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS or len(starts) != len(records):
        raise HardStop("v12 ambiguous request start; retry forbidden", records)
    previous = None
    for planned, record in zip(rows, records):
        if any(record.get(key) != planned.get(key) for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "sequence")):
            raise HardStop("v12 non-prefix recovery ledger", records)
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous:
            raise HardStop("v12 authorization or hash-chain drift", records)
        if record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("v12 ledger hash-chain drift", records)
        if record.get("terminal"):
            raise HardStop("v12 terminal ledger is not resumable", records)
        usage(record)
        previous = record["ledger_entry_sha256"]


def cost(records: list[dict[str, Any]]) -> float:
    return round(sum(usage(row)["input_tokens"] * 2.0 + usage(row)["output_tokens"] * 8.0 for row in records) / 1_000_000, 6)


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]], *, interrupt_after: int | None = None) -> list[dict[str, Any]]:
    _, auth_sha = validate_authorization()
    rows = load(RECOVERY_SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    validate_prefix(records, starts, rows, auth_sha)
    while len(records) < CALLS:
        row = rows[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if "max_tokens" in body or body.get("response_format") != {"type": "json_object"} or body.get("temperature") != 0:
            raise HardStop("v12 request boundary drift", records)
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0:
                time.sleep(wait / 1_000_000_000)
        start = {"sequence": len(starts) + 1, "request_body_sha256": stable(body), "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}
        start["start_entry_sha256"] = stable(start)
        starts.append(start)
        write(PACING, starts)
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "payload_hash", "sequence")}
        base.update(authorization_id=AUTH_ID, authorization_sha256=auth_sha, authorized_stage="formal_history_recovery", retries=0, max_tokens_present=False, previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None)
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            raw = response.get("content")
            if not isinstance(raw, str):
                raise HardStop("v12 provider response missing raw content")
            record = {**base, "raw_response": raw, "raw_response_sha256": stable(raw), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "terminal": False, "status": "completed", "error": None}
        except Exception as exc:
            record = {**base, "raw_response": response.get("content") if isinstance(response, dict) else None, "raw_response_sha256": stable(response.get("content") if isinstance(response, dict) else None), "raw_provider_response": response.get("raw_provider_response", response) if isinstance(response, dict) else response, "usage": response.get("usage") if isinstance(response, dict) else None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        seal(record)
        records.append(record)
        write(LEDGER, records)
        if interrupt_after is not None and len(records) == interrupt_after:
            raise KeyboardInterrupt("simulated durable interruption")
        if record["terminal"]:
            raise HardStop(record["error"], records)
        if cost(records) > COST_CEILING:
            records[-1].update(terminal=True, status="hard_stop", error="v12 cost ceiling exceeded")
            seal(records[-1]); write(LEDGER, records)
            raise HardStop(records[-1]["error"], records)
    return records


def audit() -> dict[str, Any]:
    rows = load(RECOVERY_SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    terminal = bool(records and records[-1].get("terminal"))
    if not terminal:
        validate_prefix(records, starts, rows, sha256_file(AUTH))
    if len(starts) != len(records):
        raise HardStop("v12 pacing count drift")
    candidate = None
    if len(records) == CALLS and not terminal:
        preserved = [row for row in load(V11_LEDGER) if row.get("status") == "completed"]
        candidate = build_recovery_candidate_artifact(preserved, records, load(COMBINED_SCHEDULE)["schedule"], load(CONFIG), root=ROOT)
        write(CANDIDATES, candidate)
    return {"schema_version": VERSION, "status": "completed" if candidate else "terminal_hard_stop" if terminal else "incomplete", "provider_attempts": len(records), "completed_calls": sum(row.get("status") == "completed" for row in records), "terminal_rows": sum(bool(row.get("terminal")) for row in records), "total_tokens": sum(usage(row)["total_tokens"] for row in records) if candidate else None, "exact_local_cost_cny": cost(records) if candidate else None, "retries": sum(row.get("retries", 0) for row in records), "duplicates": len(records) - len({row["logical_call_id"] for row in records}), "max_tokens_present": any(row.get("max_tokens_present") for row in records), "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])), "coverage_status": candidate["coverage_status"] if candidate else "not_reached", "coverage_passed": candidate["passed"] if candidate else False, "independent_verified_supports": candidate["independent_verified_supports"] if candidate else {}, "probe_calls": 0, "held_out_calls": 0, "formal_scaling_calls": 0, "authorization_closed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "execute", "audit"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = validate_preflight()
    elif args.command == "execute":
        result = {"rows": len(execute(QwenTokenPlanProviderAdapter(validate_authorization()[0])))}
    else:
        result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
