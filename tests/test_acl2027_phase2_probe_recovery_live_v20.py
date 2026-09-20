from __future__ import annotations

import json

import pytest

from scripts import run_acl2027_phase2_probe_recovery_live_v20 as live


class MockProvider:
    def __init__(self, error_at: int | None = None, response_usage: dict[str, int] | None = None):
        self.calls = 0
        self.error_at = error_at
        self.response_usage = response_usage or {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
        self.gold = {row["task_id"]: row for row in live.load(live.RECOVERY_GOLD)}

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert body["enable_thinking"] is False
        assert body["response_format"] == {"type": "json_object"}
        assert "max_tokens" not in body
        if self.error_at == self.calls:
            raise TimeoutError("mock provider timeout")
        private = self.gold[body["task_id"]]
        answer = (private.get("answers") or [private.get("answer")])[0]
        return {"content": json.dumps({"answer": answer}), "usage": self.response_usage, "request_id": f"mock-{self.calls}"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts" / "v20"
    paths = {
        "AUTH": tmp_path / "configs" / "authorization.json",
        "AUTH_CLOSED": tmp_path / "configs" / "authorization_closed.json",
        "ARTIFACT": artifact,
        "PREFLIGHT_AUDIT": artifact / "zero_network_preflight.json",
        "REGISTRY": artifact / "authorization_registry.json",
        "LEDGER": artifact / "ledger.json",
        "PACING": artifact / "request_start_ledger.json",
        "PROBE_AUDIT": artifact / "probe_audit.json",
        "RUN_AUDIT": artifact / "run_audit.json",
        "CLOSURE": artifact / "authorization_closure.json",
    }
    for name, path in paths.items():
        monkeypatch.setattr(live, name, path)
        monkeypatch.setattr(live.engine, name, path)
    monkeypatch.setattr(live.engine, "INTERVAL_NS", 0)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v20-secret")
    live.engine.open_authorization()
    return artifact


def test_v20_zero_network_preflight_and_boundary(monkeypatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v20-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 112
    assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-v20-secret")
    assert auth["authorized_stage"] == "probe"
    assert auth["authorized_calls"] == auth["max_provider_attempts"] == 112
    assert auth["stage_cost_ceiling_cny"] == auth["cumulative_cost_ceiling_cny"] == 7.5
    assert auth["temperature"] == auth["retries"] == 0
    assert auth["max_tokens_present"] is False
    assert auth["user_authorization"]["held_out_authorized"] is False
    assert auth["user_authorization"]["later_stages_authorized"] is False
    assert auth["user_authorization"]["formal_scaling_authorized"] is False


def test_v20_full_mock_probe_audit_and_closure(isolated) -> None:
    provider = MockProvider()
    records = live.engine.execute(provider)
    result = live.audit()
    assert len(records) == provider.calls == 112
    assert result["provider_attempts"] == result["unique_logical_requests"] == result["unique_request_hashes"] == 112
    assert result["input_tokens"] == 1120
    assert result["output_tokens"] == 224
    assert result["total_tokens"] == 1344
    assert result["exact_local_cost_cny"] == 0.004032
    assert result["duplicates"] == result["retries"] == 0
    assert result["max_tokens_present"] is False
    assert result["combined_probe_rows"] == 160
    assert set(result["condition_accuracy"]) == set(live.engine.load(live.SCHEDULE)["schedule"][index]["condition"] for index in range(4))
    closure = live.close("completed_exact_112")
    assert closure["status"] == "closed"
    assert live.load(live.RUN_AUDIT)["authorization_closed"] is True


def test_v20_exact_prefix_resume_has_no_duplicates(isolated) -> None:
    provider = MockProvider()
    with pytest.raises(KeyboardInterrupt):
        live.engine.execute(provider, interrupt_after=17)
    assert len(live.load(live.LEDGER)) == len(live.load(live.PACING)) == 17
    records = live.engine.execute(provider)
    assert len(records) == provider.calls == 112
    assert len({record["logical_call_id"] for record in records}) == 112


def test_v20_terminal_error_is_not_resumable(isolated) -> None:
    with pytest.raises(live.HardStop, match="mock provider timeout"):
        live.engine.execute(MockProvider(error_at=1))
    assert live.load(live.LEDGER)[0]["terminal"] is True
    with pytest.raises(live.HardStop, match="terminal ledger"):
        live.engine.execute(MockProvider())


def test_v20_ambiguous_start_refuses_provider(isolated) -> None:
    live.write(live.PACING, [{"sequence": 1}])
    provider = MockProvider()
    with pytest.raises(live.HardStop, match="ambiguous request start"):
        live.engine.execute(provider)
    assert provider.calls == 0


def test_v20_cost_ceiling_stops_without_retry(isolated) -> None:
    provider = MockProvider(response_usage={"input_tokens": 4_000_000, "output_tokens": 0, "total_tokens": 4_000_000})
    with pytest.raises(live.HardStop, match="cost ceiling"):
        live.engine.execute(provider)
    assert provider.calls == 1
    assert live.load(live.LEDGER)[0]["terminal"] is True


def test_v20_audit_rejects_cost_tampering(isolated) -> None:
    provider = MockProvider()
    with pytest.raises(KeyboardInterrupt):
        live.engine.execute(provider, interrupt_after=3)
    records = live.load(live.LEDGER)
    records[1]["cumulative_local_cost_cny"] = 999.0
    live.engine.seal(records[1])
    live.write(live.LEDGER, records)
    with pytest.raises(live.HardStop, match="cumulative cost drift"):
        live.audit()
