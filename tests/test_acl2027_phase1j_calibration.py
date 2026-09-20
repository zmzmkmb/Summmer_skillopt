import json

import pytest

from scripts.run_acl2027_phase1j_calibration import (
    CalibrationError,
    DEFAULT_CONFIG,
    diagnose_officeqa,
    diagnose_spreadsheet,
    load_inputs,
    recover_complete_edits,
    run_calibration,
)


def test_frozen_inputs_are_zero_network_and_hash_valid():
    config, rows = load_inputs(DEFAULT_CONFIG)
    assert config["execution"]["provider_calls"] == 0
    assert config["execution"]["network_calls_allowed"] is False
    assert [row["task_id"] for row in rows] == ["UID0001", "45635"]


def test_officeqa_channels_remain_independent_and_negative():
    config, rows = load_inputs(DEFAULT_CONFIG)
    result = diagnose_officeqa(config, rows[0])
    assert result["deterministic_evidence_sum"] == 2602
    assert result["reported_calculation_result"] == 2561
    assert result["diagnostic_channels"] == {
        "retrieval_or_provenance_failure": False,
        "operand_schema_failure": True,
        "arithmetic_failure": True,
        "answer_mismatch": True,
    }
    assert result["diagnostic_recovery_task_success"] is False


def test_partial_spreadsheet_json_recovers_only_complete_edit_objects():
    _, rows = load_inputs(DEFAULT_CONFIG)
    edits = recover_complete_edits(rows[1]["raw_text"])
    assert len(edits) == 12
    assert len({edit["cell"] for edit in edits}) == 12


def test_spreadsheet_channels_keep_truncation_and_semantic_failure():
    config, rows = load_inputs(DEFAULT_CONFIG)
    result, compact = diagnose_spreadsheet(config, rows[1])
    assert result["diagnostic_channels"] == {
        "json_completion_failure": True,
        "edit_schema_failure": True,
        "formula_semantics_failure": True,
    }
    assert result["golden_formula_mismatch_count"] == 12
    assert result["diagnostic_recovery_task_success"] is False
    assert compact["closes_as_json"] is True
    assert compact["within_6000_byte_guard"] is True


def test_calibration_writes_auditable_zero_call_artifact(tmp_path):
    output = tmp_path / "phase1j"
    manifest = run_calibration(output_dir=output)
    assert manifest["network_calls"] == 0
    assert manifest["paid_api_calls"] == 0
    assert manifest["available_runs"] == 2
    diagnostics = json.loads((output / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["source_phase1i_task_valid_labels_preserved"] is True
    assert diagnostics["model_assessment"]["qwen3.6_flash_currently_qualified"] is False


def test_calibration_refuses_to_overwrite(tmp_path):
    output = tmp_path / "phase1j"
    output.mkdir()
    with pytest.raises(CalibrationError, match="refusing to overwrite"):
        run_calibration(output_dir=output)
