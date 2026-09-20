from scripts import analyze_acl2027_phase3c_uptake_outcome_mediation_v1 as phase3c


def test_phase3c_mediation_audit_is_complete_closed_and_exhaustive():
    result=phase3c.audit()
    assert result["status"]=="complete" and result["tasks"]==60 and result["rows"]==300
    assert result["completed_calls"]==300
    assert sum(row["tasks"] for row in result["strata"].values())==60
    assert len(result["task_rows"])==60 and len({row["task_id"] for row in result["task_rows"]})==60
    assert result["decision_gate"] in {"positive","negative","inconclusive"}
    assert result["network_calls"]==result["provider_calls"]==result["model_calls"]==result["paid_api_calls"]==result["formal_scaling_calls"]==0


def test_phase3c_strata_match_frozen_phase3b_uptake_counts():
    result=phase3c.audit()
    assert result["strata"]["contextual_only"]["tasks"]==29
    assert result["strata"]["both_adopt"]["tasks"]==31
    assert result["strata"]["neither_adopt"]["tasks"]==0
    assert result["strata"]["shuffled_only"]["tasks"]==0
