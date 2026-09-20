"""Offline contracts for the authorized Phase 1L Flash confirmation."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from scripts.run_acl2027_phase1l_flash_confirmation import (
    DEFAULT_CONFIG,
    DEFAULT_STATE,
    SmokeError,
    execute_smoke,
    read_json,
    target_cells,
    validate_inputs,
)


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


def fake_response(request_id: str, content: str, input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        id=request_id,
        model="qwen3.6-flash",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


def write_state(path: Path, paid: bool = True) -> None:
    state = deepcopy(read_json(DEFAULT_STATE))
    state["execution_policy"]["paid_api_allowed"] = paid
    state["execution_policy"]["formal_scaling_allowed"] = False
    state["execution_policy"]["reason"] = "User authorized exactly two qwen3.6-flash calls, no retries; OfficeQA 24 and SpreadsheetBench 40 remain closed."
    state["current_phase"]["id"] = "1L"
    state["current_phase"]["status"] = "in_progress"
    path.write_text(json.dumps(state), encoding="utf-8")


def office_payload() -> dict:
    evidence = [
        {"source_path": "treasury_bulletin_1941_01.txt", "locator": f"month-{month:02d}", "period": f"1940-{month:02d}", "value": month}
        for month in range(1, 13)
    ]
    return {
        "answer": "2602",
        "evidence": evidence,
        "calculation": {
            "operation": "sum",
            "time_basis": "calendar",
            "operands": [{"period": row["period"], "value": row["value"]} for row in evidence],
            "result": 2602,
        },
    }


def spreadsheet_payload() -> dict:
    task_dir = Path("data/spreadsheetbench_verified_400/spreadsheet/45635")
    golden = next(task_dir.glob("*_golden.xlsx"))
    workbook = load_workbook(golden, data_only=False, read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    edits = [{"sheet": sheet.title, "cell": cell, "formula": sheet[cell].value} for cell in target_cells("B5:E7")]
    workbook.close()
    return {"target_range": "B5:E7", "edits": edits, "explanation": "apply the ranking formulas per target cell"}


def test_dry_run_is_bound_to_phase1k_flash_request_hashes():
    config, plan = validate_inputs(DEFAULT_CONFIG)
    result = execute_smoke(live=False)
    assert config["authorization"]["max_provider_attempts"] == 2
    assert [row["task_id"] for row in plan] == ["UID0001", "45635"]
    assert result["logical_calls"] == 0
    assert result["planned_calls"] == 2
    assert [row["request_hash"] for row in result["requests"]] == [
        "eef1697f5fca23c435544c38fe5aeba2ab0767fd74c620b947384a5599c31f10",
        "433dc7a0c34f55ef37ff5f19642635df51470f0ad1a645cb50ec73025e408bcc",
    ]


def test_fake_live_executes_two_calls_and_passes_both_task_gates(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    client = FakeClient([
        fake_response("office-ok", json.dumps(office_payload()), 100, 40),
        fake_response("sheet-ok", json.dumps(spreadsheet_payload()), 120, 80),
    ])
    output = tmp_path / "artifact"
    result = execute_smoke(state_path=state_path, output_dir=output, live=True, client=client)
    assert result["decision"] == "flash_task_valid_floor_passed_plus_not_needed"
    assert result["provider_attempts"] == 2
    assert result["usage"] == {"input_tokens": 220, "output_tokens": 120, "total_tokens": 340, "exact_for_successful_calls": True}
    assert len(client.chat.completions.calls) == 2
    assert all(call["extra_body"] == {"enable_thinking": False} for call in client.chat.completions.calls)
    records = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert all(record["task_valid"] is True for record in records)
    assert records[1]["task_validation"]["exact_formula_match"] is True


def test_task_invalid_first_response_is_charged_and_second_call_still_audited(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    client = FakeClient([
        fake_response("office-invalid", "{}", 11, 4),
        fake_response("sheet-ok", json.dumps(spreadsheet_payload()), 13, 7),
    ])
    output = tmp_path / "artifact"
    result = execute_smoke(state_path=state_path, output_dir=output, live=True, client=client)
    assert result["decision"] == "flash_task_valid_floor_failed_plus_review_required"
    assert result["provider_attempts"] == 2
    assert result["usage"] == {"input_tokens": 24, "output_tokens": 11, "total_tokens": 35, "exact_for_successful_calls": True}
    assert len(client.chat.completions.calls) == 2
    records = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert records[0]["status"] == "failed"
    assert records[0]["usage_known"] is True
    assert records[1]["task_valid"] is True


def test_live_refuses_closed_repository_permission(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, paid=False)
    with pytest.raises(PermissionError, match="paid permission"):
        execute_smoke(state_path=state_path, output_dir=tmp_path / "artifact", live=True, client=FakeClient([]))


def test_live_refuses_to_overwrite_artifact(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    output = tmp_path / "artifact"
    output.mkdir()
    with pytest.raises(SmokeError, match="refusing to overwrite"):
        execute_smoke(state_path=state_path, output_dir=output, live=True, client=FakeClient([]))
