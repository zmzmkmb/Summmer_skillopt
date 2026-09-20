from scripts.run_acl2027_phase2_probe_replacement_schedule_preflight_v16 import select_replacement, validate


def test_v16_blocks_nonidentifiable_schedule_and_selects_unused_replacement() -> None:
    result = validate()
    assert result["status"] == "blocked-condition-semantics"
    assert result["null_candidate_id_rows"] == 160
    assert result["pending_candidate_version_rows"] == 160
    assert result["model_visible_prior_payload_rows"] == 0
    assert result["spent_task_grid_rows_removed"] == result["replacement_task_grid_rows_planned"] == 4
    assert result["schedule_written"] is False
    assert result["authorization_request_status"] == "blocked_not_submittable"
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0
    replacement = select_replacement()
    assert replacement["candidate_pool_size"] > 0
    assert replacement["replacement_not_in_any_phase2_partition"] is True
