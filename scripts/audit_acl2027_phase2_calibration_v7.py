#!/usr/bin/env python3
"""Audit and irrevocably close the Phase 2 Token Plan calibration authorization."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response
from scripts.run_acl2027_phase2_calibration_token_plan_v6 import (
    HardStop,
    V4_CONFIG,
    load,
    required_bindings,
    schedule_rows,
    sha256_file,
    stable,
    usage,
    validate_authorization,
)
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import cost

DEFAULT_AUTH = ROOT / "configs/acl2027/phase2_calibration_live_authorization_v7.json"
DEFAULT_ARTIFACT = ROOT / "artifacts/acl2027_phase2_calibration_live_v7"
GOLD = ROOT / "data/searchqa_phase2_verified/calibration.json"
INTERVAL_NS = 1_000_000_000


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_open_authorization(auth_path: Path) -> dict[str, Any]:
    auth = load(auth_path)
    validate_authorization(auth, sha256_file(auth_path))
    if auth.get("bindings") != required_bindings():
        raise HardStop("v7 route binding drift")
    expected_live = {
        "live_orchestrator_sha256": sha256_file(ROOT / "scripts/run_acl2027_phase2_calibration_token_plan_live_v7.py"),
        "audit_source_sha256": sha256_file(Path(__file__).resolve()),
    }
    if auth.get("live_execution_bindings") != expected_live:
        raise HardStop("v7 audit source binding drift")
    return auth


def _validate_records(auth: dict[str, Any], auth_sha: str, records: list[dict[str, Any]]) -> None:
    expected_rows = schedule_rows()[:60]
    if len(records) > 60:
        raise HardStop("v7 audit found excess ledger rows")
    previous = None
    for expected, record in zip(expected_rows, records):
        for key in ("logical_call_id", "request_hash", "partition", "original_call_index", "staged_execution_index"):
            if record.get(key) != expected.get(key):
                raise HardStop("v7 audit found schedule drift")
        if record.get("authorization_id") != auth["authorization_id"] or record.get("authorization_sha256") != auth_sha:
            raise HardStop("v7 audit found authorization drift")
        if record.get("previous_ledger_entry_sha256") != previous:
            raise HardStop("v7 audit found ledger chain drift")
        if record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("v7 audit found ledger entry drift")
        previous = record["ledger_entry_sha256"]
        if not record.get("terminal"):
            usage(record)
    if any(record.get("terminal") for record in records[:-1]):
        raise HardStop("v7 audit found non-final terminal row")


def _validate_starts(records: list[dict[str, Any]], starts: list[dict[str, Any]]) -> None:
    if len(starts) != len(records):
        raise HardStop("v7 audit found ambiguous request-start count")
    previous = None
    previous_ns = None
    for sequence, (expected, event) in enumerate(zip(schedule_rows()[:60], starts), start=1):
        if event.get("sequence") != sequence:
            raise HardStop("v7 pacing sequence drift")
        if event.get("request_body_sha256") != stable(expected["canonical_request_body"]):
            raise HardStop("v7 pacing request drift")
        if event.get("previous_start_entry_sha256") != previous:
            raise HardStop("v7 pacing chain drift")
        if event.get("start_entry_sha256") != stable({key: value for key, value in event.items() if key != "start_entry_sha256"}):
            raise HardStop("v7 pacing entry drift")
        current_ns = event.get("request_started_at_unix_ns")
        if not isinstance(current_ns, int) or (previous_ns is not None and current_ns - previous_ns < INTERVAL_NS):
            raise HardStop("v7 request-start interval below one second")
        previous = event["start_entry_sha256"]
        previous_ns = current_ns


def build_audit(auth_path: Path = DEFAULT_AUTH, artifact: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    auth = validate_open_authorization(auth_path)
    auth_sha = sha256_file(auth_path)
    ledger = artifact / "ledger.json"
    pacing_ledger = artifact / "request_start_ledger.json"
    records = load(ledger) if ledger.exists() else []
    starts = load(pacing_ledger) if pacing_ledger.exists() else []
    _validate_records(auth, auth_sha, records)
    _validate_starts(records, starts)

    gold = {row["task_id"]: row for row in load(GOLD)}
    scored = []
    for record in records:
        valid = False
        correct = False
        try:
            parsed = parse_response(record["raw_response"])
            valid = True
            answers = gold[record["task_id"]].get("answers") or [gold[record["task_id"]]["answer"]]
            correct = normalize_answer(parsed["answer"]) in {normalize_answer(answer) for answer in answers}
        except Exception:
            pass
        scored.append({**{key: record[key] for key in ("logical_call_id", "task_id", "skill_family")}, "contract_valid": valid, "answer_correct": correct})

    attempts = len(starts)
    unique_ids = len({row["logical_call_id"] for row in records})
    known_records = [row for row in records if isinstance(row.get("usage"), dict)]
    total_usage = {key: sum(row["usage"][key] for row in known_records) for key in ("input_tokens", "output_tokens", "total_tokens")}
    valid_count = sum(row["contract_valid"] for row in scored)
    correct_count = sum(row["answer_correct"] for row in scored)
    success_types = len({gold[row["task_id"]]["task_type"] for row in scored if row["answer_correct"]})
    terminal = bool(records and records[-1].get("terminal"))
    complete = attempts == len(records) == unique_ids == 60 and not terminal
    checks = {
        "complete_60_attempt_calibration": complete,
        "contract_valid_rate_at_least_0_90": complete and valid_count / 60 >= 0.90,
        "accuracy_in_inclusive_0_25_to_0_75_band": complete and 0.25 <= correct_count / 60 <= 0.75,
        "minimum_three_successes": correct_count >= 3,
        "minimum_three_success_task_types": success_types >= 3,
        "five_reusable_skill_families_represented": len({row["skill_family"] for row in scored}) == 5,
    }
    config = load(V4_CONFIG)
    known_usage_complete = len(known_records) == len(records)
    exact_cost = cost(config, known_records) if known_usage_complete else None
    return {
        "schema_version": 7,
        "status": "completed" if complete else "terminal_hard_stop" if terminal else "incomplete",
        "authorization_id": auth["authorization_id"],
        "authorization_sha256": auth_sha,
        "bindings": auth["bindings"],
        "live_execution_bindings": auth["live_execution_bindings"],
        "planned_logical_requests": 60,
        "provider_attempts": attempts,
        "provider_accepted_calls": len(known_records),
        "unique_logical_requests": unique_ids,
        "duplicates": len(records) - unique_ids,
        "unattempted": 60 - attempts,
        "out_of_scope_requests": sum(row.get("partition") != "calibration" for row in records),
        "request_start_spacing_minimum_seconds": min(
            [(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"]) / 1_000_000_000 for a, b in zip(starts, starts[1:])],
            default=None,
        ),
        "request_start_pacing_valid": all(
            b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS for a, b in zip(starts, starts[1:])
        ),
        "retries": sorted({row.get("retries") for row in records}),
        "max_tokens_present": any(row.get("max_tokens_present") for row in records),
        "usage": total_usage,
        "exact_local_cost_cny": exact_cost,
        "cost_status": "exact" if known_usage_complete else "unknown_usage_terminal_hard_stop" if terminal else "unknown_usage_incomplete",
        "lower_bound_known_usage_cost_cny": cost(config, known_records),
        "contract_valid": valid_count,
        "answer_correct": correct_count,
        "eligibility_gate": {"passed": all(checks.values()), "checks": checks},
        "ledger_sha256": sha256_file(ledger) if ledger.exists() else None,
        "pacing_ledger_sha256": sha256_file(pacing_ledger) if pacing_ledger.exists() else None,
        "authorization_closed": True,
        "later_stages_authorized": False,
    }


def close_authorization(auth_path: Path = DEFAULT_AUTH, artifact: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    auth = load(auth_path)
    auth_sha = sha256_file(auth_path)
    try:
        audit = build_audit(auth_path, artifact)
    except Exception as exc:
        ledger = artifact / "ledger.json"
        pacing_ledger = artifact / "request_start_ledger.json"
        audit = {
            "schema_version": 7,
            "status": "audit_failed_closed",
            "authorization_id": auth["authorization_id"],
            "authorization_sha256": auth_sha,
            "error": f"{type(exc).__name__}: {exc}",
            "provider_attempts": len(load(pacing_ledger)) if pacing_ledger.exists() else 0,
            "ledger_sha256": sha256_file(ledger) if ledger.exists() else None,
            "pacing_ledger_sha256": sha256_file(pacing_ledger) if pacing_ledger.exists() else None,
            "authorization_closed": True,
            "later_stages_authorized": False,
        }
    closure = {
        "schema_version": 7,
        "authorization_id": auth["authorization_id"],
        "status": "closed_completed" if audit["status"] == "completed" else "closed_terminal_hard_stop",
        "open_authorization_sha256": auth_sha,
        "authorized_stage": "calibration",
        "authorization_exhausted": audit["provider_attempts"] >= 60,
        "paid_api_allowed": False,
        "provider_calls_allowed": False,
        "qwen_authorization_open": False,
        "formal_scaling_allowed": False,
        "later_stages_authorized": False,
        "ledger_sha256": audit["ledger_sha256"],
        "pacing_ledger_sha256": audit["pacing_ledger_sha256"],
    }
    write_json_atomic(artifact / "calibration_audit.json", audit)
    write_json_atomic(artifact / "authorization_closure.json", closure)
    write_json_atomic(artifact / "authorization_registry.json", {
        "schema_version": 7,
        "authorizations": {},
        "closed_authorizations": {auth["authorization_id"]: {"path": "../../configs/acl2027/phase2_calibration_live_authorization_v7.json", "sha256": auth_sha}},
    })
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-close", action="store_true")
    args = parser.parse_args()
    audit = close_authorization() if args.write_close else build_audit()
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
