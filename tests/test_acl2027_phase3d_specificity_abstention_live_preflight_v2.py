import json

from scripts import run_acl2027_phase3d_specificity_abstention_live_preflight_v2 as preflight


def test_phase3d_v2_preflight_is_closed_and_binds_all_requests():
    result, request = preflight.validate()
    assert result["status"] == "live-execution-preflight-passed-closed"
    assert result["authorization_status"] == "fresh-explicit-user-authorization-required"
    assert result["phase3d_design_fingerprint"] == preflight.DESIGN_FINGERPRINT
    assert result["schedule_audit"]["rows"] == 240
    assert result["schedule_audit"]["tasks"] == 40
    assert result["schedule_audit"]["unique_logical_call_ids"] == 240
    assert result["schedule_audit"]["unique_request_hashes"] == 240
    assert set(result["schedule_audit"]["condition_counts"].values()) == {40}
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["model_calls"] == result["paid_api_calls"] == 0
    assert result["later_stage_calls"] == result["cross_domain_scaling_calls"] == 0
    assert result["formal_scaling_calls"] == 0
    assert request["preflight_aggregate_fingerprint"] == result["aggregate_fingerprint"]


def test_phase3d_v2_exact_route_cost_pacing_and_stop_contract():
    result, _ = preflight.validate()
    contract = result["execution_contract"]
    assert contract["endpoint"] == preflight.ENDPOINT
    assert contract["model_id"] == "qwen3.7-plus"
    assert contract["authorized_calls"] == contract["max_provider_attempts"] == 240
    assert contract["temperature"] == 0 and contract["enable_thinking"] is False
    assert contract["retries"] == 0 and contract["max_tokens_present"] is False
    assert contract["response_format"] == {"type": "json_object"}
    assert contract["request_interval_seconds"] == 1.0
    assert contract["stage_cost_ceiling_cny"] == 3.0
    assert contract["cumulative_cost_ceiling_cny"] == 15.0
    assert contract["terminal_stop_on_first_failed_attempt"] is True
    assert contract["authorization_closes_on_completion_or_terminal_stop"] is True
    assert contract["exact_prefix_resume_only"] is True


def test_phase3d_v2_payload_egress_requires_exact_explicit_authorization():
    result, request = preflight.validate()
    assert result["authorization_receipt_exists"] is False
    assert result["authorization_open_exists"] is False
    assert result["execution_contract"]["payload_classes"] == [
        "frozen_task_prompts",
        "frozen_task_contexts",
        "frozen_historical_skill_candidate_bundles",
    ]
    statement = request["authorization_statement_verbatim"]
    assert preflight.DESIGN_FINGERPRINT in statement
    assert result["aggregate_fingerprint"] in statement
    assert preflight.ENDPOINT in statement
    assert "240" in statement and "CNY 3.00" in statement and "CNY 15.00" in statement


def test_phase3d_v2_written_artifact_matches_validation():
    result, request = preflight.validate()
    manifest = json.loads((preflight.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    written_request = json.loads((preflight.ARTIFACT / "authorization_request.json").read_text(encoding="utf-8"))
    completion = json.loads((preflight.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert written_request == request
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert completion["schedule_rows_bound"] == 240
    assert completion["provider_calls_executed"] == 0
