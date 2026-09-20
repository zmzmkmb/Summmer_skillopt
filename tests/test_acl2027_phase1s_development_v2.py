from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.run_acl2027_phase1r_development import HardStop, RunnerError
from scripts.run_acl2027_phase1s_development_v2 import (
    SimulatedProvider,
    execute_plan_v2,
    load_frozen_plan,
    normalize_response_text,
    run_preflight,
    validate_config_data,
)


def test_phase1s_v2_binds_plan_and_terminal_v1() -> None:
    config, plan = load_frozen_plan()
    assert len(plan) == 192
    assert config["terminal_v1_binding"]["resumable"] is False
    assert config["terminal_v1_binding"]["spent_call_reused"] is False
    assert all("max_tokens" not in row["request"] for row in plan)


def test_phase1s_v2_preflight_permissions_are_closed() -> None:
    config, _ = load_frozen_plan()
    assert config["execution"]["paid_api_allowed"] is False
    assert config["execution"]["network_calls_allowed"] is False
    assert config["execution"]["provider_calls_authorized"] == 0
    assert config["authorization_gate"]["new_explicit_authorization_required"]


def test_phase1s_v2_rejects_authorization_drift() -> None:
    config, _ = load_frozen_plan()
    changed = deepcopy(config)
    changed["execution"]["paid_api_allowed"] = True
    with pytest.raises(RunnerError, match="zero-network"):
        validate_config_data(changed)


def test_phase1s_v2_normalization_is_syntactic_only() -> None:
    raw = '\ufeff  ```json\n{"calculation": "1+0"}\n```  '
    assert normalize_response_text(raw) == '{"calculation": "1+0"}'


def test_phase1s_v2_malformed_known_usage_is_invalid_and_continues(tmp_path) -> None:
    _, plan = load_frozen_plan()
    provider = SimulatedProvider(plan, {1: "malformed_json"})
    manifest = execute_plan_v2(
        plan, tmp_path / "run", provider, max_new_calls=2
    )
    records = [
        json.loads(line)
        for line in (tmp_path / "run" / "results.jsonl").read_text().splitlines()
    ]
    assert manifest["status"] == "paused"
    assert manifest["invalid_output_calls"] == 1
    assert records[0]["status"] == "invalid_output"
    assert records[0]["terminal"] is False
    assert records[0]["raw_response_text"] == '{"answer":'
    assert records[1]["status"] == "completed"
    assert provider.calls == 2


def test_phase1s_v2_wrong_type_is_not_coerced(tmp_path) -> None:
    _, plan = load_frozen_plan()
    execute_plan_v2(
        plan,
        tmp_path / "run",
        SimulatedProvider(plan, {1: "wrong_type"}),
        max_new_calls=1,
    )
    record = json.loads(
        (tmp_path / "run" / "results.jsonl").read_text().strip()
    )
    assert record["status"] == "invalid_output"
    assert record["error_stage"] == "response_contract"
    assert '"calculation": "1+0"' in record["normalized_response_text"]


def test_phase1s_v2_unknown_usage_is_terminal_and_not_resumable(tmp_path) -> None:
    _, plan = load_frozen_plan()
    output = tmp_path / "run"
    manifest = execute_plan_v2(
        plan, output, SimulatedProvider(plan, {1: "unknown_usage"})
    )
    assert manifest["status"] == "hard_stopped"
    with pytest.raises(HardStop, match="not resumable"):
        execute_plan_v2(plan, output, SimulatedProvider(plan))


def test_phase1s_v2_resume_consumes_invalid_prefix_once(tmp_path) -> None:
    _, plan = load_frozen_plan()
    provider = SimulatedProvider(plan, {1: "malformed_json"})
    first = execute_plan_v2(
        plan, tmp_path / "run", provider, max_new_calls=3
    )
    second = execute_plan_v2(
        plan, tmp_path / "run", provider, max_new_calls=2
    )
    assert first["recorded_calls"] == 3
    assert second["recorded_calls"] == 5
    assert second["invalid_output_calls"] == 1
    assert provider.calls == 5


def test_phase1s_v2_detects_request_plan_drift(tmp_path) -> None:
    _, plan = load_frozen_plan()
    execute_plan_v2(
        plan, tmp_path / "run", SimulatedProvider(plan), max_new_calls=1
    )
    changed = deepcopy(plan)
    changed[0]["request"]["temperature"] = 0.25
    with pytest.raises(RunnerError, match="plan drift"):
        execute_plan_v2(changed, tmp_path / "run", SimulatedProvider(changed))


def test_phase1s_v2_full_zero_network_preflight(tmp_path) -> None:
    audit = run_preflight(tmp_path / "preflight")
    assert all(audit["checks"].values())
    assert audit["network_calls"] == 0
    assert audit["paid_api_calls"] == 0
    assert audit["provider_attempts"] == 0
    assert audit["terminal_v1_spent_call_reused"] is False
