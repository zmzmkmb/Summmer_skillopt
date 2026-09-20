import json

from scripts import run_acl2027_phase3d_specificity_abstention_preflight_v1 as phase3d


def test_phase3d_preflight_is_closed_balanced_and_complete():
    result = phase3d.validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["task_count"] == 40
    assert result["logical_calls_proposed"] == 240
    assert result["family_counts"] == {
        "attribute_comparison": 20,
        "bridge_attribute_comparison": 20,
    }
    assert set(result["condition_counts"].values()) == {40}
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["model_calls"] == result["paid_api_calls"] == 0
    assert result["formal_scaling_calls"] == 0


def test_phase3d_uses_new_tasks_and_unique_request_identities():
    tasks, selection = phase3d.select_tasks()
    schedule, _ = phase3d.build_schedule(tasks)
    identities = phase3d.identity_audit(tasks, schedule, selection)
    assert len({row["task_id"] for row in tasks}) == 40
    assert len({row["logical_call_id"] for row in schedule}) == 240
    assert len({row["request_hash"] for row in schedule}) == 240
    assert identities["task_id_overlap"] == 0
    assert identities["logical_call_id_overlap"] == 0
    assert identities["request_hash_overlap"] == 0


def test_phase3d_dual_conditions_reverse_order_without_changing_target():
    tasks, _ = phase3d.select_tasks()
    schedule, _ = phase3d.build_schedule(tasks)
    for task in tasks:
        grid = {row["condition"]: row for row in schedule if row["task_id"] == task["task_id"]}
        left = grid["dual_contextual_first"]
        right = grid["dual_irrelevant_first"]
        assert left["candidate_order"] == list(reversed(right["candidate_order"]))
        assert left["expected_specificity_selection"] == right["expected_specificity_selection"]
        assert grid["irrelevant_single"]["expected_specificity_selection"] == "none"


def test_phase3d_contract_is_candidate_complete_and_gold_free():
    tasks, _ = phase3d.select_tasks()
    schedule, _ = phase3d.build_schedule(tasks)
    for row in schedule:
        body = row["canonical_request_body"]
        contract = body["response_contract"]
        assert tuple(contract["exact_keys"]) == phase3d.RESPONSE_KEYS
        assert contract["skill_assessments"]["skill_id_order"] == row["candidate_order"]
        assert contract["skill_assessments"]["length"] == len(row["candidate_order"])
        assert not phase3d.contains_forbidden_gold_key(body)


def test_phase3d_written_artifact_matches_deterministic_validation():
    result = phase3d.validate()
    manifest = json.loads((phase3d.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((phase3d.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert completion["completed_calls"] == completion["rows"] == 240
