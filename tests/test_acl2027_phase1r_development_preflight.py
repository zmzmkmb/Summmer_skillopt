from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.run_acl2027_phase1r_development import (
    RunnerError,
    build_request_plan,
    execute_plan,
    validate_response_contract,
)
from scripts.validate_acl2027_phase1r_development_preflight import (
    ScriptedProvider,
    audit,
    valid_payload,
    write_artifact,
)


def test_phase1r_materializes_exact_balanced_plan_without_output_cap() -> None:
    _, plan = build_request_plan()
    assert len(plan) == 192
    assert len({row["logical_call_id"] for row in plan}) == 192
    assert sum(row["branch"] == "candidate" for row in plan) == 96
    assert sum(row["branch"] == "fallback" for row in plan) == 96
    assert all("max_tokens" not in row["request"] for row in plan)


def test_phase1r_zero_network_audit_passes_all_hard_stop_simulations() -> None:
    _, result = audit()
    assert result["decision"] == "development_runner_preflight_passed_paid_execution_closed"
    assert all(result["checks"].values())
    assert result["network_calls"] == 0
    assert result["paid_api_calls"] == 0
    assert result["provider_attempts"] == 0


def test_phase1r_resume_executes_only_missing_suffix(tmp_path) -> None:
    _, plan = build_request_plan()
    provider = ScriptedProvider(plan)
    first = execute_plan(plan, tmp_path / "run", provider, max_new_calls=7)
    second = execute_plan(plan, tmp_path / "run", provider)
    assert first["status"] == "paused"
    assert first["recorded_calls"] == 7
    assert second["status"] == "completed"
    assert provider.calls == 192


def test_phase1r_unknown_usage_is_terminal(tmp_path) -> None:
    _, plan = build_request_plan()
    provider = ScriptedProvider(plan, "unknown_usage", failure_at=1)
    result = execute_plan(plan, tmp_path / "run", provider)
    assert result["status"] == "hard_stopped"
    assert result["recorded_calls"] == 1
    assert provider.calls == 1


def test_phase1r_contract_failure_preserves_known_usage(tmp_path) -> None:
    _, plan = build_request_plan()
    result = execute_plan(
        plan,
        tmp_path / "run",
        ScriptedProvider(plan, "contract", failure_at=1),
    )
    record = json.loads((tmp_path / "run" / "results.jsonl").read_text())
    assert result["status"] == "hard_stopped"
    assert result["usage_known_for_all_attempts"] is True
    assert result["usage"]["total_tokens"] == 15
    assert record["usage_known"] is True
    assert record["total_tokens"] == 15


def test_phase1r_rejects_plan_drift_on_resume(tmp_path) -> None:
    _, plan = build_request_plan()
    execute_plan(plan, tmp_path / "run", ScriptedProvider(plan), max_new_calls=1)
    changed = deepcopy(plan)
    changed[0]["request"]["temperature"] = 0.25
    with pytest.raises(RunnerError, match="plan drift"):
        execute_plan(changed, tmp_path / "run", ScriptedProvider(changed))


def test_phase1r_abstention_requires_reason() -> None:
    payload = valid_payload("OfficeQA", abstain=True)
    payload["reason"] = ""
    with pytest.raises(RunnerError, match="reason"):
        validate_response_contract("OfficeQA", payload)


def test_phase1r_refuses_artifact_overwrite(tmp_path) -> None:
    output = tmp_path / "immutable"
    output.mkdir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_artifact(output)


def test_phase1r_records_are_append_only_jsonl(tmp_path) -> None:
    _, plan = build_request_plan()
    execute_plan(plan, tmp_path / "run", ScriptedProvider(plan), max_new_calls=2)
    lines = (tmp_path / "run" / "results.jsonl").read_text().splitlines()
    records = [json.loads(line) for line in lines]
    assert [row["call_index"] for row in records] == [1, 2]
