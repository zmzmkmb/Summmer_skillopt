"""Tests for persistent ACL 2027 cross-conversation experiment handoff."""
from __future__ import annotations

import copy

from scripts.acl2027_experiment_handoff import (
    DEFAULT_STATE,
    PROJECT_ROOT,
    format_handoff,
    format_status,
    load_state,
    validate_state,
)


def test_current_repository_state_validates():
    state = load_state(DEFAULT_STATE)
    assert validate_state(state, PROJECT_ROOT) == []


def test_status_contains_current_phase():
    state = load_state(DEFAULT_STATE)
    status = format_status(state)
    phase = state["current_phase"]
    assert f"Current phase: {phase['id']} - {phase['title']} [{phase['status']}]" in status
    paid = str(state["execution_policy"]["paid_api_allowed"]).lower()
    assert f"Paid API allowed: {paid}" in status


def test_handoff_contains_current_first_action():
    state = load_state(DEFAULT_STATE)
    handoff = format_handoff(state)
    assert state["current_phase"]["next_actions"][0] in handoff
    assert "validate" in handoff
    assert "repository state, not chat memory" in handoff


def test_bad_completed_phase_fingerprint_fails_validation():
    state = copy.deepcopy(load_state(DEFAULT_STATE))
    state["completed_phases"][0]["aggregate_fingerprint"] = "0" * 64
    errors = validate_state(state, PROJECT_ROOT)
    assert any("aggregate fingerprint mismatch" in error for error in errors)


def test_bad_call_manifest_phase_fingerprint_fails_validation():
    state = copy.deepcopy(load_state(DEFAULT_STATE))
    phase = next(item for item in state["completed_phases"] if item["id"] == "1S")
    phase["aggregate_fingerprint"] = "0" * 64
    errors = validate_state(state, PROJECT_ROOT)
    assert any(
        "completed phase 1S aggregate fingerprint mismatch" in error
        for error in errors
    )


def test_bad_aggregate_completion_count_fails_validation():
    state = copy.deepcopy(load_state(DEFAULT_STATE))
    phase = next(item for item in state["completed_phases"] if item["id"] == "2")
    phase["expected_runs"] += 1
    errors = validate_state(state, PROJECT_ROOT)
    assert any(
        "completed phase 2 completed_calls mismatch" in error
        for error in errors
    )


def test_invalid_current_phase_status_fails_validation():
    state = copy.deepcopy(load_state(DEFAULT_STATE))
    state["current_phase"]["status"] = "running-ish"
    errors = validate_state(state, PROJECT_ROOT)
    assert any("current_phase.status must be one of" in error for error in errors)


