from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.prepare_acl2027_phase1v_calibration import HardStop, PreflightError, stable_hash
from scripts.prepare_acl2027_phase1w_calibration_live import (
    SimulatedProvider,
    cost_cny,
    execute_simulation,
    load_frozen_plan,
    run_preflight,
    simulation_authorization,
)


def test_plan_binds_exact_scientific_and_transport_requests() -> None:
    config, plan, private = load_frozen_plan()
    assert len(plan) == len(private) == 24
    assert [row["task_family"] for row in plan] == ["SearchQA"] * 12 + ["2WikiMultiHopQA"] * 12
    assert [[row["logical_call_id"], row["scientific_request_hash"]] for row in plan] == config["phase1v_binding"]["ordered_requests"]
    assert all(set(row["request"]) == {"temperature", "messages", "model", "enable_thinking"} for row in plan)
    assert all(row["transport_request_hash"] == stable_hash(row["request"]) for row in plan)
    assert len({row["transport_request_hash"] for row in plan}) == 24


def test_transport_and_authorization_are_closed() -> None:
    config, plan, _ = load_frozen_plan()
    execution = config["execution"]
    assert execution["model_id"] == "qwen3.7-plus"
    assert execution["endpoint_class"] == "token_plan_user_confirmed"
    assert execution["request_interval_seconds"] == 1.0
    assert execution["sdk_max_retries"] == execution["explicit_retries"] == 0
    assert all("max_tokens" not in row["request"] for row in plan)
    assert config["authorization_gate"]["authorized_calls"] == 0
    assert config["authorization_gate"]["authorization_may_not_be_inherited_from_phase1s"] is True


def test_cost_arithmetic_and_ceiling_semantics() -> None:
    config, _, _ = load_frozen_plan()
    cost = config["cost_control"]
    assert cost["conservative_input_tokens"] == 51505
    assert cost["conservative_total_output_tokens"] == 98304
    assert cost["conservative_estimated_cost_cny"] == pytest.approx(0.889442)
    assert cost_cny(config, {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}) == pytest.approx(10.0)
    assert cost["accounting_ceiling_cny"] == 10.0
    assert cost["accounting_ceiling_is_request_parameter"] is False
    assert cost["max_tokens_is_cost_control"] is False


def test_known_usage_invalid_continues_and_preserves_raw(tmp_path) -> None:
    config, plan, private = load_frozen_plan()
    provider = SimulatedProvider(plan, private, {1: "malformed", 2: "schema_invalid"})
    result = execute_simulation(config, plan, private, tmp_path, provider, simulation_authorization(config, plan), max_new_calls=3)
    assert result["recorded_calls"] == 3
    assert result["invalid_output_calls"] == 2
    record = __import__("json").loads((tmp_path / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["raw_response_text"] == '{"answer":'


def test_unknown_usage_terminal_and_resume_exact_prefix(tmp_path) -> None:
    config, plan, private = load_frozen_plan()
    auth = simulation_authorization(config, plan)
    terminal = tmp_path / "terminal"
    result = execute_simulation(config, plan, private, terminal, SimulatedProvider(plan, private, {1: "unknown_usage"}), auth)
    assert result["status"] == "hard_stopped"
    with pytest.raises(HardStop, match="not resumable"):
        execute_simulation(config, plan, private, terminal, SimulatedProvider(plan, private), auth)
    resume = tmp_path / "resume"
    provider = SimulatedProvider(plan, private)
    assert execute_simulation(config, plan, private, resume, provider, auth, max_new_calls=2)["recorded_calls"] == 2
    assert execute_simulation(config, plan, private, resume, provider, auth, max_new_calls=3)["recorded_calls"] == 5
    assert provider.calls == 5


def test_plan_authorization_and_ceiling_drift_stop(tmp_path) -> None:
    config, plan, private = load_frozen_plan()
    auth = simulation_authorization(config, plan)
    bad = deepcopy(auth)
    bad["authorized_calls"] = 25
    with pytest.raises(PreflightError, match="authorization drift"):
        execute_simulation(config, plan, private, tmp_path / "auth", SimulatedProvider(plan, private), bad)
    execute_simulation(config, plan, private, tmp_path / "resume", SimulatedProvider(plan, private), auth, max_new_calls=1)
    changed = deepcopy(plan)
    changed[0]["request"]["temperature"] = 1
    changed[0]["transport_request_hash"] = stable_hash(changed[0]["request"])
    with pytest.raises(PreflightError, match="plan drift"):
        execute_simulation(config, changed, private, tmp_path / "resume", SimulatedProvider(changed, private), simulation_authorization(config, changed), max_new_calls=1)
    ceiling = tmp_path / "ceiling"
    execute_simulation(config, plan, private, ceiling, SimulatedProvider(plan, private, usage={"input_tokens": 0, "output_tokens": 1_250_000, "total_tokens": 1_250_000}), auth, max_new_calls=1)
    with pytest.raises(HardStop, match="accounting ceiling"):
        execute_simulation(config, plan, private, ceiling, SimulatedProvider(plan, private), auth, max_new_calls=1)


def test_full_preflight_is_zero_call_and_refuses_overwrite(tmp_path) -> None:
    output = tmp_path / "artifact"
    audit = run_preflight(output)
    assert all(audit["checks"].values())
    assert audit["network_calls"] == audit["provider_calls"] == audit["paid_api_calls"] == 0
    assert audit["request_count"] == 24
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_preflight(output)
