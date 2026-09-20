#!/usr/bin/env python3
"""Frozen strict analysis for the completed Phase 4B development calibration."""
from __future__ import annotations

import json
import os
import string
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

PREFLIGHT = ROOT / "artifacts/acl2027_phase4b_development_live_preflight_v1"
DESIGN = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1"
RUN = ROOT / "artifacts/acl2027_phase4b_development_live_v3"
V2 = ROOT / "artifacts/acl2027_phase4b_development_live_v2"
REPORT = ROOT / "paper/acl2027/results/phase4b_development_live_v3.md"
EXPECTED_KEYS = {"skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize(value: Any) -> str:
    text = str(value).lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in text.split() if token not in {"a", "an", "the"})


def contract_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == EXPECTED_KEYS
        and isinstance(value["skill_assessments"], (dict, list))
        and isinstance(value["selected_skill_id"], str)
        and isinstance(value["evidence_sentence_ids"], list)
        and bool(value["evidence_sentence_ids"])
        and isinstance(value["extracted_operands"], dict)
        and isinstance(value["intermediate_result"], str)
        and bool(value["intermediate_result"].strip())
        and isinstance(value["final_answer"], str)
        and bool(value["final_answer"].strip())
    )


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def analyze() -> dict[str, Any]:
    schedule = load(PREFLIGHT / "development_schedule.json")["rows"]
    ledger = load(RUN / "ledger.json")
    starts = load(RUN / "request_start_ledger.json")
    audit = load(RUN / "run_audit.json")
    gold = {row["task_id"]: row for row in load(DESIGN / "private_gold.json") if row["split"] == "development"}
    if len(schedule) != len(ledger) != len(starts):
        raise RuntimeError("Phase 4B schedule/ledger length drift")
    if len(schedule) != 100 or audit.get("completed_calls") != 100 or not audit.get("authorization_closed"):
        raise RuntimeError("Phase 4B execution is not complete and closed")

    parsed = []
    key_shapes: Counter[tuple[str, ...]] = Counter()
    valid_rows = 0
    answer_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    family_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    contextual_selected = 0
    contextual_assessable = 0
    evidence_assessable = 0

    for row, record in zip(schedule, ledger):
        if row["logical_call_id"] != record["logical_call_id"] or row["request_hash"] != record["request_hash"]:
            raise RuntimeError("Phase 4B ledger order or identity drift")
        try:
            value = json.loads(record["raw_response"])
        except (TypeError, json.JSONDecodeError):
            value = None
        parsed.append(value)
        key_shapes[tuple(sorted(value)) if isinstance(value, dict) else ("PARSE_ERROR",)] += 1
        valid = contract_valid(value)
        valid_rows += int(valid)
        if valid:
            evidence_assessable += 1
            if row["condition"] == "contextual_typed":
                contextual_assessable += 1
                contextual_selected += int(value["selected_skill_id"] == row["canonical_request_body"]["expected_selected_skill_id"])
        if isinstance(value, dict):
            answer = value.get("final_answer", value.get("answer", ""))
        else:
            answer = ""
        target = gold[row["task_id"]]["target_answer"]
        correct = int(normalize(answer) == normalize(target))
        answer_counts[row["condition"]][0] += correct
        answer_counts[row["condition"]][1] += 1
        family_key = f"{gold[row['task_id']]['skill_family']}::{row['condition']}"
        family_counts[family_key][0] += correct
        family_counts[family_key][1] += 1

    rate = valid_rows / len(schedule)
    result = {
        "schema_version": 1,
        "experiment": "acl2027_phase4b_development_live_v3",
        "status": "completed_stop_before_phase4c",
        "decision": "stop_contract_calibration_failed",
        "strict_metrics": {
            "rows": len(schedule),
            "json_parse_valid_rows": sum(value is not None for value in parsed),
            "contract_valid_rows": valid_rows,
            "contract_valid_rate": rate,
            "contract_valid_threshold": 0.95,
            "contextual_selection_assessable_rows": contextual_assessable,
            "contextual_selection_rate": contextual_selected / contextual_assessable if contextual_assessable else None,
            "contextual_selection_threshold": 0.90,
            "evidence_extraction_assessable_rows": evidence_assessable,
            "evidence_extraction_reliably_verifiable": evidence_assessable == len(schedule),
        },
        "response_key_shapes": {"|".join(keys): count for keys, count in sorted(key_shapes.items())},
        "non_gating_descriptive_answer_accuracy": {condition: {"correct": counts[0], "rows": counts[1], "rate": counts[0] / counts[1]} for condition, counts in sorted(answer_counts.items())},
        "non_gating_family_answer_accuracy": {key: {"correct": counts[0], "rows": counts[1], "rate": counts[0] / counts[1]} for key, counts in sorted(family_counts.items())},
        "execution": audit,
        "prior_zero_call_record": {
            "v2_closure_sha256": sha256_file(V2 / "authorization_closure.json"),
            "v2_provider_call_correction_sha256": sha256_file(V2 / "provider_call_correction_v2_1.json"),
            "corrected_provider_calls": 0,
        },
        "bindings": {
            "schedule_sha256": sha256_file(PREFLIGHT / "development_schedule.json"),
            "ledger_sha256": sha256_file(RUN / "ledger.json"),
            "request_start_ledger_sha256": sha256_file(RUN / "request_start_ledger.json"),
            "run_audit_sha256": sha256_file(RUN / "run_audit.json"),
            "authorization_closure_sha256": sha256_file(RUN / "authorization_closure.json"),
        },
        "phase4c_authorized": False,
        "network_calls": 100,
        "provider_calls": 100,
        "paid_api_calls": 100,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_outputs(result: dict[str, Any]) -> None:
    atomic_text(RUN / "development_analysis.json", json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n")
    completion = {"schema_version": 1, "experiment": result["experiment"], "status": "complete", "completion_kind": "closed_live_development_calibration", "planned_calls": 100, "completed_calls": 100, "rows": 100, "provider_calls_executed": 100, "decision": result["decision"], "phase4c_authorized": False, "aggregate_fingerprint": result["aggregate_fingerprint"]}
    atomic_text(RUN / "completion_manifest.json", json.dumps(completion, ensure_ascii=True, sort_keys=True, indent=2) + "\n")
    metrics = result["strict_metrics"]
    atomic_text(REPORT,
        "# Phase 4B development calibration live v3\n\n"
        "The explicitly authorized execution completed 100/100 qwen3.7-plus calls with zero retries, valid request-start pacing, exact usage accounting, and automatic authorization closure. "
        f"It used {result['execution']['total_tokens']:,} exact tokens and CNY {result['execution']['exact_stage_cost_cny']:.6f}; known cumulative cost is CNY {result['execution']['known_cumulative_cost_lower_bound_cny']:.6f}.\n\n"
        f"Strict contract validity was {metrics['contract_valid_rows']}/100 ({metrics['contract_valid_rate']:.3f}), below the frozen 0.95 calibration threshold. All 100 responses were JSON-parseable, but none returned the required six-field evidence-grounded contract. Contextual selection and evidence grounding are therefore not strictly assessable. The frozen Phase 4B stop rule fires, and Phase 4C remains unauthorized.\n\n"
        "Descriptive answer extraction is non-gating because it comes from contract-invalid responses. It must not override the calibration failure.\n\n"
        f"Analysis fingerprint: `{result['aggregate_fingerprint']}`.\n",
    )


if __name__ == "__main__":
    result = analyze()
    write_outputs(result)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
