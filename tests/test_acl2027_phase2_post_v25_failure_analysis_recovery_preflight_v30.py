from scripts import run_acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v30 as recovery


def test_v30_is_closed_and_requires_fresh_authorization() -> None:
    result = recovery.validate()
    assert all(value is False for value in result["execution"].values())
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0
    assert result["authorization_request_status"] == "fresh_explicit_user_authorization_required"


def test_v30_preserves_only_complete_v27_v29_grids() -> None:
    result = recovery.validate()
    provenance = result["provenance"]
    assert provenance["v27_reusable_completed_rows"] == 1072
    assert provenance["v29_reusable_completed_rows"] == 308
    assert provenance["v29_orphan_completed_rows_excluded"] == 1
    assert result["spent_v27_v29_requests_excluded"] == 1383


def test_v30_freezes_balanced_220_call_recovery() -> None:
    result = recovery.validate()
    assert result["recovery_calls"] == 220
    assert result["recovery_tasks"] == 55
    assert result["combined_analysis_rows"] == 1600
    assert result["combined_task_count"] == 400
    assert all(value == 400 for value in result["combined_condition_counts"].values())
    assert result["all_recovery_logical_ids_new"] is True
    assert result["all_recovery_request_hashes_new"] is True


def test_v30_proposal_keeps_later_work_closed() -> None:
    proposed = recovery.validate()["proposed_authorization"]
    assert proposed["requested_calls"] == proposed["max_provider_attempts"] == 220
    assert proposed["known_cumulative_cost_lower_bound_cny"] == 6.13433
    assert proposed["later_stages_authorized"] is False
    assert proposed["formal_scaling_authorized"] is False
