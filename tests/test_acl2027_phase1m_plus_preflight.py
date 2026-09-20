"""Contracts for the zero-network Phase 1M Plus preflight."""
import json

import pytest

from scripts.prepare_acl2027_phase1m_plus_preflight import PreflightError, build_plan, run_preflight


def test_plan_has_two_plus_requests_and_zero_calls():
    config, plan, audit = build_plan()
    assert config["execution"]["provider_calls"] == 0
    assert [item["model"] for item in plan] == ["qwen3.7-plus", "qwen3.7-plus"]
    assert [item["task_id"] for item in plan] == ["UID0001", "45635"]
    assert audit["network_calls"] == 0
    assert audit["paid_api_calls"] == 0
    assert audit["preflight_pass"] is True


def test_client_output_cap_is_completely_omitted():
    _, plan, audit = build_plan()
    assert audit["source_caps_detected"] is True
    assert audit["max_tokens_omitted"] is True
    assert all("max_tokens" not in item["request"] for item in plan)


def test_messages_are_identical_and_no_answers_leak():
    _, plan, audit = build_plan()
    assert audit["messages_identical_to_phase1k"] is True
    assert audit["office_operand_schema_explicit"] is True
    assert audit["spreadsheet_semantics_explicit"] is True
    assert audit["reference_answer_leaked"] is False
    assert audit["golden_formula_leaked"] is False
    assert all(item["message_hash"] == item["source_message_hash"] for item in plan)


def test_artifact_has_two_unique_request_files(tmp_path):
    output = tmp_path / "phase1m"
    manifest = run_preflight(output)
    assert manifest["available_runs"] == 2
    assert manifest["network_calls"] == 0
    assert len({run["result_path"] for run in manifest["runs"]}) == 2
    for index in range(1, 3):
        row = json.loads((output / f"request_{index:02d}.json").read_text(encoding="utf-8"))
        assert "max_tokens" not in row["request"]
    with pytest.raises(PreflightError, match="refusing to overwrite"):
        run_preflight(output)