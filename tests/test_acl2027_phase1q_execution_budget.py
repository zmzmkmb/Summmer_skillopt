from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_acl2027_phase1q_execution_budget import (
    CONFIG_PATH,
    _cold_or_execute,
    audit,
    build_call_matrix,
    read_json,
    write_artifact,
)


def test_phase1q_preflight_passes_without_network_or_paid_calls() -> None:
    result = audit(read_json(CONFIG_PATH))
    assert result["decision"] == "execution_plan_frozen_paid_execution_closed"
    assert all(result["checks"].values())
    assert result["eligibility_summary"]["audited"] == 48
    assert result["eligibility_summary"]["eligible"] == 48
    assert result["eligibility_summary"]["abstain"] == 0
    assert result["network_calls"] == 0
    assert result["paid_api_calls"] == 0
    assert result["provider_attempts"] == 0


def test_phase1q_exact_call_counts_charge_both_branches() -> None:
    matrix = {
        row["plan"]: row for row in build_call_matrix(read_json(CONFIG_PATH))
    }
    assert matrix["development_only"]["condition_accounted_calls"] == 192
    assert matrix["staged_confirmation"]["condition_accounted_calls"] == 384
    assert matrix["full_frozen_design"]["condition_accounted_calls"] == 960
    assert all(
        row["candidate_calls"] == row["fallback_calls"]
        for row in matrix.values()
    )
    assert all(
        row["physical_request_ceiling"] == row["condition_accounted_calls"]
        for row in matrix.values()
    )


def test_phase1q_unsupported_identity_abstains() -> None:
    assert _cold_or_execute(False, "execute_candidate_and_fallback") == "abstain"
    assert (
        _cold_or_execute(True, "execute_candidate_and_fallback")
        == "execute_candidate_and_fallback"
    )


def test_phase1q_rejects_incomplete_candidate_binding_matrix() -> None:
    config = deepcopy(read_json(CONFIG_PATH))
    config["candidate_provenance"]["condition_bindings"].pop()
    result = audit(config)
    assert not result["checks"][
        "candidate_bindings_cover_all_prior_gate_pairs"
    ]
    assert result["decision"] == "execution_preflight_failed_paid_execution_closed"


def test_phase1q_rejects_non_prefix_staged_confirmation() -> None:
    config = deepcopy(read_json(CONFIG_PATH))
    config["call_accounting"]["plans"]["staged_confirmation"][
        "held_out_prefix_ids"
    ]["OfficeQA"][0] = "UID0240"
    result = audit(config)
    assert not result["checks"]["staged_prefix_is_first_four_stream_tasks"]
    assert result["decision"] == "execution_preflight_failed_paid_execution_closed"


def test_phase1q_refuses_artifact_overwrite(tmp_path) -> None:
    output = tmp_path / "immutable"
    output.mkdir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_artifact(read_json(CONFIG_PATH), output)
