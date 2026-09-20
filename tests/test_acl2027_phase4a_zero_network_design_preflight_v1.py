import json

from scripts import run_acl2027_phase4a_zero_network_design_preflight_v1 as phase


def test_phase4a_is_closed_balanced_and_zero_network():
    result = phase.validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["task_count"] == 100
    assert result["development_tasks"] == 20
    assert result["heldout_tasks"] == 80
    assert result["logical_calls_proposed"] == 500
    assert result["condition_counts"] == {condition: 100 for condition in phase.CONDITIONS}
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0


def test_phase4a_has_no_prior_identity_overlap_and_uniform_contract():
    result = phase.validate()
    assert all(value == 0 for value in result["identity_overlap_audit"].values())
    assert result["response_contract"]["exact_keys"] == ["skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer"]


def test_phase4a_artifact_is_deterministic_and_not_authorized():
    result = phase.validate()
    manifest = json.loads((phase.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((phase.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert completion["completed_calls"] == completion["proposed_calls"] == 500
    assert completion["provider_calls_executed"] == 0
    assert completion["authorization_status"] == "not-authorized"
