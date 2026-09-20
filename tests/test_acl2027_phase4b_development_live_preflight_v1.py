import json
from scripts import run_acl2027_phase4b_development_live_preflight_v1 as phase


def test_phase4b_preflight_is_closed_and_balanced():
    result, _ = phase.validate()
    assert result["status"] == "live-execution-preflight-passed-closed"
    assert result["authorization_status"] == "fresh-exact-explicit-user-authorization-required"
    assert result["schedule_audit"]["rows"] == 100
    assert result["schedule_audit"]["condition_counts"] == {condition: 20 for condition in phase.CONDITIONS}
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0


def test_phase4b_preflight_artifact_matches_validation():
    result, request = phase.validate()
    assert json.loads((phase.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8")) == result
    assert json.loads((phase.ARTIFACT / "authorization_request.json").read_text(encoding="utf-8")) == request
