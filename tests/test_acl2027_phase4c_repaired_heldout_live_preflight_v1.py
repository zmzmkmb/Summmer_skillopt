from scripts import run_acl2027_phase4c_repaired_heldout_live_preflight_v1 as preflight
def test_preflight_closed_and_balanced():
    result, request = preflight.validate()
    assert result["status"] == "live-execution-preflight-passed-closed"
    assert result["schedule_audit"]["rows"] == 400 and result["schedule_audit"]["heldout_tasks"] == 80
    assert result["schedule_audit"]["condition_counts"] == {c:80 for c in sorted(preflight.CONDITIONS)}
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0
    assert request["preflight_aggregate_fingerprint"] == result["aggregate_fingerprint"]
def test_authorization_binds_design_and_limits():
    result, request = preflight.validate(); s=request["authorization_statement_verbatim"]
    assert preflight.DESIGN_FINGERPRINT in s and result["aggregate_fingerprint"] in s
    assert "400 frozen requests" in s and "CNY 3.00" in s and "CNY 15.00" in s
