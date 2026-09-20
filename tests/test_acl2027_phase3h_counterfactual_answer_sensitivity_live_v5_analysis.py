from scripts import analyze_acl2027_phase3h_counterfactual_answer_sensitivity_live_v5 as analysis


def test_phase3h_v5_analysis_is_complete_and_remains_bounded():
    result = analysis.analyze()
    assert result["status"] == "complete"
    assert result["audit"]["completed_calls"] == result["audit"]["provider_attempts"] == 200
    assert result["audit"]["retries"] == 0
    assert result["cross_domain_scaling_authorized"] is False
    assert result["formal_scaling_authorized"] is False
