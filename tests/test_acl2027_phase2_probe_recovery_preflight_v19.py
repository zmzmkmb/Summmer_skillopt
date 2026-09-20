from __future__ import annotations

from scripts import run_acl2027_phase2_probe_recovery_preflight_v19 as recovery


def test_v19_inputs_are_closed_and_zero_network() -> None:
    result = recovery.validate()
    assert result["status"] == "preflight-passed-recovery-plan"
    assert result["execution"] == {
        "network_calls_allowed": False,
        "provider_calls_allowed": False,
        "paid_api_allowed": False,
        "qwen_authorization_open": False,
        "formal_scaling_allowed": False,
    }
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0
    assert result["authorization_request_status"] == "fresh_explicit_authorization_required"


def test_v19_preserves_provenance_and_excludes_spent_grid() -> None:
    result = recovery.validate()
    provenance = result["v18_provenance"]
    assert provenance["v18_rows"] == 50
    assert provenance["v18_completed_rows"] == 49
    assert provenance["v18_terminal_rows"] == 1
    assert provenance["reusable_completed_rows"] == 48
    assert provenance["orphan_completed_rows"] == 1
    assert provenance["carry_forward_rows"] == 108
    assert len(provenance["excluded_task_ids"]) == 1
    assert result["spent_v18_requests_excluded"] == 50


def test_v19_recovery_is_a_balanced_new_request_plan() -> None:
    result = recovery.validate()
    assert result["recovery_calls"] == 112
    assert result["recovery_condition_counts"] == {condition: 28 for condition in recovery.CONDITIONS}
    assert result["combined_analysis_rows"] == 160
    assert result["combined_task_count"] == 40
    assert result["combined_condition_counts"] == {condition: 40 for condition in recovery.CONDITIONS}
    assert result["all_recovery_logical_ids_new"] is True
    assert result["all_recovery_request_hashes_new"] is True


def test_v19_replacement_is_attribute_comparison_and_fresh() -> None:
    result = recovery.validate()
    replacement = result["replacement_selection"]
    assert replacement["replacement_not_in_any_prior_or_v17_probe"] is True
    assert replacement["candidate_pool_size"] > 0
    assert len(replacement["replacement_task_id"]) > 0


def test_v19_proposed_boundary_does_not_open_authorization() -> None:
    result = recovery.validate()
    proposed = result["proposed_authorization"]
    assert proposed["requested_calls"] == proposed["max_provider_attempts"] == 112
    assert proposed["model_id"] == "qwen3.7-plus"
    assert proposed["temperature"] == 0
    assert proposed["retries"] == 0
    assert proposed["max_tokens_present"] is False
    assert proposed["held_out_authorized"] is False
    assert proposed["later_stages_authorized"] is False
    assert proposed["formal_scaling_authorized"] is False
    assert proposed["status"] == "fresh_explicit_authorization_required"
