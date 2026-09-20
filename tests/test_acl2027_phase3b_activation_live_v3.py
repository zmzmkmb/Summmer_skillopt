import json
import pytest
from scripts import analyze_acl2027_phase3b_activation_live_v3 as analysis
from scripts import run_acl2027_phase3b_activation_live_v3 as live


class MockProvider:
    def __init__(self, error_at=None): self.calls, self.error_at = 0, error_at
    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus" and body["temperature"] == 0 and body["enable_thinking"] is False and body["response_format"] == {"type": "json_object"} and "max_tokens" not in body
        if self.calls == self.error_at: raise TimeoutError("mock Phase 3B timeout")
        selected = body["available_skill_ids"][-1]
        return {"content": json.dumps({"declared_skill_applicability": selected != "none", "selected_skill_id": selected, "intermediate_operation": "retrieve", "final_answer": "mock"}), "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}, "request_id": f"mock-phase3b-v3-{self.calls}"}


def patch_artifact(tmp_path, monkeypatch):
    artifact = tmp_path / "phase3b-v3"
    for name,path in {"ARTIFACT": artifact, "PREFLIGHT_AUDIT": artifact/"zero_network_preflight.json", "REGISTRY": artifact/"authorization_registry.json", "AUTH": artifact/"authorization_open.json", "AUTH_CLOSED": artifact/"authorization_closed.json", "LEDGER": artifact/"ledger.json", "PACING": artifact/"request_start_ledger.json", "RUN_AUDIT": artifact/"run_audit.json", "CLOSURE": artifact/"authorization_closure.json"}.items(): monkeypatch.setattr(live, name, path)
    monkeypatch.setattr(live, "INTERVAL_NS", 0)


def test_phase3b_v3_preflight_binds_exact_plan_and_egress(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-phase3b-secret"); gate = live.preflight(); assert gate["authorized_calls"] == gate["max_provider_attempts"] == 300; assert gate["network_calls"] == gate["provider_calls"] == gate["model_calls"] == gate["paid_api_calls"] == 0
    assert gate["data_egress_authorized"] is True and gate["authorized_destination"] == live.ENDPOINT and gate["authorized_payload_classes"] == live.PAYLOAD_CLASSES
    auth = live.authorization_template("mock-phase3b-secret"); assert auth["authorized_stage"] == "activation_pilot" and auth["stage_cost_ceiling_cny"] == 3.0 and auth["cumulative_cost_ceiling_cny"] == 11.0 and auth["formal_scaling_allowed"] is False and auth["paid_usage_authorized"] is True


def test_phase3b_v3_terminal_error_is_not_resumable(tmp_path, monkeypatch):
    patch_artifact(tmp_path, monkeypatch); monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-phase3b-secret"); live.open_authorization()
    with pytest.raises(live.HardStop, match="mock Phase 3B timeout"): live.execute(MockProvider(error_at=2))
    records = live.load(live.LEDGER); assert records[1]["terminal"] is True and records[1]["usage"] is None
    with pytest.raises(live.HardStop, match="ledger chain is not resumable"): live.execute(MockProvider())


def test_phase3b_v3_receipt_rejects_egress_drift(tmp_path, monkeypatch):
    receipt = live.load(live.RECEIPT); receipt["authorized_destination"] = "https://example.invalid"; path = tmp_path/"receipt.json"; live.write(path, receipt); monkeypatch.setattr(live, "RECEIPT", path)
    with pytest.raises(live.HardStop, match="data-egress authorization drift"): live.preflight()


def test_activation_parser_enforces_exact_contract():
    valid = json.dumps({"declared_skill_applicability": True, "selected_skill_id": "skill", "intermediate_operation": "compare", "final_answer": "yes"}); assert analysis.parse_activation(valid, ["none", "skill"])["selected_skill_id"] == "skill"
    with pytest.raises(ValueError): analysis.parse_activation(json.dumps({"final_answer": "yes"}), ["none"])
