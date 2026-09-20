import json

import pytest

from scripts.prepare_acl2027_phase1k_preflight import PreflightError, build_plan, run_preflight


def test_plan_is_four_calls_and_zero_network():
    config, plan, audit = build_plan()
    assert config["execution"]["provider_calls"] == 0
    assert len(plan) == 4
    assert audit["network_calls"] == 0
    assert audit["paid_api_calls"] == 0
    assert audit["preflight_pass"] is True


def test_pairing_is_content_fair_and_contracts_are_explicit():
    _, plan, audit = build_plan()
    assert audit["office_content_fair"] is True
    assert audit["spreadsheet_content_fair"] is True
    assert audit["office_operand_schema_explicit"] is True
    assert audit["spreadsheet_semantics_explicit"] is True
    assert [row["model"] for row in plan] == ["qwen3.6-flash", "qwen3.6-flash", "qwen3.8-max", "qwen3.8-max"]


def test_no_reference_or_golden_leakage():
    _, _, audit = build_plan()
    assert audit["reference_answer_leaked"] is False
    assert audit["golden_formula_leaked"] is False


def test_artifact_has_four_unique_request_files(tmp_path):
    output = tmp_path / "phase1k"
    manifest = run_preflight(output)
    assert manifest["available_runs"] == 4
    assert len({run["result_path"] for run in manifest["runs"]}) == 4
    for index in range(1, 5):
        assert json.loads((output / f"request_{index:02d}.json").read_text(encoding="utf-8"))
    with pytest.raises(PreflightError, match="refusing to overwrite"):
        run_preflight(output)
