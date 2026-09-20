"""Offline contracts for the Phase 1F bounded live smoke runner."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_acl2027_phase1f_smoke import (
    DEFAULT_CONFIG,
    DEFAULT_STATE,
    SmokeError,
    build_smoke_plan,
    execute_smoke,
    read_json,
    validate_inputs,
)


class FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
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
    state["execution_policy"]["reason"] = (
        "User authorized the two-call bounded smoke; this does not authorize the 24/40 batch."
    )
    state["current_phase"]["id"] = "1F"
    state["current_phase"]["status"] = "in_progress"
    path.write_text(json.dumps(state), encoding="utf-8")


def test_dry_run_builds_exact_frozen_two_family_plan():
    result = execute_smoke(live=False)
    assert result["logical_calls"] == 0
    assert result["planned_calls"] == 2
    assert [row["task_family"] for row in result["requests"]] == ["OfficeQA", "SpreadsheetBench"]
    config = validate_inputs(DEFAULT_CONFIG)
    plan = build_smoke_plan(config)
    assert [row["task_id"] for row in plan] == ["UID0001", "45635"]
    assert all(row["request_hash"] for row in plan)


def test_live_fake_client_issues_exactly_two_calls_and_writes_exact_usage(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    client = FakeClient([
        fake_response("office-1", '{"answer":"2602","evidence":"sum of the 1940 monthly national defense entries"}', 120, 20),
        fake_response("sheet-1", '{"formula":"=IF(B$4=MAX($B$4:$E$4),6/COUNTIF($B$4:$E$4,MAX($B$4:$E$4)),0)","target_range":"B5:E7","explanation":"allocate six points among tied maxima"}', 90, 30),
    ])
    output = tmp_path / "artifact"
    result = execute_smoke(state_path=state_path, output_dir=output, live=True, client=client)
    assert result["status"] == "passed"
    assert result["decision"] == "smoke_passed_batch_still_closed"
    assert result["provider_attempts"] == 2
    assert result["usage"] == {
        "input_tokens": 210,
        "output_tokens": 50,
        "total_tokens": 260,
        "exact_for_successful_calls": True,
    }
    assert len(client.chat.completions.calls) == 2
    assert all(call["extra_body"] == {"enable_thinking": False} for call in client.chat.completions.calls)
    records = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert [record["attempt_count"] for record in records] == [1, 1]
    assert all(record["usage_known"] is True for record in records)


def test_live_refuses_closed_permission(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, paid=False)
    with pytest.raises(PermissionError):
        execute_smoke(state_path=state_path, output_dir=tmp_path / "artifact", live=True, client=FakeClient([]))


def test_live_refuses_to_overwrite_artifact(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    output = tmp_path / "artifact"
    output.mkdir()
    with pytest.raises(SmokeError, match="refusing to overwrite"):
        execute_smoke(state_path=state_path, output_dir=output, live=True, client=FakeClient([]))


def test_missing_usage_stops_before_second_call(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    broken = fake_response("office-bad", '{"answer":"2602","evidence":"table"}', 1, 1)
    broken.usage.total_tokens = None
    client = FakeClient([broken, fake_response("unused", "{}", 1, 1)])
    output = tmp_path / "artifact"
    with pytest.raises(SmokeError, match="stopped after call 1"):
        execute_smoke(state_path=state_path, output_dir=output, live=True, client=client)
    assert len(client.chat.completions.calls) == 1
    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["status"] == "stopped"
    assert manifest["provider_attempts"] == 1
    assert manifest["decision"] == "smoke_stopped_batch_closed"


def test_parse_failure_preserves_known_usage_and_stops(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    invalid = fake_response("office-invalid", "not-json", 11, 4)
    client = FakeClient([invalid, fake_response("unused", "{}", 1, 1)])
    output = tmp_path / "artifact"
    with pytest.raises(SmokeError, match="stopped after call 1"):
        execute_smoke(state_path=state_path, output_dir=output, live=True, client=client)
    assert len(client.chat.completions.calls) == 1
    record = json.loads((output / "results.jsonl").read_text().splitlines()[0])
    assert record["usage_known"] is True
    assert record["total_tokens"] == 15
    assert record["status"] == "failed"
