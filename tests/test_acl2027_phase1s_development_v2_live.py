from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from openpyxl import Workbook

from scripts.analyze_acl2027_phase1s_development import (
    AnalysisError,
    build_design_audit,
    expand_formula_regions,
    parse_numeric,
    score_spreadsheet,
)
from scripts.run_acl2027_phase1r_development import read_json
from scripts.run_acl2027_phase1r_development import RunnerError
from scripts.run_acl2027_phase1s_development_v2_live import (
    _cost_cny,
    assert_repository_authorized,
    validate_live_config,
)


def test_phase1s_v2_live_binds_authorized_plan() -> None:
    config, plan = validate_live_config()
    assert len(plan) == 192
    assert config["authorization_gate"]["authorized_calls"] == 192
    assert config["authorization_gate"]["authorized_model"] == "qwen3.7-plus"
    assert config["cost_control"]["accounting_ceiling"] == 2000.0
    assert all("max_tokens" not in row["request"] for row in plan)


def test_phase1s_v2_live_has_zero_retries_and_no_max() -> None:
    config, _ = validate_live_config()
    execution = config["execution"]
    assert execution["sdk_max_retries"] == 0
    assert execution["explicit_retries"] == 0
    assert execution["max_provider_attempts_per_logical_call"] == 1
    assert execution["request_interval_seconds"] == 1.0
    assert execution["model_id"] == "qwen3.7-plus"


def test_phase1s_v2_live_rejects_cap_drift(tmp_path) -> None:
    config, _ = validate_live_config()
    changed = deepcopy(config)
    changed["cost_control"]["accounting_ceiling"] = 200.0
    path = tmp_path / "config.json"
    import json
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(RunnerError, match="accounting"):
        validate_live_config(path)


def test_phase1s_v2_live_cost_is_local_accounting() -> None:
    config, _ = validate_live_config()
    assert _cost_cny(
        config,
        {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000},
    ) == pytest.approx(10.0)
    assert config["cost_control"]["accounting_ceiling_is_request_parameter"] is False
    assert config["cost_control"]["max_tokens_is_cost_control"] is False


def test_phase1s_v2_live_repository_permission_is_closed_after_run(
    monkeypatch,
) -> None:
    config, _ = validate_live_config()
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-" + "x" * 110)
    with pytest.raises(PermissionError, match="permission is closed"):
        assert_repository_authorized(config)


def test_phase1s_analysis_numeric_normalization_preserves_percent_scale() -> None:
    assert parse_numeric("2,602") == 2602
    assert parse_numeric("4.815%") == parse_numeric(4.815)
    assert parse_numeric("($1,234.5)") == parse_numeric("-1234.5")
    with pytest.raises(AnalysisError, match="non-numeric"):
        parse_numeric("about 2602")


def test_phase1s_analysis_expands_regions_and_rejects_overlap() -> None:
    response = {
        "target_range": "'Data'!B2:C3",
        "formula_regions": [
            {
                "range": "'Data'!B2:C3",
                "anchor_cell": "'Data'!B2",
                "formula": "=A2",
            }
        ],
    }
    sheet, formulas = expand_formula_regions(
        response,
        expected_target_range="'Data'!B2:C3",
        default_sheet="Data",
    )
    assert sheet == "Data"
    assert formulas == {"B2": "=A2", "C2": "=B2", "B3": "=A3", "C3": "=B3"}
    response["formula_regions"].append(
        {"range": "'Data'!C3", "anchor_cell": "'Data'!C3", "formula": "=1"}
    )
    with pytest.raises(AnalysisError, match="overlapping"):
        expand_formula_regions(
            response,
            expected_target_range="'Data'!B2:C3",
            default_sheet="Data",
        )


def test_phase1s_analysis_persists_and_scores_spreadsheet_formulas(
    tmp_path: Path,
) -> None:
    initial = tmp_path / "initial.xlsx"
    golden = tmp_path / "golden.xlsx"
    for path, formula in ((initial, None), (golden, "=A2")):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Data"
        if formula:
            sheet["B2"] = formula
            sheet["B3"] = "=A3"
        workbook.save(path)
        workbook.close()
    record = {
        "status": "completed",
        "decision": "execute",
        "response": {
            "target_range": "'Data'!B2:B3",
            "formula_regions": [
                {
                    "range": "'Data'!B2:B3",
                    "anchor_cell": "'Data'!B2",
                    "formula": "=A2",
                }
            ],
        },
    }
    score = score_spreadsheet(
        record,
        expected_target_range="'Data'!B2:B3",
        initial_workbook=initial,
        golden_workbook=golden,
        temp_root=tmp_path,
    )
    assert score["executed"] is True
    assert score["formula_matches"] == 2
    assert score["exact_task_correct"] is True


def test_phase1s_design_audit_exposes_gate_and_downstream_nonidentification() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = read_json(
        root
        / "artifacts/acl2027_phase1s_development_method_effect_live_v2"
        / "request_plan.json"
    )
    phase1p = read_json(
        root / "configs/acl2027/phase1p_contribution_aligned_protocol_v1.json"
    )
    audit = build_design_audit(plan, phase1p)
    assert audit["unique_request_bodies"] == 52
    assert audit["gate_label_pairs"] == 96
    assert audit["gate_label_pairs_with_identical_requests"] == 96
    assert audit["downstream_tasks_executed"] is False
    assert audit["claims_identified"]["probe_to_downstream_representativeness"] is False
