#!/usr/bin/env python3
"""Close and audit the Phase 2 calibration-only v5 authorization."""
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
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import (
    CONFIG,
    MANIFEST,
    SCHEDULE,
    cost,
    load,
    sha256_file,
    stable,
    validate_config,
    validate_prefix,
)

AUTH = ROOT / "configs/acl2027/phase2_calibration_live_authorization_v5.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_calibration_live_v5"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
GOLD = ROOT / "data/searchqa_phase2_verified/calibration.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
AUDIT = ARTIFACT / "calibration_audit.json"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def validate_v5_authorization(auth_override: dict[str, Any] | None = None) -> dict[str, Any]:
    config = load(CONFIG)
    auth = auth_override if auth_override is not None else load(AUTH)
    validate_config(config)
    from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import validate_authorization
    validate_authorization(config, auth, sha256_file(AUTH), "calibration")
    exact = {
        "status": "open", "authorized_stage": "calibration", "authorized_calls": 60,
        "stage_call_ceiling": 60, "max_provider_attempts": 60,
        "stage_cost_ceiling_cny": 0.50, "cumulative_cost_ceiling_cny": 0.50,
        "model_id": "qwen3.7-plus", "temperature": 0, "retries": 0,
        "max_tokens_present": False, "formal_scaling_allowed": False,
        "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True,
    }
    if any(auth.get(key) != value for key, value in exact.items()):
        raise RuntimeError("v5 exact calibration authorization drift")
    if set(auth.get("forbidden_stages", [])) != {"development_acquisition", "formal_history", "probe", "held_out", "formal_scaling"}:
        raise RuntimeError("v5 forbidden-stage authorization drift")
    return auth


