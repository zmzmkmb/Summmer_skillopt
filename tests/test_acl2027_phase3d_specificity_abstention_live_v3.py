import json

import pytest

from scripts import run_acl2027_phase3d_specificity_abstention_live_v3 as live


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
            raise TimeoutError("mock Phase 3D v3 timeout")
        ids = body["available_skill_ids"][1:]
        content = {"skill_assessments": [{"skill_id": value, "applicable": False} for value in ids], "selected_skill_id": "none", "intermediate_operation": "mock", "final_answer": "mock"}
        return {"content": json.dumps(content), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-phase3d-v3-{self.calls}"}


def patch_artifact(tmp_path, monkeypatch):
    artifact = tmp_path / "phase3d-v3"
    for name, path in {"ARTIFACT": artifact, "PREFLIGHT_AUDIT": artifact / "zero_network_preflight.json", "REGISTRY": artifact / "authorization_registry.json", "AUTH": artifact / "authorization_open.json", "AUTH_CLOSED": artifact / "authorization_closed.json", "LEDGER": artifact / "ledger.json", "PACING": artifact / "request_start_ledger.json", "RUN_AUDIT": artifact / "run_audit.json", "CLOSURE": artifact / "authorization_closure.json"}.items():
        monkeypatch.setattr(live, name, path)
    monkeypatch.setattr(live, "INTERVAL_NS", 0)


def test_phase3d_v3_preflight_binds_authorized_route_and_payloads(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-phase3d-v3-secret")
    gate = live.preflight()
    assert gate["authorized_calls"] == gate["max_provider_attempts"] == 240
    assert gate["phase3d_design_fingerprint"] == live.DESIGN_FINGERPRINT
    assert gate["phase3d_live_preflight_fingerprint"] == live.PREFLIGHT_FINGERPRINT
    assert gate["data_egress_authorized"] is True
    assert gate["authorized_destination"] == live.ENDPOINT
    assert gate["authorized_payload_classes"] == live.PAYLOAD_CLASSES
    assert gate["network_calls"] == gate["provider_calls"] == gate["paid_api_calls"] == 0
    auth = live.authorization_template("mock-phase3d-v3-secret")
    assert auth["stage_cost_ceiling_cny"] == 3.0
    assert auth["cumulative_cost_ceiling_cny"] == 15.0
    assert auth["cross_domain_scaling_authorized"] is False


def test_phase3d_v3_terminal_error_is_not_resumable(tmp_path, monkeypatch):
    patch_artifact(tmp_path, monkeypatch)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-phase3d-v3-secret")
    live.open_authorization()
    with pytest.raises(live.HardStop, match="mock Phase 3D v3 timeout"):
        live.execute(MockProvider(error_at=2))
    records = live.load(live.LEDGER)
    assert records[1]["terminal"] is True and records[1]["usage"] is None
    with pytest.raises(live.HardStop, match="ledger chain is not resumable"):
        live.execute(MockProvider())


def test_phase3d_v3_receipt_rejects_binding_drift(tmp_path, monkeypatch):
    receipt = live.load(live.RECEIPT)
    receipt["bindings"]["v1_schedule_sha256"] = "0" * 64
    path = tmp_path / "receipt.json"
    live.write(path, receipt)
    monkeypatch.setattr(live, "RECEIPT", path)
    with pytest.raises(live.HardStop, match="receipt binding drift"):
        live.preflight()
