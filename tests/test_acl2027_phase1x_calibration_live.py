from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.prepare_acl2027_phase1v_calibration import HardStop, PreflightError
from scripts.run_acl2027_phase1x_calibration_live import (
    assert_repository_authorized,
    cost_cny,
    execute_live,
    validate_live_config,
)


class FakeProvider:
    def __init__(self, plan, private, modes=None):
        self.plan, self.private, self.modes, self.calls = plan, private, modes or {}, 0

    def __call__(self, request):
        item = self.plan[self.calls]
        self.calls += 1
        mode = self.modes.get(self.calls, "valid")
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        if mode == "unknown_usage":
            return {"content": "{}", "usage": None}
        if mode == "exception":
            raise RuntimeError("provider failed")
        if mode == "invalid":
            return {"content": '{"answer":', "usage": usage}
        gold = self.private[item["logical_call_id"]]
        payload = {"answer": gold["answers"][0]}
        if item["task_family"] == "2WikiMultiHopQA":
            payload["supporting_evidence"] = gold["supporting_evidence"]
        return {"content": json.dumps(payload), "usage": usage}


def test_authorized_config_binds_exact_plan_and_cny_100() -> None:
    config, plan, private = validate_live_config()
    assert len(plan) == len(private) == 24
    assert config["authorization_gate"]["authorized_calls"] == 24
    assert config["authorization_gate"]["authorized_accounting_ceiling_cny"] == 100.0
    assert config["authorization_gate"]["inherited_from_phase1s"] is False
    assert all("max_tokens" not in row["request"] for row in plan)


def test_zero_retries_route_and_local_accounting() -> None:
    config, _, _ = validate_live_config()
    execution = config["execution"]
    assert execution["sdk_max_retries"] == execution["explicit_retries"] == 0
    assert execution["request_interval_seconds"] == 1.0
    assert execution["endpoint_class"] == "token_plan_user_confirmed"
    assert cost_cny(config, {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}) == pytest.approx(10.0)
    assert config["cost_control"]["accounting_ceiling_is_request_parameter"] is False


def test_repository_permission_is_closed_before_state_transition(monkeypatch) -> None:
    config, _, _ = validate_live_config()
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-" + "x" * 80)
    with pytest.raises(PermissionError, match="permission is closed"):
        assert_repository_authorized(config)


def test_known_usage_invalid_continues_and_scores(tmp_path) -> None:
    config, plan, private = validate_live_config()
    provider = FakeProvider(plan, private, {1: "invalid"})
    manifest = execute_live(config, plan, private, tmp_path, provider, max_new_calls=3)
    assert manifest["recorded_calls"] == 3
    assert manifest["families"]["SearchQA"]["invalid_output"] == 1
    assert provider.calls == 3


def test_terminal_failure_refuses_resume(tmp_path) -> None:
    config, plan, private = validate_live_config()
    output = tmp_path / "run"
    manifest = execute_live(config, plan, private, output, FakeProvider(plan, private, {1: "unknown_usage"}))
    assert manifest["status"] == "hard_stopped"
    with pytest.raises(HardStop, match="not resumable"):
        execute_live(config, plan, private, output, FakeProvider(plan, private))


def test_exact_prefix_and_plan_drift(tmp_path) -> None:
    config, plan, private = validate_live_config()
    output = tmp_path / "run"
    provider = FakeProvider(plan, private)
    execute_live(config, plan, private, output, provider, max_new_calls=2)
    execute_live(config, plan, private, output, provider, max_new_calls=2)
    assert provider.calls == 4
    changed = deepcopy(plan)
    changed[0]["task_id"] = "drift"
    with pytest.raises(PreflightError, match="plan drift"):
        execute_live(config, changed, private, output, FakeProvider(changed, private), max_new_calls=1)
