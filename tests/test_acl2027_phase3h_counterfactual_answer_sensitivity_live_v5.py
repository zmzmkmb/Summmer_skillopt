import json

from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_live_v5 as phase


def test_phase3h_v5_preflight_is_bound_and_zero_network():
    rows = phase.preflight()
    assert len(rows) == phase.CALLS == 200
    assert phase.receipt()["phase3h_live_preflight_fingerprint"] == phase.PREFLIGHT_FINGERPRINT
    assert phase.receipt()["authorized_payload_classes"] == phase.PAYLOAD_CLASSES


def test_phase3h_v5_mock_execution_closes_exact_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "phase3h-test-key")
    monkeypatch.setattr(phase, "RECEIPT", tmp_path / "receipt.json")
    monkeypatch.setattr(phase, "ARTIFACT", tmp_path)
    for name in ("AUTH", "REGISTRY", "STARTS", "LEDGER", "AUDIT", "CLOSURE"):
        monkeypatch.setattr(phase, name, tmp_path / getattr(phase, name).name)
    monkeypatch.setattr(phase, "INTERVAL_NS", 0)
    phase.authorize(); seen = {"count": 0}

    def provider(_body):
        seen["count"] += 1
        return {"content": json.dumps({"skill_assessments": {}, "selected_skill_id": "none", "intermediate_operation": "mock", "final_answer": "mock"}), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-{seen['count']}"}

    records = phase.execute(provider); closure = phase.close("completed_exact_200")
    audit = phase.load(phase.AUDIT)
    assert len(records) == seen["count"] == 200
    assert audit["completed_calls"] == audit["provider_attempts"] == 200
    assert audit["retries"] == audit["terminal_rows"] == 0
    assert closure["status"] == "closed"
