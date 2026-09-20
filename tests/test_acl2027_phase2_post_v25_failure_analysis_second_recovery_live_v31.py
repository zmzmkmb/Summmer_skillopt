import json

import pytest

from scripts import run_acl2027_phase2_post_v25_failure_analysis_second_recovery_live_v31 as live


class MockProvider:
    def __init__(self, error_at=None):
        self.calls = 0
        self.error_at = error_at

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert body["enable_thinking"] is False
        assert body["response_format"] == {"type": "json_object"}
        assert "max_tokens" not in body
        if self.calls == self.error_at:
            raise TimeoutError("mock v31 timeout")
        return {"content": json.dumps({"answer": "mock"}), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-v31-{self.calls}"}


def patch_artifact(tmp_path, monkeypatch):
    artifact = tmp_path / "v31"
    for name, path in {"ARTIFACT": artifact, "PREFLIGHT_AUDIT": artifact / "zero_network_preflight.json", "REGISTRY": artifact / "authorization_registry.json", "AUTH": artifact / "authorization_open.json", "AUTH_CLOSED": artifact / "authorization_closed.json", "LEDGER": artifact / "ledger.json", "PACING": artifact / "request_start_ledger.json", "RUN_AUDIT": artifact / "run_audit.json", "CLOSURE": artifact / "authorization_closure.json"}.items():
        monkeypatch.setattr(live, name, path)
    monkeypatch.setattr(live, "INTERVAL_NS", 0)


def test_v31_preflight_binds_exact_v30_plan(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v31-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 220
    assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-v31-secret")
    assert auth["authorized_stage"] == "post_v25_failure_analysis_second_recovery"
    assert auth["stage_cost_ceiling_cny"] == 1.5
    assert auth["cumulative_cost_ceiling_cny"] == 8.0
    assert auth["formal_scaling_allowed"] is False


def test_v31_terminal_error_has_unknown_usage_and_is_not_resumable(tmp_path, monkeypatch):
    patch_artifact(tmp_path, monkeypatch)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v31-secret")
    live.open_authorization()
    with pytest.raises(live.HardStop, match="mock v31 timeout"):
        live.execute(MockProvider(error_at=2))
    records = live.load(live.LEDGER)
    assert records[1]["terminal"] is True
    assert records[1]["request_id"] is None
    assert records[1]["usage"] is None
    assert records[1]["raw_response"] is None
    with pytest.raises(live.HardStop, match="ledger chain is not resumable"):
        live.execute(MockProvider())


def test_v31_receipt_rejects_binding_drift(tmp_path, monkeypatch):
    receipt = live.load(live.RECEIPT)
    receipt["bindings"]["v30_schedule_sha256"] = "0" * 64
    path = tmp_path / "receipt.json"
    live.write(path, receipt)
    monkeypatch.setattr(live, "RECEIPT", path)
    with pytest.raises(live.HardStop, match="receipt binding drift"):
        live.preflight()
