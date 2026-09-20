from scripts.audit_acl2027_phase2_post_v25_failure_analysis_v27_1 import build


def test_v27_1_corrects_stale_terminal_usage_without_rewriting_provenance() -> None:
    audit = build()
    assert audit["provider_attempts"] == 1073
    assert audit["completed_calls"] == 1072
    assert audit["skipped_after_hard_stop"] == 527
    assert audit["usage_known_for_all_attempts"] is False
    assert audit["exact_local_cost_cny"] is None
    assert audit["known_local_cost_lower_bound_cny"] > 0
    assert audit["analysis_gate_reached"] is False
    assert audit["authorization_closed"] is True
