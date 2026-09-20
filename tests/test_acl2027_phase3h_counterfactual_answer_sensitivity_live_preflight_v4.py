import json

from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_live_preflight_v4 as preflight


def test_phase3h_v4_preflight_is_closed_and_binds_all_requests():
    result, request = preflight.validate()
    assert result["status"] == "live-execution-preflight-passed-closed"
    assert result["authorization_status"] == "fresh-exact-explicit-user-authorization-required"
    assert result["phase3h_design_fingerprint"] == preflight.DESIGN_FINGERPRINT
    assert result["schedule_audit"]["rows"] == 200
    assert result["schedule_audit"]["tasks"] == 40
    assert result["schedule_audit"]["unique_logical_call_ids"] == 200
    assert result["schedule_audit"]["unique_request_hashes"] == 200
    assert set(result["schedule_audit"]["condition_counts"].values()) == {40}
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == 0
    assert result["paid_api_calls"] == result["later_stage_calls"] == 0
    assert result["cross_domain_scaling_calls"] == result["formal_scaling_calls"] == 0
    assert request["preflight_aggregate_fingerprint"] == result["aggregate_fingerprint"]


def test_phase3h_v4_exact_route_cost_pacing_and_stop_contract():
    result, _ = preflight.validate()
    contract = result["execution_contract"]
    assert contract["endpoint"] == preflight.ENDPOINT
    assert contract["model_id"] == "qwen3.7-plus"
    assert contract["authorized_calls"] == contract["max_provider_attempts"] == 200
    assert contract["temperature"] == 0 and contract["enable_thinking"] is False
    assert contract["retries"] == 0 and contract["max_tokens_present"] is False
    assert contract["response_format"] == {"type": "json_object"}
    assert contract["request_interval_seconds"] == 1.0
    assert contract["stage_cost_ceiling_cny"] == 3.0
    assert contract["cumulative_cost_ceiling_cny"] == 15.0
    assert contract["known_cumulative_cost_lower_bound_cny"] == 10.334338
    assert contract["terminal_stop_on_first_failed_attempt"] is True
    assert contract["authorization_closes_on_completion_or_terminal_stop"] is True
    assert contract["exact_prefix_resume_only"] is True


def test_phase3h_v4_payload_egress_requires_exact_explicit_authorization():
    result, request = preflight.validate()
    assert result["authorization_receipt_exists"] is False
    assert result["authorization_open_exists"] is False
    assert result["execution_contract"]["payload_classes"] == [
        "frozen_task_prompts",
        "frozen_task_contexts",
        "frozen_procedure_candidate_bundles",
    ]
    statement = request["authorization_statement_verbatim"]
    assert preflight.DESIGN_FINGERPRINT in statement
    assert result["aggregate_fingerprint"] in statement
    assert preflight.ENDPOINT in statement
    assert "200" in statement and "CNY 3.00" in statement and "CNY 15.00" in statement
    assert statement != "我授权开始"


def test_phase3h_v4_written_artifact_matches_validation():
    result, request = preflight.validate()
    manifest = json.loads((preflight.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    written_request = json.loads((preflight.ARTIFACT / "authorization_request.json").read_text(encoding="utf-8"))
    completion = json.loads((preflight.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert written_request == request
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert completion["schedule_rows_bound"] == 200
    assert completion["provider_calls_executed"] == 0
