from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import (
    ARTIFACT,
    CONDITIONS,
    FAMILIES,
    TASKS_PER_FAMILY,
    build_schedule,
    contains_forbidden_gold_key,
    load,
    select_tasks,
    validate,
)


def test_v24_is_closed_zero_network_design_only() -> None:
    result = validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["authorization_artifact_created"] is False
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["model_calls"] == result["paid_api_calls"] == result["formal_scaling_calls"] == 0
    assert result["v23_gate"] == "inconclusive"


def test_v24_freezes_balanced_new_task_and_condition_grids() -> None:
    tasks, audit = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    assert len(tasks) == len(private_gold) == 80
    assert len({task["task_id"] for task in tasks}) == 80
    assert audit["selected_prior_overlap"] == 0
    assert {family: sum(task["skill_family"] == family for task in tasks) for family in FAMILIES} == {
        family: TASKS_PER_FAMILY for family in FAMILIES
    }
    assert len(schedule) == 320
    assert {condition: sum(row["condition"] == condition for row in schedule) for condition in CONDITIONS} == {
        condition: 80 for condition in CONDITIONS
    }
    assert len({row["logical_call_id"] for row in schedule}) == 320
    assert len({row["request_hash"] for row in schedule}) == 320


def test_v24_requests_have_distinct_semantics_and_no_gold() -> None:
    tasks, _ = select_tasks()
    schedule, _ = build_schedule(tasks)
    for task in tasks:
        grid = [row for row in schedule if row["task_id"] == task["task_id"]]
        assert {row["condition"] for row in grid} == set(CONDITIONS)
        assert len({row["prior_payload_sha256"] for row in grid}) == 4
    for row in schedule:
        body = row["canonical_request_body"]
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        assert "max_tokens" not in body
        assert contains_forbidden_gold_key(body) is False


def test_v24_written_artifact_matches_when_present() -> None:
    if not ARTIFACT.exists():
        return
    result = validate()
    manifest = load(ARTIFACT / "run_manifest.json")
    assert manifest["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert manifest["documents"] == result["documents"]
    assert load(ARTIFACT / "task_selection_audit.json")["selected_prior_overlap"] == 0
