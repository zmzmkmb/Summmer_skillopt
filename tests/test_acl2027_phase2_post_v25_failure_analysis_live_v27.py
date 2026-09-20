import json

import pytest

from scripts import run_acl2027_phase2_post_v25_failure_analysis_live_v27 as live


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
            raise TimeoutError("mock v27 timeout")
        return {"content": json.dumps({"answer": "mock"}), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-v27-{self.calls}"}


def test_preflight_and_authorization_boundary(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v27-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 1600
    assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-v27-secret")
    assert auth["authorized_stage"] == "post_v25_failure_analysis_followup"
    assert auth["temperature"] == auth["retries"] == 0
    assert auth["max_tokens_present"] is False
    assert auth["stage_cost_ceiling_cny"] == auth["cumulative_cost_ceiling_cny"] == 10.0
    assert auth["formal_scaling_allowed"] is False


def test_preflight_rejects_receipt_binding_drift(tmp_path, monkeypatch):
    receipt = live.load(live.RECEIPT)
    receipt["bindings"]["v26_schedule_sha256"] = "0" * 64
    path = tmp_path / "receipt.json"
    live.write(path, receipt)
    monkeypatch.setattr(live, "RECEIPT", path)
    with pytest.raises(live.HardStop, match="receipt file binding drift"):
        live.preflight()


def test_terminal_error_is_not_resumable(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts" / "v27"
    for name, path in {
        "ARTIFACT": artifact,
        "PREFLIGHT_AUDIT": artifact / "zero_network_preflight.json",
        "REGISTRY": artifact / "authorization_registry.json",
        "AUTH": artifact / "authorization_open.json",
        "AUTH_CLOSED": artifact / "authorization_closed.json",
        "LEDGER": artifact / "ledger.json",
        "PACING": artifact / "request_start_ledger.json",
        "RUN_AUDIT": artifact / "run_audit.json",
        "CLOSURE": artifact / "authorization_closure.json",
    }.items():
        monkeypatch.setattr(live, name, path)
    monkeypatch.setattr(live, "INTERVAL_NS", 0)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v27-secret")
    live.open_authorization()
    with pytest.raises(live.HardStop, match="mock v27 timeout"):
        live.execute(MockProvider(error_at=1))
    assert live.load(live.LEDGER)[0]["terminal"] is True
    with pytest.raises(live.HardStop, match="ledger chain is not resumable"):
        live.execute(MockProvider())
