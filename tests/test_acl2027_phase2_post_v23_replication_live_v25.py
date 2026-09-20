import json

import pytest

from scripts import run_acl2027_phase2_post_v23_replication_live_v25 as live


class MockProvider:
    def __init__(self, error_at=None):
        self.calls = 0
        self.error_at = error_at

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        assert body["enable_thinking"] is False
        assert "max_tokens" not in body
        if self.calls == self.error_at:
            raise TimeoutError("mock v25 timeout")
        return {"content": json.dumps({"answer": "mock"}), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-v25-{self.calls}"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts" / "v25"
    for name, path in {
        "ARTIFACT": artifact,
        "PREFLIGHT_AUDIT": artifact / "zero_network_preflight.json",
        "REGISTRY": artifact / "authorization_registry.json",
        "AUTH": tmp_path / "configs" / "authorization.json",
        "AUTH_CLOSED": tmp_path / "configs" / "authorization_closed.json",
        "LEDGER": artifact / "ledger.json",
        "PACING": artifact / "request_start_ledger.json",
        "RUN_AUDIT": artifact / "run_audit.json",
        "CLOSURE": artifact / "authorization_closure.json",
    }.items():
        monkeypatch.setattr(live, name, path)
    monkeypatch.setattr(live, "INTERVAL_NS", 0)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v25-secret")
    live.open_authorization()
    return artifact


def test_preflight_and_boundary(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v25-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 320
    assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-v25-secret")
    assert auth["authorized_stage"] == "post_v23_replication"
    assert auth["temperature"] == auth["retries"] == 0
    assert auth["max_tokens_present"] is False
    assert auth["stage_cost_ceiling_cny"] == auth["cumulative_cost_ceiling_cny"] == 3.5
    assert auth["formal_scaling_allowed"] is False


def test_full_mock_execution_and_closure(isolated):
    provider = MockProvider()
    records = live.execute(provider)
    result = live.audit()
    assert len(records) == provider.calls == 320
    assert result["provider_attempts"] == result["unique_logical_requests"] == result["unique_request_hashes"] == 320
    assert result["input_tokens"] == 3200
    assert result["output_tokens"] == 640
    assert result["total_tokens"] == 3840
    assert result["duplicates"] == result["retries"] == 0
    closure = live.close("completed_exact_320")
    assert closure["status"] == "closed"
    assert closure["post_v23_replication_calls"] == 320


def test_terminal_error_is_not_resumable(isolated):
    with pytest.raises(live.HardStop, match="mock v25 timeout"):
        live.execute(MockProvider(error_at=1))
    assert live.load(live.LEDGER)[0]["terminal"] is True
    with pytest.raises(live.HardStop, match="ledger chain is not resumable"):
        live.execute(MockProvider())
