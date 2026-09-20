from scripts.materialize_acl2027_phase1y_live_candidates import build


def test_live_candidate_materialization_and_coverage_failure():
    audit = build()
    assert audit["verified_trajectories"] == 8
    assert audit["typed_candidates"] == 3
    assert audit["checks"]["no_evaluation_leakage"] is True
    assert audit["checks"]["family_type_coverage_met"] is False
    assert audit["coverage"]["missing_skill_families"] == ["entity_bridge", "relation_inference"]
    assert audit["phase1z"]["theoretical_minimum_additional_successful_calls"] == 2
    assert audit["phase1z"]["currently_authorized_calls"] == 0


def test_candidate_ids_and_support_are_deterministic():
    first, second = build(), build()
    assert first["candidate_records"] == second["candidate_records"]
    accepted = [row for row in first["candidate_records"] if row["admitted"]]
    assert len(accepted) == 3
    assert all(len(row["supporting_task_ids"]) == 2 for row in accepted)
