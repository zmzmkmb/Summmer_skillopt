from scripts.run_acl2027_phase2_probe_prompt_route_correction_preflight_v15 import validate


def test_v15_zero_network_correction_required_and_spent_request_excluded() -> None:
    result = validate()
    assert result["status"] == "correction-required"
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0
    assert result["frozen_probe_rows"] == 160
    assert result["excluded_spent_rows"] == 1
    assert result["v8_json_contract_verified"] is True
    assert result["adapter_json_route_verified"] is True
    assert result["fresh_authorization_required"] is True
    assert result["held_out_authorized"] is False
    assert result["formal_scaling_authorized"] is False
