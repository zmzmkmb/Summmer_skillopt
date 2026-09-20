import json

from scripts import run_acl2027_phase4b_contract_repair_recovery_live_preflight_v5 as preflight


def test_r5_is_closed_zero_network_and_binds_r4() -> None:
    result, request = preflight.validate()
    assert result["status"] == "live-execution-preflight-passed-closed"
    assert result["source_recovery_fingerprint"] == "fc668155d0e1d787fe45bf381f5958d8f9d5d78759be3c0bab3951580254f066"
    assert all(value is False for value in result["execution"].values())
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0
    assert request["preflight_aggregate_fingerprint"] == result["aggregate_fingerprint"]


def test_r5_freezes_exact_28_call_route_contract() -> None:
    contract = preflight.validate()[0]["execution_contract"]
    assert contract["authorized_calls"] == contract["max_provider_attempts"] == 28
    assert contract["endpoint"] == preflight.ENDPOINT
    assert contract["model_id"] == "qwen3.7-plus"
    assert contract["temperature"] == 0 and contract["enable_thinking"] is False
    assert contract["retries"] == 0 and contract["max_tokens_present"] is False
    assert contract["response_format"] == {"type": "json_object"}
    assert contract["request_interval_seconds"] == 1.0
    assert contract["stage_cost_ceiling_cny"] == 0.30
    assert contract["cumulative_cost_ceiling_cny"] == 15.00


def test_r5_cost_policy_reserves_unknown_orphan_and_stays_below_cumulative_cap() -> None:
    contract = preflight.validate()[0]["execution_contract"]
    assert contract["orphan_usage_reserve_cny"] == 0.011136
    assert contract["known_cumulative_cost_lower_bound_cny"] == 12.328920
    assert contract["projected_known_upper_bound_cny"] == 12.640056
    assert contract["projected_known_upper_bound_cny"] < contract["cumulative_cost_ceiling_cny"]


def test_r5_preserves_transport_equivalence_disclosure_and_forbidden_scope() -> None:
    result, request = preflight.validate()
    eq = result["known_transport_equivalence"]
    assert eq["unique_transport_payloads_in_combined_grid"] == 80
    assert eq["duplicate_pair_count"] == 20
    assert eq["causal_comparison_identifiable"] is False
    assert request["orphan_transport_repeat_disclosure"]["same_logical_or_request_identity"] is False
    assert "phase4c" in request["forbidden_scope"]
    assert "formal_scaling" in request["forbidden_scope"]


def test_r5_written_artifact_matches_validation() -> None:
    result, request = preflight.validate()
    manifest = json.loads((preflight.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    written_request = json.loads((preflight.ARTIFACT / "authorization_request.json").read_text(encoding="utf-8"))
    completion = json.loads((preflight.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert written_request == request
    assert completion["proposed_calls"] == completion["completed_calls"] == completion["rows"] == 28
    assert completion["provider_calls_executed"] == 0
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
