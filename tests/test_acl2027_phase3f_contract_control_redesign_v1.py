import json

from scripts import run_acl2027_phase3f_contract_control_redesign_v1 as phase


def test_phase3f_is_closed_balanced_and_zero_network():
    result = phase.validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["task_count"] == 40
    assert result["logical_calls_proposed"] == 240
    assert result["family_counts"] == {"attribute_comparison": 20, "bridge_attribute_comparison": 20}
    assert set(result["condition_counts"].values()) == {40}
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["model_calls"] == result["paid_api_calls"] == result["formal_scaling_calls"] == 0


def test_phase3f_uses_native_mapping_and_operation_incompatible_bridge_control():
    tasks, _ = phase.select_tasks()
    schedule, _ = phase.build_schedule(tasks)
    for task in tasks:
        grid = {row["condition"]: row for row in schedule if row["task_id"] == task["task_id"]}
        contextual = grid["contextual_single"]
        contract = contextual["canonical_request_body"]["response_contract"]["skill_assessments"]
        assert contract["type"] == "object"
        assert contract["exact_candidate_id_keys"] == contextual["candidate_order"]
        assert grid["dual_contextual_first"]["candidate_order"] == list(reversed(grid["dual_irrelevant_first"]["candidate_order"]))
        if task["skill_family"] == "bridge_attribute_comparison":
            control = grid["irrelevant_single"]
            assert control["control_skill_family"] == "fact_retrieval"
            candidate = json.loads(control["canonical_request_body"]["messages"][1]["content"].split("Historical skill candidates in assessment order:\n", 1)[1].split("\n\nQuestion:", 1)[0])[0]
            assert candidate["control_validity"] == "cannot_supply_required_entity_bridge"


def test_phase3f_identities_are_new_and_written_artifact_is_deterministic():
    result = phase.validate()
    identities = result["identity_overlap_audit"]
    assert identities["task_id_overlap"] == identities["logical_call_id_overlap"] == identities["request_hash_overlap"] == 0
    manifest = json.loads((phase.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((phase.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