def test_tracegraph_current_state_has_auditable_isolation():
    state = load_state(DEFAULT_STATE)
    assert state["active_research_line"]["id"] == "tracegraph-observable-state-skill-composition"
    assert state["current_phase"]["id"] == "TG8-tracegraph-observable-subgoal-selector-audit-v3"
    assert state["current_phase"]["title"] == "TraceGraph TG8 observable-subgoal selector v3 audit"
    durable_execution = state["current_phase"].get("durable_execution")
    if durable_execution:
        assert durable_execution["authorization_reusable"] is False
        assert durable_execution["planned_rows"] == 360
        assert durable_execution["max_retries"] == 0
        assert durable_execution["config_binding_sha256"] == (
            "a5617a8c1ed4d4671ebddfaedeedce0415cc60f7c1e7876c68b87909fc14d2b8"
        )
        if durable_execution["status"] in {"authorized_launch_pending", "running"}:
            assert state["current_phase"]["status"] == "in_progress"
    else:
        assert state["current_phase"]["status"] == "blocked"
    assert state["last_completed_phase"] == "TG8-tracegraph-observable-subgoal-preflight-v1"
    assert state["current_phase"]["research_line"] == state["active_research_line"]["id"]
    assert state["tracegraph"]["primary_environment"] == "ALFWorld"
    assert state["tracegraph"]["runtime_allowed_inputs"] == [
        "observation",
        "historical_actions",
        "admissible_actions",
    ]
    assert "TraceGraph data source" in state["tracegraph"]["phase0_to_phase6"]["forbidden_uses"]
    assert state["tracegraph"]["current_stage"] == "TG8"
    assert state["tracegraph"]["tg1_preflight"]["status"] == "zero-network-preflight-planned"
    assert state["tracegraph"]["tg1_preflight"]["source_audit_script"] == "scripts/audit_acl2027_tracegraph_tg1_alfworld_source_v1.py"
    assert state["tracegraph"]["tg6_execution"]["status"] == "blocked_local_environment_integrity"
    assert state["tracegraph"]["tg6_execution"]["retry_or_resume_forbidden"] is True
    assert state["tracegraph"]["tg6_derived_repair"]["status"] == "completed_zero_network_preflight"
    assert state["tracegraph"]["tg6_derived_repair"]["planner_status_counts"] == {"passed": 40}
    assert state["tracegraph"]["tg6_derived_repair"]["repaired_task_count"] == 8
    assert state["tracegraph"]["tg6_repaired_execution"]["status"] == "completed_zero_network_execution"
    assert state["tracegraph"]["tg6_repaired_execution"]["episodes_started"] == 40
    assert state["tracegraph"]["tg6_repaired_execution"]["episodes_completed"] == 40
    assert state["tracegraph"]["tg6_repaired_execution"]["successes"] == 0
    assert state["tracegraph"]["tg7_execution"]["episodes_started"] == 72
    assert state["tracegraph"]["tg7_execution"]["episodes_completed"] == 72
    assert state["tracegraph"]["tg7_execution"]["successes"] == 0
    assert state["tracegraph"]["tg7_execution"]["decision"] == "representation-limited"
    assert state["current_phase"]["planned_episode_rows"] == 360
    assert state["current_phase"]["preflight"] == (
        "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v4/preflight.json"
    )
    assert state["current_phase"]["selector"] == (
        "scripts/run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3.py"
    )
    assert state["current_phase"]["selector_audit"] == (
        "artifacts/acl2027_tracegraph_tg8_observable_subgoal_selector_audit_v3/selector_audit.json"
    )
    if not durable_execution:
        assert state["current_phase"]["runner_status"] == (
            "durable_v2_offline_verified_execution_closed"
        )
    assert state["current_phase"]["readiness_status"] == "passed"
    assert state["current_phase"]["readiness_task_count"] == 30
    assert state["current_phase"]["readiness_passed_task_count"] == 30
    assert state["current_phase"]["readiness_selector_probe_count"] == 120
    assert state["current_phase"]["readiness_episodes_run"] == 0
    assert state["current_phase"]["readiness_actions_taken"] == 0
    assert state["current_phase"]["readiness_sha256"] == (
        "85627fd938abce62e254a68957893f81b1389cc0a7e6519976d338a15ed3904b"
    )
    assert state["current_phase"]["readiness_allowed"] is False
    assert state["current_phase"]["execution_authorized"] is bool(
        durable_execution and durable_execution["status"] in {"authorized_launch_pending", "running"}
    )
    assert state["current_phase"]["execution_attempt"]["completed_rows"] is None
    assert state["current_phase"]["execution_attempt"]["authorization_reusable"] is False
    assert state["current_phase"]["durability_repair"]["formal_episodes_run"] == 0
    assert "tracegraph_tg8_observable_subgoal_readiness_v1_ubuntu_wsl.py" in " ".join(
        state["current_phase"]["expected_write_scope"]
    )


def test_tracegraph_contamination_boundary_fails_validation_when_relaxed():
    state = copy.deepcopy(load_state(DEFAULT_STATE))
    state["tracegraph"]["phase0_to_phase6"]["status"] = "reusable"
    errors = validate_state(state, PROJECT_ROOT)
    assert "tracegraph.phase0_to_phase6 must be frozen-read-only" in errors
