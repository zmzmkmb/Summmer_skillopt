import json

from scripts import run_acl2027_phase4b_contract_repair_live_v3 as live


def test_r3_preflight_binds_repair_schedule():
    rows = live.preflight()
    assert len(rows) == 100
    assert live.PREFLIGHT_FINGERPRINT == "94a2e284a4049db12f5e1f1294fa92d4433547ee9be0dd151e6ba848bbc7da28"
    assert live.REPAIR_FINGERPRINT == "a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c"
    assert len({row["logical_call_id"] for row in rows}) == 100
    assert len({row["request_hash"] for row in rows}) == 100
    assert len({row["transport_payload_hash"] for row in rows}) == 80


def test_r3_receipt_is_scoped_and_closed_before_opening():
    receipt = live.receipt()
    assert receipt["status"] == "explicit_user_authorization_received_execution_not_open"
    assert receipt["phase4b_repair_fingerprint"] == live.REPAIR_FINGERPRINT
    assert receipt["phase4b_live_preflight_fingerprint"] == live.PREFLIGHT_FINGERPRINT
    assert receipt["authorized_calls"] == 100
    assert receipt["paid_usage_authorized"] is True
    assert receipt["execution"]["qwen_authorization_open"] is False
    assert receipt["forbidden_stages"] == ["other_models", "later_phase4", "cross_domain_scaling", "formal_scaling"]


def test_r3_transport_contract_is_visible():
    for row in live.preflight():
        projection = row["transport_projection"]
        assert set(projection) == {"model", "messages", "temperature", "enable_thinking", "response_format"}
        system = projection["messages"][0]["content"]
        assert all(key in system for key in ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer"))
        user = json.loads(projection["messages"][1]["content"])
        assert user["response_contract"]["exact_keys"] == ["skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer"]
        assert all(sentence["id"] for block in user["context"] for sentence in block["sentences"])
