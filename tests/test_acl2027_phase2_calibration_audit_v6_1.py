from scripts.audit_acl2027_phase2_calibration_v6_1 import build_supplement


def test_closed_unknown_usage_cost_is_not_reported_as_exact_zero() -> None:
    supplement = build_supplement()
    assert supplement["provider_attempts"] == 1
    assert supplement["provider_accepted_calls"] == 0
    assert supplement["cost_status"] == "unknown_usage_terminal_hard_stop"
    assert supplement["exact_local_cost_cny"] is None
    assert supplement["authorization_closed"] is True
