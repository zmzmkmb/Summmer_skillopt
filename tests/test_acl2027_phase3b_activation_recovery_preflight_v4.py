from scripts import run_acl2027_phase3b_activation_recovery_preflight_v4 as recovery


def test_phase3b_v4_recovery_is_complete_closed_and_disjoint():
    result, documents = recovery.build()
    assert result["status"] == "recovery-preflight-passed-closed"
    assert result["v3_provider_attempts"] == 127 and result["v3_completed_calls"] == 126
    assert result["v3_reusable_complete_grid_rows"] == 125 and result["v3_reusable_complete_tasks"] == 25
    assert result["excluded_partial_completed_rows"] == result["excluded_terminal_rows"] == 1
    assert result["recovery_tasks"] == 35 and result["recovery_calls"] == 175
    assert result["combined_tasks"] == 60 and result["combined_rows"] == 300
    assert result["spent_request_hash_overlap"] == result["spent_logical_call_overlap"] == 0
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0
    assert len(documents["recovery_schedule.json"]["schedule"]) == 175
