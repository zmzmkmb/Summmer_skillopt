from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.prepare_acl2027_phase1v_calibration import (
    HardStop,
    PreflightError,
    SimulatedProvider,
    build_request_plan,
    execute_simulation,
    parse_response,
    run_preflight,
    validate_two_wiki_record,
    verify_response,
)


def test_plan_has_exact_order_and_private_gold_boundary() -> None:
    _, plan, private = build_request_plan()
    assert len(plan) == 24
    assert [row["task_family"] for row in plan] == ["SearchQA"] * 12 + ["2WikiMultiHopQA"] * 12
    assert len({row["request_hash"] for row in plan}) == 24
    assert all(set(row["request"]) == {"temperature", "messages"} for row in plan)
    assert all("answers" not in row and "answer_id" not in row for row in plan)
    assert all("answers" in private[row["logical_call_id"]] for row in plan)


def test_strengthened_source_gate_rejects_blanks_and_evidence_mismatch() -> None:
    _, _, private = build_request_plan()
    # Use a compact valid record because the gate is intentionally a public unit.
    record = {
        "id": "x", "question": "q", "answer": "a", "answer_id": "Q1",
        "supporting_evidence": [["T", 0]], "evidences": [["Q", "r", "A"]],
        "evidences_id": [["Q1", "r", "Q2"]], "context": [["T", ["sentence"]]],
    }
    validate_two_wiki_record(record)
    blank = deepcopy(record)
    blank["answer"] = " "
    with pytest.raises(PreflightError, match="blank"):
        validate_two_wiki_record(blank)
    unavailable_ids = deepcopy(record)
    unavailable_ids["evidences_id"] = []
    validate_two_wiki_record(unavailable_ids)
    mismatch = deepcopy(record)
    mismatch["evidences_id"].append(["Q2", "r", "Q3"])
    with pytest.raises(PreflightError, match="lengths differ"):
        validate_two_wiki_record(mismatch)
    assert private


def test_strict_parsers_and_private_verifiers() -> None:
    _, plan, private = build_request_plan()
    search = plan[0]
    search_private = private[search["logical_call_id"]]
    payload = parse_response("SearchQA", json.dumps({"answer": search_private["answers"][0]}))
    assert verify_response(payload, search_private)["joint_correct"]
    with pytest.raises(PreflightError, match="schema"):
        parse_response("SearchQA", json.dumps({"answer": "x", "extra": 1}))
    wiki = plan[12]
    wiki_private = private[wiki["logical_call_id"]]
    payload = {"answer": wiki_private["answers"][0], "supporting_evidence": wiki_private["supporting_evidence"]}
    assert verify_response(parse_response("2WikiMultiHopQA", json.dumps(payload)), wiki_private)["joint_correct"]
    payload["supporting_evidence"] = payload["supporting_evidence"][:-1]
    assert not verify_response(payload, wiki_private)["joint_correct"]


def test_known_usage_invalid_is_visible_and_resume_is_exact_prefix(tmp_path) -> None:
    _, plan, private = build_request_plan()
    provider = SimulatedProvider(plan, private, {1: "malformed", 2: "schema_invalid"})
    first = execute_simulation(plan, private, tmp_path / "run", provider, max_new_calls=3)
    second = execute_simulation(plan, private, tmp_path / "run", provider, max_new_calls=2)
    assert first["invalid_output_calls"] == 2
    assert first["usage"]["total_tokens"] == 54
    assert second["recorded_calls"] == 5
    assert provider.calls == 5


def test_unknown_usage_and_plan_drift_are_terminal(tmp_path) -> None:
    _, plan, private = build_request_plan()
    output = tmp_path / "unknown"
    result = execute_simulation(plan, private, output, SimulatedProvider(plan, private, {1: "unknown_usage"}))
    assert result["status"] == "hard_stopped"
    with pytest.raises(HardStop, match="not resumable"):
        execute_simulation(plan, private, output, SimulatedProvider(plan, private))
    resume = tmp_path / "resume"
    execute_simulation(plan, private, resume, SimulatedProvider(plan, private), max_new_calls=1)
    changed = deepcopy(plan)
    changed[0]["request"]["temperature"] = 1
    with pytest.raises(PreflightError, match="plan drift"):
        execute_simulation(changed, private, resume, SimulatedProvider(changed, private))


def test_full_preflight_is_zero_call_and_refuses_overwrite(tmp_path) -> None:
    output = tmp_path / "artifact"
    audit = run_preflight(output)
    assert all(audit["checks"].values())
    assert audit["provider_calls"] == audit["paid_api_calls"] == 0
    assert audit["request_count"] == 24
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_preflight(output)
