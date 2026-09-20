import json

from scripts import run_acl2027_phase4b_contract_repair_live_preflight_v2 as preflight


def test_phase4b_r2_preflight_is_closed_and_binds_r1():
    result, request = preflight.validate()
    assert result["status"] == "live-execution-preflight-passed-closed"
    assert result["authorization_status"] == "fresh-exact-explicit-user-authorization-required"
    assert result["phase4b_repair_fingerprint"] == preflight.REPAIR_FINGERPRINT
    assert result["schedule_audit"]["rows"] == 100
    assert result["schedule_audit"]["tasks"] == 20
    assert result["schedule_audit"]["unique_logical_call_ids"] == 100
    assert result["schedule_audit"]["unique_request_hashes"] == 100
    assert not any(result["schedule_audit"]["identity_overlap_audit"].values())
    assert request["preflight_aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == 0
    assert result["paid_api_calls"] == result["phase4c_calls"] == 0


def test_phase4b_r2_revalidates_visible_contract_and_transport_hashes():
    audit = preflight.validate_schedule(preflight.schedule_rows())
    assert audit["contract_visible_in_all_transmitted_messages"] is True
    assert audit["evidence_ids_visible_in_all_transmitted_messages"] is True
    assert audit["condition_counts"] == {condition: 20 for condition in sorted(preflight.CONDITIONS)}
    assert audit["unique_transport_payload_hashes"] == 80
    assert audit["duplicate_transport_pair_count"] == 20
    assert audit["duplicate_transport_pair_conditions"] == ["global_only", "contextual_typed"]


def test_phase4b_r2_exact_route_cost_pacing_and_stop_contract():
    result, _ = preflight.validate()
    contract = result["execution_contract"]
    assert contract["endpoint"] == preflight.ENDPOINT
    assert contract["model_id"] == "qwen3.7-plus"
    assert contract["authorized_calls"] == contract["max_provider_attempts"] == 100
    assert contract["temperature"] == 0 and contract["enable_thinking"] is False
    assert contract["retries"] == 0 and contract["max_tokens_present"] is False
    assert contract["response_format"] == {"type": "json_object"}
    assert contract["request_interval_seconds"] == 1.0
    assert contract["stage_cost_ceiling_cny"] == 2.0
    assert contract["cumulative_cost_ceiling_cny"] == 15.0
    assert contract["known_cumulative_cost_lower_bound_cny"] == 11.816126
    assert contract["terminal_stop_on_first_failed_attempt"] is True
    assert contract["authorization_closes_on_completion_or_terminal_stop"] is True
    assert contract["exact_prefix_resume_only"] is True
    assert contract["hash_chain_required"] is True


def test_phase4b_r2_authorization_request_discloses_equivalent_payloads():
    result, request = preflight.validate()
    assert result["authorization_receipt_exists"] is False
    assert result["authorization_open_exists"] is False
    statement = request["authorization_statement_verbatim"]
    assert preflight.REPAIR_FINGERPRINT in statement
    assert result["aggregate_fingerprint"] in statement
    assert preflight.ENDPOINT in statement
    assert "80" in statement and "20" in statement
    assert "CNY 2.00" in statement and "CNY 15.00" in statement


def test_phase4b_r2_written_artifact_matches_validation():
    result, request = preflight.validate()
    manifest = json.loads((preflight.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    written_request = json.loads((preflight.ARTIFACT / "authorization_request.json").read_text(encoding="utf-8"))
    completion = json.loads((preflight.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert written_request == request
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert completion["proposed_calls"] == 100
    assert completion["completed_calls"] == 100
    assert completion["rows"] == 100
    assert completion["schedule_rows_bound"] == 100
    assert completion["provider_calls_executed"] == 0
