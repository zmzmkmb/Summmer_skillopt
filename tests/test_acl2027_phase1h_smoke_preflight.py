"""Contracts for the Phase 1H zero-network repaired smoke preflight."""
from __future__ import annotations

import json

import pytest

from scripts.prepare_acl2027_phase1h_smoke import (
    DEFAULT_CONFIG,
    PreflightError,
    audit_plan,
    build_request_plan,
    prepare,
    validate_config,
)


def test_preflight_builds_exact_frozen_two_family_plan():
    audit, plan = prepare()
    assert [row["task_family"] for row in plan] == ["OfficeQA", "SpreadsheetBench"]
    assert [row["task_id"] for row in plan] == ["UID0001", "45635"]
    assert all(len(row["request_hash"]) == 64 for row in plan)
    assert audit["decision"] == "preflight_passed_paid_successor_still_closed"
    assert all(audit["checks"].values())
    assert audit["network_calls"] == audit["paid_api_calls"] == 0


def test_office_prompt_requires_provenance_and_calendar_calculation_without_reference_answer():
    config = validate_config()
    office = build_request_plan(config)[0]
    prompt = json.dumps(office["request"]["messages"], ensure_ascii=True)
    for token in ("answer", "evidence", "calculation", "source_path", "locator", "period", "value", "operation", "time_basis", "operands", "result"):
        assert token in prompt
    assert "12 monthly operands" in prompt
    assert "fiscal-year" in prompt
    assert "2602" not in prompt


def test_spreadsheet_prompt_requires_exact_per_cell_edits_without_golden_formula():
    config = validate_config()
    spreadsheet = build_request_plan(config)[1]
    prompt = json.dumps(spreadsheet["request"]["messages"], ensure_ascii=True)
    for token in ("target_range", "edits", "explanation", "sheet", "cell", "formula", "B5:E7", "12 edits"):
        assert token in prompt
    assert "golden" not in prompt.lower()
    assert "=IF(" not in prompt


def test_preflight_config_can_never_authorize_live_execution(tmp_path):
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["execution"]["network_calls_allowed"] = True
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(PreflightError, match="must disable"):
        validate_config(path)


def test_audit_fails_when_schema_language_is_removed():
    config = validate_config()
    plan = build_request_plan(config)
    plan[0]["request"]["messages"][0]["content"] = "Return JSON."
    audit = audit_plan(config, plan)
    assert audit["checks"]["office_repaired_schema_present"] is False
    assert audit["decision"] == "preflight_failed_paid_successor_closed"