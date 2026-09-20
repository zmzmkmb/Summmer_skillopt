from scripts.audit_acl2027_phase2_probe_only_v14_1 import build


def test_v14_1_preserves_unknown_usage_semantics_and_closed_scope() -> None:
    audit = build()
    assert audit["provider_attempts"] == audit["unique_logical_requests"] == 1
    assert audit["usage_known_for_all_attempts"] is False
    assert audit["total_tokens"] is None
    assert audit["exact_local_cost_cny"] is None
    assert audit["known_cost_lower_bound_cny"] == 0.0
    assert audit["authorization_closed"] is True
    assert audit["held_out_calls"] == audit["formal_scaling_calls"] == 0