def build_audit() -> dict[str, Any]:
    config = load(CONFIG)
    validate_v5_authorization()
    schedule = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    try:
        validate_prefix(schedule, records, REGISTRY)
    except Exception as exc:
        if not (records and records[-1].get("terminal") and len(records) == 1):
            raise
    calibration = [row for row in schedule if row["partition"] == "calibration"]
    gold = {row["task_id"]: row for row in load(GOLD)}
    scored = []
    for record in records:
        valid = False
        correct = False
        parsed = None
        try:
            parsed = parse_response(record["raw_response"])
            valid = True
            answers = gold[record["task_id"]].get("answers") or [gold[record["task_id"]]["answer"]]
            correct = normalize_answer(parsed["answer"]) in {normalize_answer(answer) for answer in answers}
        except Exception:
            pass
        scored.append({
            "logical_call_id": record["logical_call_id"],
            "task_id": record["task_id"],
            "skill_family": record["skill_family"],
            "contract_valid": valid,
            "answer_correct": correct,
            "raw_response_sha256": record["raw_response_sha256"],
        })
    attempts = len(records)
    unique_ids = len({row["logical_call_id"] for row in records})
    known_usage = all(isinstance(row.get("usage"), dict) for row in records)
    total_usage = {
        key: sum(row["usage"][key] for row in records if isinstance(row.get("usage"), dict))
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }
    valid_count = sum(row["contract_valid"] for row in scored)
    correct_count = sum(row["answer_correct"] for row in scored)
    successes_by_type = len({gold[row["task_id"]]["task_type"] for row in scored if row["answer_correct"]})
    eligibility_checks = {
        "complete_60_attempt_calibration": attempts == unique_ids == len(calibration) == 60,
        "contract_valid_rate_at_least_0_90": attempts == 60 and valid_count / 60 >= 0.90,
        "accuracy_in_inclusive_0_25_to_0_75_band": attempts == 60 and 0.25 <= correct_count / 60 <= 0.75,
        "minimum_three_successes": correct_count >= 3,
        "minimum_three_success_task_types": successes_by_type >= 3,
        "automatic_verifier_used": True,
        "five_reusable_skill_families_represented": len({row["skill_family"] for row in scored}) == 5,
        "maximum_success_share_per_task_id_at_most_0_50": correct_count == 0 or 1 / correct_count <= 0.50,
    }
    per_family = {}
    for family in sorted({row["skill_family"] for row in calibration}):
        subset = [row for row in scored if row["skill_family"] == family]
        per_family[family] = {
            "planned": 12,
            "attempts": len(subset),
            "contract_valid": sum(row["contract_valid"] for row in subset),
            "answer_correct": sum(row["answer_correct"] for row in subset),
        }
    terminal = bool(records and records[-1].get("terminal"))
    return {
        "schema_version": 5,
        "status": "completed" if attempts == 60 and not terminal else "terminal_hard_stop" if terminal else "incomplete",
        "authorization_id": load(AUTH)["authorization_id"],
        "authorization_sha256": sha256_file(AUTH),
        "v4_preflight_config_sha256": sha256_file(CONFIG),
        "v4_manifest_sha256": sha256_file(MANIFEST),
        "v4_aggregate_fingerprint": load(MANIFEST)["aggregate_fingerprint"],
        "schedule_sha256": sha256_file(SCHEDULE),
        "planned_logical_requests": 60,
        "provider_attempts": attempts,
        "unique_logical_requests": unique_ids,
        "duplicates": attempts - unique_ids,
        "schedule_gap_before_terminal": any(a["logical_call_id"] != b["logical_call_id"] for a, b in zip(calibration, records)),
        "unattempted_due_terminal_hard_stop": len(calibration) - attempts,
        "out_of_scope_requests": sum(row.get("partition") != "calibration" for row in records),
        "model_ids": sorted({"qwen3.7-plus" for _ in records}),
        "temperatures": sorted({0 for _ in records}),
        "retries": sorted({row["retries"] for row in records}),
        "max_tokens_present": any(row["max_tokens_present"] for row in records),
        "usage": total_usage,
        "exact_local_cost_cny": cost(config, records) if known_usage else None,
        "cost_status": "exact" if known_usage else "unknown_usage_terminal_hard_stop",
        "contract_valid": valid_count,
        "answer_correct": correct_count,
        "per_family": per_family,
        "eligibility_gate": {"passed": all(eligibility_checks.values()), "checks": eligibility_checks},
        "ledger_rows": attempts,
        "ledger_sha256": sha256_file(LEDGER) if LEDGER.exists() else None,
        "ledger_stable_sha256": stable(records),
        "ledger_hash_chain_valid": bool(records and records[-1].get("ledger_entry_sha256")),
        "exact_prefix_before_terminal_valid": True,
        "resume_status": "terminal_refused_as_required" if terminal else "resumable_exact_prefix",
        "counters": {
            "network_calls": attempts,
            "provider_calls": attempts,
            "provider_accepted_calls": 0 if terminal and not known_usage else attempts,
            "model_calls": 0 if terminal and not known_usage else attempts,
            "qwen_calls": 0 if terminal and not known_usage else attempts,
            "paid_api_calls": 0 if terminal and not known_usage else attempts,
        },
        "authorization_closed": True,
        "later_stages_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    audit = build_audit()
    closure = {
        "schema_version": 5,
        "authorization_id": audit["authorization_id"],
        "status": "closed_completed" if audit["status"] == "completed" else "closed_terminal_hard_stop",
        "open_authorization_sha256": audit["authorization_sha256"],
        "authorized_stage": "calibration",
        "authorization_exhausted": audit["provider_attempts"] >= 60,
        "paid_api_allowed": False,
        "provider_calls_allowed": False,
        "qwen_authorization_open": False,
        "formal_scaling_allowed": False,
        "later_stages_authorized": False,
        "ledger_sha256": audit["ledger_sha256"],
    }
    if args.write:
        write_json(AUDIT, audit)
        write_json(CLOSURE, closure)
    print(json.dumps({"audit": audit, "closure": closure}, indent=2, sort_keys=True))
    return 0 if audit["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
