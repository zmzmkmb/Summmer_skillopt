from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.run_acl2027_phase1r_development import RunnerError
from scripts.run_acl2027_phase1s_development import (
    assert_live_authorized,
    load_frozen_plan,
    validate_config_data,
)


def test_phase1s_binds_exact_phase1r_plan_without_output_cap() -> None:
    config, plan = load_frozen_plan()
    assert len(plan) == 192
    assert sum(row["branch"] == "candidate" for row in plan) == 96
    assert sum(row["branch"] == "fallback" for row in plan) == 96
    assert len({row["request_hash"] for row in plan}) == 52
    assert all("max_tokens" not in row["request"] for row in plan)
    assert config["immutable_request_plan"]["stable_sha256"] == (
        "9eeb21f0a40460deb4db4d480dce3f8bc5f329a2ea3ba98b6d730f3f1391cd41"
    )


def test_phase1s_uses_exact_user_confirmed_token_plan_route() -> None:
    config, _ = load_frozen_plan()
    assert config["execution"]["endpoint"] == (
        "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    )
    changed = deepcopy(config)
    changed["execution"]["endpoint"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    with pytest.raises(RunnerError, match="user-confirmed Token Plan"):
        validate_config_data(changed)


def test_phase1s_rejects_output_cap_drift() -> None:
    config, _ = load_frozen_plan()
    changed = deepcopy(config)
    changed["execution"]["request_body_forbidden_keys"] = []
    with pytest.raises(RunnerError, match="max_tokens"):
        validate_config_data(changed)


def test_phase1s_accounting_ceiling_is_not_a_request_parameter() -> None:
    config, plan = load_frozen_plan()
    cost = config["cost_control"]
    assert cost["accounting_ceiling"] == 200.0
    assert cost["accounting_ceiling_is_request_parameter"] is False
    assert cost["max_tokens_is_cost_control"] is False
    assert all("max_tokens" not in row["request"] for row in plan)


def test_phase1s_cost_estimate_is_below_conservative_envelope() -> None:
    config, _ = load_frozen_plan()
    cost = config["cost_control"]
    expected = (
        cost["calibrated_input_tokens"]
        * cost["list_price_cny_per_million_input_tokens"]
        + cost["phase1q_output_envelope_tokens"]
        * cost["list_price_cny_per_million_output_tokens"]
    ) / 1_000_000
    assert cost["list_price_estimate_cny"] == pytest.approx(expected)
    assert cost["conservative_list_price_estimate_cny"] < 8.0
    assert cost["conservative_list_price_estimate_cny"] < cost["accounting_ceiling"]


def test_phase1s_live_execution_is_closed_after_terminal_attempt(monkeypatch) -> None:
    config, _ = load_frozen_plan()
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-" + "x" * 110)
    with pytest.raises(PermissionError, match="closed"):
        assert_live_authorized(config)


def test_phase1s_rejects_authorization_count_drift(monkeypatch) -> None:
    config, _ = load_frozen_plan()
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-" + "x" * 110)
    changed = deepcopy(config)
    changed["execution"]["provider_calls_authorized"] = 191
    with pytest.raises(PermissionError, match="closed"):
        assert_live_authorized(changed)


def test_phase1s_keeps_max_and_scaling_closed() -> None:
    config, _ = load_frozen_plan()
    authorization = config["authorization_gate"]
    assert authorization["qwen3.8_max_allowed"] is False
    assert authorization["legacy_24_40_batch_allowed"] is False
    assert authorization["staged_384_calls_allowed"] is False
    assert authorization["full_960_calls_allowed"] is False
