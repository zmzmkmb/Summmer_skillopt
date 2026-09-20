from scripts.analyze_acl2027_phase2_heldout_live_v21 import analyze


def test_v21_partial_heldout_audit_is_terminal_and_non_gating():
    result = analyze()
    assert result["status"] == "partial_terminal_hard_stop"
    assert result["planned_calls"] == 320
    assert result["completed_calls"] == 233
    assert result["terminal_rows"] == 1
    assert result["full_task_grids"] == 58
    assert result["contract_valid_counts"] == {
        "cold": 59,
        "copied_global": 58,
        "global_only": 58,
        "contextual_typed_prior": 58,
    }
    assert result["full_grid_primary_comparison"]["margin"] == 0.0
    assert result["eligibility_gate"] == "not_reached_incomplete_held_out_prefix"
    assert result["later_stage_calls"] == result["formal_scaling_calls"] == 0
