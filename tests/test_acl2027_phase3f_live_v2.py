import json

from scripts import run_acl2027_phase3f_live_v2 as phase
from scripts import analyze_acl2027_phase3f_live_v2 as strict_analysis
from scripts import analyze_acl2027_phase3f_mapping_diagnostic_v1 as diagnostic


def test_phase3f_preflight_binds_native_mapping_and_stays_closed():
    result = phase.preflight()
    assert result["status"] == "zero-network-preflight-passed"
    assert result["authorized_calls"] == 240
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["authorization_opened"] is False
    rows = phase.load(phase.SCHEDULE)["schedule"]
    assert all(row["canonical_request_body"]["response_contract"]["skill_assessments"]["type"] == "object" for row in rows)


def test_phase3f_mock_execution_builds_exact_closed_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "phase3f-test-key")
    monkeypatch.setattr(phase, "ARTIFACT", tmp_path)
    for name in ("PREFLIGHT_AUDIT", "REGISTRY", "AUTH", "AUTH_CLOSED", "LEDGER", "PACING", "RUN_AUDIT", "CLOSURE"):
        monkeypatch.setattr(phase, name, tmp_path / getattr(phase, name).name)
    monkeypatch.setattr(phase, "INTERVAL_NS", 0)
    phase.open_authorization()
    counter = {"value": 0}

    def provider(_body):
        counter["value"] += 1
        return {
            "content": json.dumps({"skill_assessments": {}, "selected_skill_id": "none", "intermediate_operation": "mock", "final_answer": "mock"}),
            "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            "request_id": f"mock-{counter['value']}",
            "raw_provider_response": {"id": f"mock-{counter['value']}"},
        }

    records = phase.execute(provider)
    closure = phase.close("completed_exact_240")
    audit = phase.load(phase.RUN_AUDIT)
    assert len(records) == counter["value"] == 240
    assert audit["completed_calls"] == audit["provider_attempts"] == 240
    assert audit["duplicates"] == audit["retries"] == 0
    assert closure["status"] == "closed"
    assert audit["authorization_closed"] is True


def test_phase3f_strict_and_diagnostic_gates_remain_bounded():
    strict = strict_analysis.analyze()
    normalized = diagnostic.analyze()
    assert strict["contract_valid_rows"] == 221
    assert strict["decision_gate"] == "inconclusive"
    assert normalized["contract_valid_rows"] == 238
    assert normalized["decision_gate"] == "non_gating"
    assert normalized["descriptive_gate_if_normalization_preregistered"] == "inconclusive"
    assert normalized["metrics"]["irrelevant_single_rejection_rate"] == 1.0
    assert normalized["metrics"]["contextual_vs_irrelevant_normalized_answer_change_rate"] == 0.05
