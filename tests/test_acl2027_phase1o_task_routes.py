from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from scripts.analyze_acl2027_phase1o_task_routes import (
    DEFAULT_CONFIG,
    AdjudicationError,
    construct_officeqa_from_frozen_run,
    construct_spreadsheet_formulas,
    evaluate_officeqa_construction,
    evaluate_spreadsheet_construction,
    execute_adjudication,
    validate_config,
)

ROOT = Path(__file__).resolve().parents[1]
PHASE1N = ROOT / "artifacts/acl2027_phase1n_plus_live_confirmation_v1"
OFFICE_REFERENCE = ROOT / "data/officeqa_verified/officeqa_full.csv"
SHEET_DIR = ROOT / "data/spreadsheetbench_verified_400/spreadsheet/45635"


def test_config_freezes_zero_network_and_constructor_boundaries():
    config = validate_config(DEFAULT_CONFIG)
    assert config["execution"]["network_calls_allowed"] is False
    assert config["execution"]["paid_api_allowed"] is False
    assert config["execution"]["provider_calls"] == 0
    assert config["constructors"]["officeqa"]["allowed_inputs"] == ["officeqa_phase1n_run"]
    assert config["constructors"]["spreadsheetbench"]["allowed_inputs"] == ["spreadsheetbench_initial_workbook"]


def test_constructor_signatures_cannot_receive_reference_or_golden_paths():
    office_params = set(inspect.signature(construct_officeqa_from_frozen_run).parameters)
    sheet_params = set(inspect.signature(construct_spreadsheet_formulas).parameters)
    forbidden = {"reference", "reference_path", "reference_csv", "golden", "golden_path", "golden_workbook"}
    assert not office_params & forbidden
    assert not sheet_params & forbidden
    with pytest.raises(TypeError):
        construct_officeqa_from_frozen_run(  # type: ignore[call-arg]
            PHASE1N / "run_01.json", Path("unused.json"), task_id="UID0001",
            required_time_basis="calendar", expected_period_count=12, reference_csv=OFFICE_REFERENCE,
        )


def test_officeqa_recomputes_before_independent_reference_scoring(tmp_path):
    construction = tmp_path / "office.json"
    record = construct_officeqa_from_frozen_run(
        PHASE1N / "run_01.json", construction,
        task_id="UID0001", required_time_basis="calendar", expected_period_count=12,
    )
    assert construction.is_file()
    assert record["reference_accessed"] is False
    assert record["recomputed_answer"] == 2602
    assert record["model_answer"] == 2498
    assert record["execution_decision"] == "execute"
    evaluation = evaluate_officeqa_construction(construction, OFFICE_REFERENCE, task_id="UID0001")
    assert evaluation["exact_answer_match"] is True
    assert evaluation["route_decision"] == "keep_with_deterministic_executor_and_abstain_on_evidence_mismatch"


def test_spreadsheet_constructor_has_no_golden_access_and_scores_12_of_12(tmp_path):
    construction = tmp_path / "sheet.json"
    generated = tmp_path / "generated.xlsx"
    record = construct_spreadsheet_formulas(
        SHEET_DIR / "1_45635_init.xlsx", generated, construction,
        task_id="45635", target_range="B5:E7", source_rows=[1, 2, 3], points_per_column=6,
    )
    assert construction.is_file() and generated.is_file()
    assert record["golden_accessed"] is False
    assert len(record["payload"]["edits"]) == 12
    assert record["payload"]["edits"][0]["formula"] == "=IF(B1=MAX(B$1:B$3),6/COUNTIF(B$1:B$3,MAX(B$1:B$3)),0)"
    evaluation = evaluate_spreadsheet_construction(
        construction, generated, SHEET_DIR / "1_45635_golden.xlsx",
        task_id="45635", target_range="B5:E7",
    )
    assert evaluation["exact_formula_matches"] == 12
    assert evaluation["mismatch_count"] == 0
    assert evaluation["route_decision"] == "redesign_as_constrained_executor_backed_task"


def test_execute_records_zero_calls_and_refuses_overwrite(tmp_path):
    output = tmp_path / "phase1o"
    manifest = execute_adjudication(config_path=DEFAULT_CONFIG, output_dir=output)
    assert manifest["expected_runs"] == manifest["available_runs"] == 2
    assert manifest["network_calls"] == manifest["paid_api_calls"] == manifest["provider_attempts"] == 0
    assert manifest["constructor_leakage_audit"]["passed"] is True
    assert manifest["decision"] == "task_routes_retained_with_executor_backing"
    with pytest.raises(AdjudicationError, match="refusing to overwrite"):
        execute_adjudication(config_path=DEFAULT_CONFIG, output_dir=output)
