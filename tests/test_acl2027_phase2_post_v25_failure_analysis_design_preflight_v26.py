from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import (
    ARTIFACT,
    CONDITIONS,
    FAMILIES,
    TASKS_PER_FAMILY,
    build_future_schedule,
    contains_forbidden_gold_key,
    failure_analysis,
    identity_audit,
    load,
    select_future_tasks,
    validate,
)


def test_v26_is_closed_zero_network_design_only() -> None:
    result = validate()
    assert result["status"] == "design-preflight-passed-closed"
    assert result["authorization_status"] == "not-authorized"
    assert result["authorization_artifact_created"] is False
    assert result["network_calls"] == result["provider_calls"] == 0
    assert result["model_calls"] == result["paid_api_calls"] == result["formal_scaling_calls"] == 0
    assert result["v23_gate_preserved"] == "inconclusive"
    assert result["v25_gate_preserved"] == "negative"


def test_v26_failure_analysis_preserves_old_gates_and_surfaces_alias_sensitivity() -> None:
    analysis = failure_analysis()
    assert analysis["historical_gates_preserved"] == {"v23": "inconclusive", "v25": "negative"}
    assert analysis["combined_strict_pair_outcomes"] == {
        "both_correct": 113,
        "both_wrong": 38,
        "typed_loss": 3,
        "typed_win": 6,
    }
    assert analysis["diagnostic_conclusions"]["verifier_alias_sensitivity"]["discordant_tasks_changed_by_alias_rule"] >= 1
    assert analysis["diagnostic_conclusions"]["typed_coverage"]["coverage_status"] == "coverage-passed"


def test_v26_freezes_independent_balanced_future_grid() -> None:
    tasks, selection = select_future_tasks()
    schedule, private_gold = build_future_schedule(tasks)
    assert len(tasks) == len(private_gold) == 400
    assert len({task["task_id"] for task in tasks}) == 400
    assert selection["prior_task_overlap"] == 0
    assert {family: sum(task["skill_family"] == family for task in tasks) for family in FAMILIES} == {
        family: TASKS_PER_FAMILY for family in FAMILIES
    }
    assert len(schedule) == 1600
    assert {condition: sum(row["condition"] == condition for row in schedule) for condition in CONDITIONS} == {
        condition: 400 for condition in CONDITIONS
    }
    assert len({row["logical_call_id"] for row in schedule}) == 1600
    assert len({row["request_hash"] for row in schedule}) == 1600
    assert all(row["provider_response_id"] is None for row in schedule)


def test_v26_future_requests_have_distinct_semantics_no_gold_and_no_overlap() -> None:
    tasks, selection = select_future_tasks()
    schedule, _ = build_future_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    assert identities["prior_evaluation_task_overlap"] == 0
    assert identities["logical_call_id_overlap"] == 0
    assert identities["request_hash_overlap"] == 0
    assert identities["provider_response_id_overlap"] == 0
    for task in tasks:
        grid = [row for row in schedule if row["task_id"] == task["task_id"]]
        assert {row["condition"] for row in grid} == set(CONDITIONS)
        assert len({row["prior_payload_sha256"] for row in grid}) == 4
    assert all(contains_forbidden_gold_key(row["canonical_request_body"]) is False for row in schedule)


def test_v26_written_artifact_matches_when_present() -> None:
    if not ARTIFACT.exists():
        return
    result = validate()
    manifest = load(ARTIFACT / "run_manifest.json")
    assert manifest["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert manifest["documents"] == result["documents"]
    assert load(ARTIFACT / "identity_overlap_audit.json")["request_hash_overlap"] == 0
