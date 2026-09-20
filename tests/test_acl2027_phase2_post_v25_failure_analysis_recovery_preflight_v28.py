from scripts import run_acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v28 as recovery


def test_v28_is_closed_zero_network_and_requires_fresh_authorization() -> None:
    result = recovery.validate()
    assert all(value is False for value in result["execution"].values())
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0
    assert result["authorization_request_status"] == "fresh_explicit_user_authorization_required"


def test_v28_preserves_complete_grids_and_excludes_every_spent_request() -> None:
    result = recovery.validate()
    assert result["provenance"]["reusable_completed_tasks"] == 268
    assert result["provenance"]["reusable_completed_rows"] == 1072
    assert result["spent_v27_requests_excluded"] == 1073
    assert result["all_recovery_logical_ids_new"] is True
    assert result["all_recovery_request_hashes_new"] is True


def test_v28_freezes_balanced_528_call_recovery() -> None:
    result = recovery.validate()
    assert result["recovery_calls"] == 528
    assert result["recovery_tasks"] == 132
    assert result["combined_analysis_rows"] == 1600
    assert result["combined_task_count"] == 400
    assert all(value == 400 for value in result["combined_condition_counts"].values())
    assert result["analysis_gate_reached"] is False


def test_v28_proposal_keeps_later_work_closed() -> None:
    proposed = recovery.validate()["proposed_authorization"]
    assert proposed["requested_calls"] == proposed["max_provider_attempts"] == 528
    assert proposed["retries"] == 0
    assert proposed["max_tokens_present"] is False
    assert proposed["later_stages_authorized"] is False
    assert proposed["formal_scaling_authorized"] is False
