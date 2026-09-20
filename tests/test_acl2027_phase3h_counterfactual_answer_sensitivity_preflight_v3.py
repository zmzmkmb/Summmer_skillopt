import json

from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v3 as phase


def test_phase3h_v3_is_closed_balanced_and_zero_network():
    result = phase.validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["task_count"] == result["counterfactually_identifiable_tasks"] == 40
    assert result["logical_calls_proposed"] == 200
    assert result["family_counts"] == {"attribute_comparison": 20, "bridge_attribute_comparison": 20}
    assert result["condition_counts"] == {condition: 40 for condition in phase.CONDITIONS}
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == 0
    assert result["paid_api_calls"] == result["later_stage_calls"] == result["formal_scaling_calls"] == 0


def test_phase3h_v3_has_distinct_answers_native_mapping_and_new_identities():
    tasks, selection = phase.select_tasks()
    schedule, _ = phase.base.build_schedule(tasks)
    assert selection["prior_task_overlap"] == 0
    for task in tasks:
        assert all(task["counterfactual_validity"].values())
        assert phase.normalize(task["target_answer"]) != phase.normalize(task["counterfactual_answer"])
        grid = {row["condition"]: row for row in schedule if row["task_id"] == task["task_id"]}
        control = grid["incompatible_control"]
        assert control["expected_selected_skill_id"] == control["control_candidate_id"]
        assert control["expected_applicability"] == {control["control_candidate_id"]: False}
        assert grid["dual_contextual_first"]["candidate_order"] == list(reversed(grid["dual_control_first"]["candidate_order"]))
    identities = phase.validate()["identity_overlap_audit"]
    assert identities["task_id_overlap"] == identities["logical_call_id_overlap"] == identities["request_hash_overlap"] == 0


def test_phase3h_v3_completion_schema_and_artifact_are_deterministic():
    result = phase.validate()
    schedule = json.loads((phase.ARTIFACT / "counterfactual_schedule.json").read_text(encoding="utf-8"))["schedule"]
    for row in schedule:
        keys = {key for record in phase.base.walk_records(row["canonical_request_body"]) for key in record}
        assert "target_answer" not in keys
        assert "counterfactual_answer" not in keys
        assert row["logical_call_id"].startswith("phase3h-v3:")
    manifest = json.loads((phase.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((phase.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert completion["completed_calls"] == completion["rows"] == 200
    assert completion["provider_calls_executed"] == 0
