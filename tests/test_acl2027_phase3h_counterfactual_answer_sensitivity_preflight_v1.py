import json
from pathlib import Path

from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1 as phase

V1_ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1"


def test_phase3h_v1_is_preserved_as_unaccepted_zero_call_provenance():
    manifest = json.loads((V1_ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((V1_ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["aggregate_fingerprint"] == "9888dac8cef340a6fee5b09252ad19911d7febae5a4b7cf9dacb2b2df6dc906b"
    assert manifest["network_calls"] == manifest["provider_calls"] == manifest["model_calls"] == 0
    assert manifest["paid_api_calls"] == manifest["later_stage_calls"] == manifest["formal_scaling_calls"] == 0
    assert completion["completed_calls"] == 0
    assert completion["authorization_status"] == "not-authorized"
