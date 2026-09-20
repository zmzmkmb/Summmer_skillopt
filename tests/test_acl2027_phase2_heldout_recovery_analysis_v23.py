from scripts.analyze_acl2027_phase2_heldout_recovery_v23 import analyze


def test_v23_combined_heldout_gate_is_complete_and_inconclusive() -> None:
    result = analyze()
    assert result["status"] == "complete"
    assert result["combined_rows"] == 320
    assert result["combined_tasks"] == 80
    assert result["v21_preserved_rows"] == 232
    assert result["v23_recovery_rows"] == 88
    assert result["contract_valid_counts"] == {
        "cold": 80,
        "copied_global": 80,
        "global_only": 80,
        "contextual_typed_prior": 80,
    }
    assert result["condition_correct_counts"] == {
        "cold": 62,
        "copied_global": 59,
        "global_only": 59,
        "contextual_typed_prior": 60,
    }
    paired = result["primary_paired_comparison"]
    assert paired["contextual_typed_prior_minus_global_only_accuracy"] == 0.012499999999999956
    assert paired["typed_wins"] == 2
    assert paired["typed_losses"] == 1
    assert paired["ties"] == 77
    assert result["eligibility_gate"] == "inconclusive"
    assert result["calibration_calls"] == result["development_calls"] == 0
    assert result["formal_history_calls"] == result["probe_calls"] == 0
    assert result["later_stage_calls"] == result["formal_scaling_calls"] == 0
