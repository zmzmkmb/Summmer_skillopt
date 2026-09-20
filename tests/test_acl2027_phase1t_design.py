from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_acl2027_phase1t_design import (
    CONFIG_PATH,
    apply_initial_transition,
    apply_recovery,
    audit,
    read_json,
    substrate_eligible,
    triage_decision,
    write_artifact,
)


def test_phase1t_design_passes_all_zero_network_checks() -> None:
    result = audit(read_json(CONFIG_PATH))
    assert result["decision"] == "design_frozen_execution_closed"
    assert all(result["checks"].values())
    assert result["network_calls"] == 0
    assert result["paid_api_calls"] == 0
    assert result["counterfactual_token_total"] == 1000


def test_phase1t_capability_gate_rejects_floor_and_concentration() -> None:
    config = read_json(CONFIG_PATH)
    gate = config["substrate_eligibility_gate"]
    valid = {
        "tasks": 12,
        "contract_valid_rate": 1.0,
        "baseline_accuracy": 0.5,
        "successes": 6,
        "successful_task_types": ["bridge", "comparison", "temporal"],
        "successes_by_task_id": {str(index): 1 for index in range(6)},
        "automatic_verifier": True,
        "reusable_skill_families": True,
    }
    assert substrate_eligible(valid, gate)
    floor = deepcopy(valid)
    floor["baseline_accuracy"] = 0.0
    assert not substrate_eligible(floor, gate)
    concentrated = deepcopy(valid)
    concentrated["successes_by_task_id"] = {"same": 6}
    assert not substrate_eligible(concentrated, gate)


@pytest.mark.parametrize(
    ("scenario_id", "expected"),
    [
        ("helpful_accept", "accept"),
        ("harmful_reject", "reject"),
        ("uncertain_abstain", "abstain"),
        ("invalid_abstain", "abstain"),
    ],
)
def test_phase1t_numerical_triage_is_identifiable(
    scenario_id: str,
    expected: str,
) -> None:
    config = read_json(CONFIG_PATH)
    scenario = next(
        item
        for item in config["identifiability_scenarios"]
        if item["id"] == scenario_id
    )
    result = triage_decision(
        scenario["candidate_exact"],
        scenario["fallback_exact"],
        scenario["contract_valid"],
        config["numerical_triage"],
    )
    assert result["decision"] == expected


def test_phase1t_retention_recovers_while_discard_cannot() -> None:
    config = read_json(CONFIG_PATH)
    policies = config["policy_state_transitions"]
    recovery = config["recovery_scenario"]
    retaining = policies["candidate_retaining_triage"]
    destructive = policies["destructive_gate"]
    retained_state = apply_initial_transition(retaining, "reject")
    discarded_state = apply_initial_transition(destructive, "reject")
    assert (
        apply_recovery(retained_state, recovery["later_windows"], retaining)
        == "candidate_recovered_active"
    )
    assert (
        apply_recovery(discarded_state, recovery["later_windows"], destructive)
        == "candidate_discarded"
    )


def test_phase1t_rejects_threshold_drift() -> None:
    config = deepcopy(read_json(CONFIG_PATH))
    config["substrate_eligibility_gate"]["contract_valid_rate_min"] = 0.8
    result = audit(config)
    assert not result["checks"]["eligibility_gate_exact"]
    assert result["decision"] == "design_failed_execution_closed"


def test_phase1t_refuses_artifact_overwrite(tmp_path) -> None:
    output = tmp_path / "immutable"
    output.mkdir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_artifact(read_json(CONFIG_PATH), output)
