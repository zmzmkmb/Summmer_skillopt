import json

import pytest

from scripts import run_acl2027_phase2_heldout_recovery_live_v23 as live


class MockProvider:
    def __init__(self, error_at=None, usage=None):
        self.calls = 0
        self.error_at = error_at
        self.response_usage = usage or {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        assert body["enable_thinking"] is False
        assert "max_tokens" not in body
        if self.error_at == self.calls:
            raise TimeoutError("mock v23 timeout")
        return {"content": json.dumps({"answer": "mock"}), "usage": self.response_usage, "request_id": f"mock-v23-{self.calls}"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts" / "v23"
    paths = {"AUTH": tmp_path / "configs" / "authorization.json", "AUTH_CLOSED": tmp_path / "configs" / "authorization_closed.json", "ARTIFACT": artifact, "PREFLIGHT_AUDIT": artifact / "zero_network_preflight.json", "REGISTRY": artifact / "authorization_registry.json", "LEDGER": artifact / "ledger.json", "PACING": artifact / "request_start_ledger.json", "RUN_AUDIT": artifact / "run_audit.json", "CLOSURE": artifact / "authorization_closure.json"}
    for name, path in paths.items():
        monkeypatch.setattr(live, name, path); monkeypatch.setattr(live.engine, name, path)
    monkeypatch.setattr(live, "INTERVAL_NS", 0); monkeypatch.setattr(live.engine, "INTERVAL_NS", 0)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v23-secret")
    live.engine.open_authorization()
    return artifact


def test_v23_preflight_and_authorization_boundary(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v23-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 88
    assert gate["stage_cost_ceiling_cny"] == 1.0
    assert gate["cumulative_cost_ceiling_cny"] == 2.0
    assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-v23-secret")
    assert auth["authorized_stage"] == "held_out_recovery"
    assert auth["temperature"] == auth["retries"] == 0
    assert auth["max_tokens_present"] is False
    assert auth["user_authorization"]["held_out_recovery_authorized"] is True
    assert auth["user_authorization"]["later_stages_authorized"] is False


def test_v23_full_mock_execution_and_closure(isolated):
    provider = MockProvider()
    records = live.execute(provider)
    result = live.audit()
    assert len(records) == provider.calls == 88
    assert result["provider_attempts"] == result["unique_logical_requests"] == result["unique_request_hashes"] == 88
    assert result["input_tokens"] == 880
    assert result["output_tokens"] == 176
    assert result["total_tokens"] == 1056
    assert result["duplicates"] == result["retries"] == 0
    assert result["max_tokens_present"] is False
    assert result["probe_calls"] == result["formal_history_calls"] == 0
    closure = live.close("completed_exact_88")
    assert closure["status"] == "closed"
    assert closure["held_out_recovery_calls"] == 88


def test_v23_terminal_error_is_not_resumable(isolated):
    with pytest.raises(live.HardStop, match="mock v23 timeout"):
        live.execute(MockProvider(error_at=1))
    assert live.load(live.LEDGER)[0]["terminal"] is True
    with pytest.raises(live.HardStop, match="terminal ledger"):
        live.execute(MockProvider())


def test_v23_ambiguous_start_refuses_provider(isolated):
    live.write(live.PACING, [{"sequence": 1}])
    provider = MockProvider()
    with pytest.raises(live.HardStop, match="ambiguous request start"):
        live.execute(provider)
    assert provider.calls == 0
