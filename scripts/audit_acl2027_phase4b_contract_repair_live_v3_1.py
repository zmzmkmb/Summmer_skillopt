#!/usr/bin/env python3
"""Audit the terminal Phase 4B-R3 prefix without retrying the orphan request."""
from __future__ import annotations

import json
import hashlib
import os
import string
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts import run_acl2027_phase4b_contract_repair_live_v3 as live

RUN = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3"
REPORT = ROOT / "paper/acl2027/results/phase4b_contract_repair_live_v3.md"
FINAL_STARTS = 73
FINAL_RESPONSES = 72
CLOSURE_STARTS = 67
CLOSURE_RESPONSES = 66
EXACT_KEYS = {
    "skill_assessments",
    "selected_skill_id",
    "evidence_sentence_ids",
    "extracted_operands",
    "intermediate_result",
    "final_answer",
}


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


def normalize(value: Any) -> str:
    text = str(value).lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in text.split() if token not in {"a", "an", "the"})


def visible_user(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["transport_projection"]["messages"][1]["content"])


def contract_valid(row: dict[str, Any], value: Any) -> tuple[bool, bool]:
    if not isinstance(value, dict) or set(value) != EXACT_KEYS:
        return False, False
    user = visible_user(row)
    candidate_ids = {str(item["candidate_id"]) for item in user["candidates"]}
    evidence_ids = {
        str(sentence["id"])
        for block in user["context"]
        for sentence in block["sentences"]
    }
    assessments = value["skill_assessments"]
    evidence = value["evidence_sentence_ids"]
    shape_valid = (
        isinstance(assessments, dict)
        and set(assessments) == candidate_ids
        and all(
            isinstance(item, dict)
            and isinstance(item.get("applicable"), bool)
            and isinstance(item.get("rationale"), str)
            for item in assessments.values()
        )
        and isinstance(value["selected_skill_id"], str)
        and value["selected_skill_id"] in set(user["available_skill_ids"])
        and isinstance(evidence, list)
        and bool(evidence)
        and isinstance(value["extracted_operands"], dict)
        and isinstance(value["intermediate_result"], str)
        and bool(value["intermediate_result"].strip())
        and isinstance(value["final_answer"], str)
        and bool(value["final_answer"].strip())
    )
    evidence_resolves = shape_valid and all(str(item) in evidence_ids for item in evidence)
    return shape_valid and evidence_resolves, evidence_resolves


def validate_orphan(rows: list[dict[str, Any]], starts: list[dict[str, Any]], auth_sha: str) -> dict[str, Any]:
    orphan = starts[-1]
    row = rows[FINAL_RESPONSES]
    expected_hash = stable({key: value for key, value in orphan.items() if key != "start_entry_sha256"})
    if (
        orphan.get("sequence") != FINAL_STARTS
        or orphan.get("logical_call_id") != row["logical_call_id"]
        or orphan.get("request_hash") != row["request_hash"]
        or orphan.get("request_body_sha256") != stable(row["canonical_request_body"])
        or orphan.get("authorization_sha256") != auth_sha
        or orphan.get("previous_start_entry_sha256") != starts[-2]["start_entry_sha256"]
        or orphan.get("start_entry_sha256") != expected_hash
    ):
        raise RuntimeError("orphan request-start entry drift")
    return {
        "sequence": orphan["sequence"],
        "logical_call_id": orphan["logical_call_id"],
        "request_hash": orphan["request_hash"],
        "start_entry_sha256": orphan["start_entry_sha256"],
        "response_record_exists": False,
        "retry_forbidden": True,
    }


