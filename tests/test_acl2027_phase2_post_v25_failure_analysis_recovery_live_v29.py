import json

import pytest

from scripts import run_acl2027_phase2_post_v25_failure_analysis_recovery_live_v29 as live


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
            raise TimeoutError("mock v29 timeout")
        return {"content": json.dumps({"answer": "mock"}), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-v29-{self.calls}"}


def patch_artifact(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts" / "v29"
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


def test_v29_preflight_binds_closed_v28_and_exact_recovery_boundary(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v29-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 528
    assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-v29-secret")
    assert auth["authorized_stage"] == "post_v25_failure_analysis_recovery"
    assert auth["stage_cost_ceiling_cny"] == 3.0
    assert auth["cumulative_cost_ceiling_cny"] == 8.0
    assert auth["formal_scaling_allowed"] is False


def test_v29_terminal_error_never_copies_previous_response(tmp_path, monkeypatch):
    patch_artifact(tmp_path, monkeypatch)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-v29-secret")
    live.open_authorization()
    with pytest.raises(live.HardStop, match="mock v29 timeout"):
        live.execute(MockProvider(error_at=2))
    records = live.load(live.LEDGER)
    assert records[0]["status"] == "completed"
    assert records[1]["terminal"] is True
    assert records[1]["request_id"] is None
    assert records[1]["usage"] is None
    assert records[1]["raw_response"] is None
    with pytest.raises(live.HardStop, match="ledger chain is not resumable"):
        live.execute(MockProvider())


def test_v29_receipt_rejects_binding_drift(tmp_path, monkeypatch):
    receipt = live.load(live.RECEIPT)
    receipt["bindings"]["v28_schedule_sha256"] = "0" * 64
    path = tmp_path / "receipt.json"
    live.write(path, receipt)
    monkeypatch.setattr(live, "RECEIPT", path)
    with pytest.raises(live.HardStop, match="receipt binding drift"):
        live.preflight()
