from scripts.run_acl2027_phase3b_activation_preflight_v1 import (
    ARTIFACT,
    CONDITIONS,
    FAMILIES,
    RESPONSE_KEYS,
    TASKS_PER_FAMILY,
    build_schedule,
    contains_forbidden_gold_key,
    identity_audit,
    load,
    select_tasks,
    validate,
)


def test_phase3b_is_closed_zero_network_and_preserves_phase2_gate() -> None:
    result = validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["authorization_artifact_created"] is False
    assert result["phase2_gate_preserved"] == "inconclusive"
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["model_calls"] == result["paid_api_calls"] == result["formal_scaling_calls"] == 0


def test_phase3b_selects_balanced_new_tasks_without_gold() -> None:
    tasks, selection = select_tasks()
    assert len(tasks) == len({task["task_id"] for task in tasks}) == 60
    assert selection["selection_uses_gold"] is False
    assert selection["phase2_task_overlap"] == 0
    assert {family: sum(task["skill_family"] == family for task in tasks) for family in FAMILIES} == {
        family: TASKS_PER_FAMILY for family in FAMILIES
    }


def test_phase3b_freezes_300_unique_five_condition_requests() -> None:
    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    assert len(private_gold) == 60
    assert len(schedule) == 300
    assert len({row["logical_call_id"] for row in schedule}) == 300
    assert len({row["request_hash"] for row in schedule}) == 300
    assert {condition: sum(row["condition"] == condition for row in schedule) for condition in CONDITIONS} == {
        condition: 60 for condition in CONDITIONS
    }
    assert identities["task_id_overlap"] == 0
    assert identities["logical_call_id_overlap"] == 0
    assert identities["request_hash_overlap"] == 0


def test_phase3b_contract_shuffled_control_and_leakage_guards() -> None:
    tasks, _ = select_tasks()
    schedule, _ = build_schedule(tasks)
    for task in tasks:
        grid = [row for row in schedule if row["task_id"] == task["task_id"]]
        assert {row["condition"] for row in grid} == set(CONDITIONS)
        assert len({row["prior_payload_sha256"] for row in grid}) == 5
        shuffled = next(row for row in grid if row["condition"] == "shuffled_typed_prior")
        assert shuffled["source_skill_family"] != shuffled["target_skill_family"]
    for row in schedule:
        body = row["canonical_request_body"]
        assert tuple(body["response_contract"]["exact_keys"]) == RESPONSE_KEYS
        assert contains_forbidden_gold_key(body) is False
        assert "max_tokens" not in body
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}


def test_phase3b_analysis_rules_and_written_artifact_are_deterministic() -> None:
    first = validate()
    second = validate()
    assert first == second
    assert first["analysis_plan"]["no_posthoc_regating"] is True
    assert "contextual uptake is below 0.15" in first["analysis_plan"]["stop_rule"]
    if ARTIFACT.exists():
        manifest = load(ARTIFACT / "run_manifest.json")
        assert manifest["aggregate_fingerprint"] == first["aggregate_fingerprint"]
        assert manifest["documents"] == first["documents"]
