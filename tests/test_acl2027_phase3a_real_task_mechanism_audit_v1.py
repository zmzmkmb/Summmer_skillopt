from scripts import analyze_acl2027_phase3a_real_task_mechanism_audit_v1 as phase3a


def test_phase3a_reproduces_frozen_uptake_counts():
    audit, diagnostics, pilot = phase3a.analyze()
    assert audit["rows"] == audit["completed_calls"] == len(diagnostics) == 400
    assert audit["analyzed_phase2_response_rows"] == 1600
    assert audit["uptake_counts"]["all_response_hashes_identical"] == 294
    assert audit["uptake_counts"]["all_normalized_answers_identical"] == 340
    assert audit["uptake_counts"]["all_strict_outcomes_equal"] == 358
    assert audit["uptake_counts"]["all_alias_outcomes_equal"] == 368
    assert audit["uptake_counts"]["typed_global_response_differs"] == 53
    assert sum(audit["taxonomy_counts"].values()) == 400
    assert pilot["logical_calls"] == 300


def test_phase3a_preserves_phase2_and_rejects_random_scale_up():
    audit, _, pilot = phase3a.analyze()
    assert audit["phase2_gate_preserved"] == "inconclusive"
    assert audit["random_scale_up_decision"] == "reject_random_scale_up"
    assert audit["mechanism_bridge_required"] is True
    assert audit["next_stage"] == "phase3b_activation_preflight_design_only"
    assert pilot["provider_execution_authorized"] is False
    assert pilot["authorization_artifact_created"] is False
    assert audit["network_calls"] == audit["provider_calls"] == 0
    assert audit["model_calls"] == audit["paid_api_calls"] == 0


def test_phase3a_fingerprint_and_documents_are_deterministic():
    first, first_tasks, first_pilot = phase3a.analyze()
    second, second_tasks, second_pilot = phase3a.analyze()
    assert first == second
    assert first_tasks == second_tasks
    assert first_pilot == second_pilot
    assert len(first["aggregate_fingerprint"]) == 64