def analyze() -> dict[str, Any]:
    rows = live.preflight()
    starts = load(live.STARTS)
    records = load(live.LEDGER)
    closure = load(live.CLOSURE)
    auth_sha = sha256_file(live.AUTH)
    if len(starts) != FINAL_STARTS or len(records) != FINAL_RESPONSES:
        raise RuntimeError("terminal prefix count drift")
    if closure.get("status") != "closed" or closure.get("provider_attempts") != CLOSURE_STARTS or closure.get("completed_calls") != CLOSURE_RESPONSES:
        raise RuntimeError("original closure provenance drift")
    live.validate_prefix(rows, starts[:FINAL_RESPONSES], records, auth_sha)
    orphan = validate_orphan(rows, starts, auth_sha)

    parsed_rows = 0
    valid_rows = 0
    evidence_rows = 0
    key_shapes: Counter[str] = Counter()
    condition_valid: Counter[str] = Counter()
    condition_rows: Counter[str] = Counter()
    answer_correct: Counter[str] = Counter()
    gold = {str(item["task_id"]): item for item in load(ROOT / "artifacts/acl2027_phase4b_contract_repair_preflight_v1/private_gold.json")}
    for row, record in zip(rows, records):
        if row["logical_call_id"] != record["logical_call_id"] or row["request_hash"] != record["request_hash"]:
            raise RuntimeError("response ledger identity drift")
        condition = str(row["condition"])
        condition_rows[condition] += 1
        try:
            value = json.loads(record["raw_response"])
        except (TypeError, json.JSONDecodeError):
            value = None
        parsed_rows += int(value is not None)
        key_shapes["|".join(sorted(value)) if isinstance(value, dict) else "PARSE_ERROR"] += 1
        valid, evidence_resolves = contract_valid(row, value)
        valid_rows += int(valid)
        evidence_rows += int(evidence_resolves)
        condition_valid[condition] += int(valid)
        if isinstance(value, dict):
            answer_correct[condition] += int(
                normalize(value.get("final_answer", "")) == normalize(gold[str(row["task_id"])]["target_answer"])
            )

    known_cost = round(sum(float(record["local_cost_cny"]) for record in records), 6)
    input_tokens = sum(int(record["usage"]["input_tokens"]) for record in records)
    output_tokens = sum(int(record["usage"]["output_tokens"]) for record in records)
    total_tokens = sum(int(record["usage"]["total_tokens"]) for record in records)
    result = {
        "schema_version": 1,
        "experiment": "acl2027_phase4b_contract_repair_live_v3",
        "status": "terminal_closed_incomplete",
        "decision": "no_gate_incomplete_terminal_prefix",
        "planned_calls": 100,
        "request_starts": FINAL_STARTS,
        "conservatively_counted_provider_attempts": FINAL_STARTS,
        "completed_responses": FINAL_RESPONSES,
        "orphan_request_starts": 1,
        "unattempted_rows": 100 - FINAL_STARTS,
        "original_closure_snapshot": {
            "request_starts": CLOSURE_STARTS,
            "completed_responses": CLOSURE_RESPONSES,
            "reason": closure["reason"],
            "closure_sha256": sha256_file(live.CLOSURE),
        },
        "post_closure_process_tail": {
            "additional_request_starts": FINAL_STARTS - CLOSURE_STARTS,
            "additional_completed_responses": FINAL_RESPONSES - CLOSURE_RESPONSES,
            "cause": "external_command_timeout_left_child_process_running_until_explicit_termination",
            "authorization_not_reopened": True,
        },
        "orphan_request": orphan,
        "authorization_provenance": {
            "authorization_received_date": "2026-08-18",
            "preflight_authorization_statement_sha256": hashlib.sha256(
                load(live.PREFLIGHT_REQUEST)["authorization_statement_verbatim"].encode("utf-8")
            ).hexdigest(),
            "receipt_recorded_statement_sha256": load(live.RECEIPT)["authorization_statement_sha256"],
            "receipt_hash_matches_preflight_statement": (
                load(live.RECEIPT)["authorization_statement_sha256"]
                == hashlib.sha256(load(live.PREFLIGHT_REQUEST)["authorization_statement_verbatim"].encode("utf-8")).hexdigest()
            ),
            "formatting_note": "The user supplied the full authorization content, with the endpoint rendered as a Markdown link; execution treated the visible endpoint text and all frozen terms as equivalent to the requested statement.",
        },
        "prefix_integrity": {
            "completed_response_prefix_hash_chain_valid": True,
            "orphan_start_hash_chain_valid": True,
            "request_start_pacing_valid": all(
                later["request_started_at_unix_ns"] - earlier["request_started_at_unix_ns"] >= live.INTERVAL_NS
                for earlier, later in zip(starts, starts[1:])
            ),
            "retries": 0,
        },
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "known_stage_cost_cny": known_cost,
            "known_cumulative_cost_cny": round(live.PRIOR_COST + known_cost, 6),
            "orphan_usage_unknown": True,
        },
        "partial_non_gating_contract_diagnostic": {
            "rows": FINAL_RESPONSES,
            "json_parse_valid_rows": parsed_rows,
            "contract_valid_rows": valid_rows,
            "contract_valid_rate": valid_rows / FINAL_RESPONSES,
            "evidence_ids_resolve_rows": evidence_rows,
            "condition_rows": dict(sorted(condition_rows.items())),
            "condition_contract_valid_rows": dict(sorted(condition_valid.items())),
            "response_key_shapes": dict(sorted(key_shapes.items())),
            "descriptive_answer_correct": dict(sorted(answer_correct.items())),
            "cannot_trigger_frozen_gate": True,
        },
        "bindings": {
            "receipt_sha256": sha256_file(live.RECEIPT),
            "authorization_open_sha256": sha256_file(live.AUTH),
            "request_start_ledger_sha256": sha256_file(live.STARTS),
            "response_ledger_sha256": sha256_file(live.LEDGER),
            "run_audit_sha256": sha256_file(live.AUDIT),
            "runner_sha256": sha256_file(Path(live.__file__).resolve()),
        },
        "authorization_closed": True,
        "retry_or_resume_authorized": False,
        "phase4c_authorized": False,
        "replication_authorized": False,
        "cross_domain_scaling_authorized": False,
        "formal_scaling_authorized": False,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_outputs(result: dict[str, Any]) -> None:
    write(RUN / "terminal_audit_v3_1.json", result)
    write(RUN / "completion_manifest.json", {
        "schema_version": 1,
        "experiment": result["experiment"],
        "status": "complete",
        "completion_kind": "terminal_closed_partial_live_calibration",
        "planned_calls": 100,
        "completed_calls": FINAL_RESPONSES,
        "rows": FINAL_RESPONSES,
        "provider_calls_executed": FINAL_STARTS,
        "orphan_request_starts": 1,
        "decision": result["decision"],
        "phase4c_authorized": False,
        "aggregate_fingerprint": result["aggregate_fingerprint"],
    })
    diagnostic = result["partial_non_gating_contract_diagnostic"]
    usage = result["usage"]
    REPORT.write_text(
        "# Phase 4B-R3 repaired development calibration\n\n"
        "The explicitly authorized run is terminally closed and incomplete. An external command timeout left the Python child process running; it was explicitly terminated after 73 request-start entries and 72 complete responses. The final start has no response record and is conservatively treated as a spent provider attempt. It must never be retried.\n\n"
        "The first 72 response rows and all 73 request-start rows have valid hash chains and valid one-second pacing. The original closure snapshot was written at 67 starts and 66 responses; six additional starts and six responses arrived before the background process was terminated. Authorization was not reopened.\n\n"
        f"Known usage for the 72 recorded responses is {usage['total_tokens']:,} tokens and CNY {usage['known_stage_cost_cny']:.6f}; known cumulative cost is CNY {usage['known_cumulative_cost_cny']:.6f}. Usage for the orphan attempt is unknown.\n\n"
        f"The partial non-gating diagnostic finds {diagnostic['contract_valid_rows']}/{FINAL_RESPONSES} strict contract-valid responses ({diagnostic['contract_valid_rate']:.3f}). Because the frozen 100-row calibration did not complete, no Phase 4B calibration gate is evaluated and Phase 4C remains unauthorized.\n\n"
        f"Terminal audit fingerprint: `{result['aggregate_fingerprint']}`.\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    value = analyze()
    write_outputs(value)
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2))
