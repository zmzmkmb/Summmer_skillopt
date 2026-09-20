#!/usr/bin/env python3
"""Additive unknown-usage correction for terminal Phase 2 probe v14."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_only_live_v14"
AUTH = ROOT / "configs/acl2027/phase2_probe_only_authorization_v14.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
OUTPUT = ARTIFACT / "run_audit_v14_1.json"


class AuditError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> dict[str, Any]:
    records = load(LEDGER)
    starts = load(PACING)
    auth = load(AUTH)
    closure = load(CLOSURE)
    probe = [r for r in load(SCHEDULE)["schedule"] if r.get("partition") == "probe"]
    if len(records) != len(starts) != 0 or len(records) != 1:
        raise AuditError("expected one aligned terminal attempt")
    record, start, planned = records[0], starts[0], probe[0]
    if any(record.get(k) != planned.get(k) for k in ("logical_call_id", "request_hash", "task_id", "skill_family", "condition", "staged_execution_index")):
        raise AuditError("schedule binding drift")
    if record.get("ledger_entry_sha256") != stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}):
        raise AuditError("ledger hash drift")
    if start.get("start_entry_sha256") != stable({k: v for k, v in start.items() if k != "start_entry_sha256"}):
        raise AuditError("request-start hash drift")
    if record.get("status") != "hard_stop" or record.get("terminal") is not True or record.get("usage") is not None:
        raise AuditError("terminal unknown-usage semantics drift")
    if record.get("authorization_sha256") != sha256_file(AUTH) or closure.get("status") != "closed":
        raise AuditError("authorization closure drift")
    if auth.get("model_id") != "qwen3.7-plus" or auth.get("temperature") != 0 or auth.get("retries") != 0 or auth.get("max_tokens_present") is not False:
        raise AuditError("request policy drift")
    return {
        "schema_version": "14.1", "status": "terminal_hard_stop", "planned_calls": 160,
        "provider_attempts": 1, "unique_logical_requests": 1, "completed_calls": 0,
        "terminal_rows": 1, "duplicates": 0, "skipped_after_hard_stop": 159,
        "usage_known_for_all_attempts": False, "input_tokens": None, "output_tokens": None,
        "total_tokens": None, "exact_local_cost_cny": None, "known_token_lower_bound": 0,
        "known_cost_lower_bound_cny": 0.0, "retries": 0, "max_tokens_present": False,
        "model_id": "qwen3.7-plus", "temperature": 0, "probe_gate_reached": False,
        "probe_gate_passed": False, "authorization_closed": True, "held_out_calls": 0,
        "formal_scaling_calls": 0, "terminal_error": record.get("error"),
        "bindings": {"authorization_sha256": sha256_file(AUTH), "ledger_sha256": sha256_file(LEDGER), "request_start_ledger_sha256": sha256_file(PACING), "closure_sha256": sha256_file(CLOSURE), "schedule_sha256": sha256_file(SCHEDULE)},
    }


if __name__ == "__main__":
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
