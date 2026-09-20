import json
from pathlib import Path

V2_ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v2"


def test_phase3h_v2_is_preserved_as_unaccepted_zero_call_provenance():
    manifest = json.loads((V2_ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((V2_ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["aggregate_fingerprint"] == "41a5e6f82c5503c09bf380f0489bcc5fef9af8343f4f46ab790c03ee7f956e64"
    assert manifest["network_calls"] == manifest["provider_calls"] == manifest["model_calls"] == 0
    assert manifest["paid_api_calls"] == manifest["later_stage_calls"] == manifest["formal_scaling_calls"] == 0
    assert completion["completed_calls"] == 0
    assert "rows" not in completion
    assert completion["authorization_status"] == "not-authorized"
