#!/usr/bin/env python3
"""Additive audit correction for the terminal v27 failure-analysis run."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import usage

ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
AUTH = ARTIFACT / "authorization_open.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
ORIGINAL_AUDIT = ARTIFACT / "run_audit.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_design_preflight_v26/future_schedule.json"
OUTPUT = ARTIFACT / "run_audit_v27_1.json"


class AuditError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def call_cost(tokens: dict[str, int]) -> float:
    return round((tokens["input_tokens"] * 2.0 + tokens["output_tokens"] * 8.0) / 1_000_000, 6)


def build() -> dict[str, Any]:
    records, starts = load(LEDGER), load(PACING)
    auth, closure, original = load(AUTH), load(CLOSURE), load(ORIGINAL_AUDIT)
    planned = load(SCHEDULE)["schedule"]
    if len(records) != len(starts) or len(records) != 1073:
        raise AuditError("v27 terminal prefix length drift")
    if closure.get("status") != "closed" or auth.get("status") != "open" or original.get("status") != "terminal_hard_stop":
        raise AuditError("v27 authorization/audit closure drift")
    for index, (record, start, row) in enumerate(zip(records, starts, planned), 1):
        if record.get("logical_call_id") != row.get("logical_call_id") or record.get("request_hash") != row.get("request_hash") or start.get("request_hash") != row.get("request_hash"):
            raise AuditError("v27 non-prefix provenance")
        if record.get("provider_attempt_index") != index or record.get("retries") != 0:
            raise AuditError("v27 attempt accounting drift")
        if record.get("ledger_entry_sha256") != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise AuditError("v27 ledger hash drift")
        if start.get("start_entry_sha256") != stable({key: value for key, value in start.items() if key != "start_entry_sha256"}):
            raise AuditError("v27 request-start hash drift")
    completed, terminal = records[:-1], records[-1]
    if any(row.get("status") != "completed" or row.get("terminal") for row in completed):
        raise AuditError("v27 completed prefix drift")
    if terminal.get("status") != "hard_stop" or terminal.get("terminal") is not True or "HTTP Error 400" not in str(terminal.get("error")):
        raise AuditError("v27 terminal row drift")
    if terminal.get("request_id") != completed[-1].get("request_id") or terminal.get("raw_response_sha256") != completed[-1].get("raw_response_sha256"):
        raise AuditError("v27 stale-response signature drift")
    provider_ids = [row.get("request_id") for row in completed]
    if len(set(provider_ids)) != len(completed) or any(not value for value in provider_ids):
        raise AuditError("v27 completed provider identity drift")
    tokens = [usage(row) for row in completed]
    known_cost = round(sum(call_cost(value) for value in tokens), 6)
    result = {
        "schema_version": "27.1",
        "status": "terminal_hard_stop_additive_correction",
        "planned_calls": 1600,
        "provider_attempts": 1073,
        "completed_calls": 1072,
        "terminal_rows": 1,
        "skipped_after_hard_stop": 527,
        "unique_spent_logical_requests": 1073,
        "unique_completed_provider_response_ids": 1072,
        "terminal_usage_status": "unknown_stale_previous_response_was_copied_into_terminal_record",
        "usage_known_for_all_attempts": False,
        "known_input_tokens": sum(value["input_tokens"] for value in tokens),
        "known_output_tokens": sum(value["output_tokens"] for value in tokens),
        "known_total_tokens": sum(value["total_tokens"] for value in tokens),
        "exact_local_cost_cny": None,
        "known_local_cost_lower_bound_cny": known_cost,
        "retries": 0,
        "request_start_pacing_valid": all(second["request_started_at_unix_ns"] - first["request_started_at_unix_ns"] >= 1_000_000_000 for first, second in zip(starts, starts[1:])),
        "authorization_closed": True,
        "analysis_gate_reached": False,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "bindings": {
            "authorization_sha256": sha256_file(AUTH),
            "ledger_sha256": sha256_file(LEDGER),
            "request_start_ledger_sha256": sha256_file(PACING),
            "closure_sha256": sha256_file(CLOSURE),
            "original_audit_sha256": sha256_file(ORIGINAL_AUDIT),
            "v26_schedule_sha256": sha256_file(SCHEDULE),
        },
    }
    return result


if __name__ == "__main__":
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
