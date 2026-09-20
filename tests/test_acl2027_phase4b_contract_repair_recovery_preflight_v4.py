import json

from scripts import run_acl2027_phase4b_contract_repair_recovery_preflight_v4 as recovery


def test_phase4b_r4_is_closed_zero_network_and_binds_sources() -> None:
    result, request, _, _ = recovery.validate()
    assert result["status"] == "zero-network-recovery-preflight-passed-closed"
    assert result["source_fingerprints"] == {
        "phase4b_r1_repair": recovery.R1_FINGERPRINT,
        "phase4b_r2_live_preflight": recovery.R2_FINGERPRINT,
        "phase4b_r3_terminal_audit": recovery.R3_FINGERPRINT,
    }
    assert all(value is False for value in result["execution"].values())
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == 0
    assert result["paid_api_calls"] == result["phase4c_calls"] == 0
    assert request["fresh_live_execution_preflight_required"] is True


def test_phase4b_r4_excludes_all_spent_identities_and_freezes_28_new_rows() -> None:
    result, _, schedule, _ = recovery.validate()
    assert result["r3_provenance"]["request_starts"] == 73
    assert result["r3_provenance"]["completed_responses"] == 72
    assert result["r3_provenance"]["orphan_request_starts"] == 1
    assert result["r3_provenance"]["reusable_contract_valid_rows"] == 72
    assert result["r3_provenance"]["reusable_evidence_resolving_rows"] == 72
    assert len(schedule) == result["recovery_rows"] == 28
    assert result["new_logical_call_ids"] == result["new_request_hashes"] == 28
    assert result["spent_identity_overlap"] == {"logical_call_ids": 0, "request_hashes": 0}


def test_phase4b_r4_discloses_exactly_one_spent_transport_repeat() -> None:
    result, request, schedule, _ = recovery.validate()
    assert result["transport_payloads_preserved"] == 28
    assert result["deliberate_spent_transport_repeats"] == 1
    replacement = [row for row in schedule if row["recovery_kind"] == "orphan_transport_replacement"]
    assert len(replacement) == 1 and replacement[0]["source_sequence"] == 73
    disclosure = request["orphan_transport_repeat_disclosure"]
    assert disclosure["same_provider_visible_content_as_spent_orphan"] is True
    assert disclosure["same_logical_or_request_identity"] is False


def test_phase4b_r4_restores_balanced_grid_but_preserves_nonidentifiability() -> None:
    result, request, _, combined = recovery.validate()
    assert len(combined) == result["combined_analysis_rows"] == 100
    assert result["combined_task_count"] == 20
    assert result["combined_condition_counts"] == {condition: 20 for condition in sorted(recovery.repair.CONDITIONS)}
    assert result["combined_unique_transport_payloads"] == 80
    assert result["combined_duplicate_transport_pairs"] == 20
    assert result["global_only_contextual_typed_causal_comparison_identifiable"] is False
    assert request["known_transport_equivalence"]["causal_comparison_identifiable"] is False


def test_phase4b_r4_keeps_cost_and_authorization_unresolved() -> None:
    _, request, _, _ = recovery.validate()
    assert request["requested_calls"] == request["max_provider_attempts"] == 28
    assert request["cost_treatment_status"] == "unresolved_due_to_unknown_orphan_usage"
    assert request["stage_cost_ceiling_cny"] is None
    assert request["cumulative_cost_ceiling_cny"] is None
    assert request["provider_calls"] == request["paid_api_calls"] == 0


def test_phase4b_r4_written_artifact_matches_validation() -> None:
    result, request, schedule, combined = recovery.validate()
    manifest = json.loads((recovery.ARTIFACT / "run_manifest.json").read_text(encoding="utf-8"))
    written_request = json.loads((recovery.ARTIFACT / "authorization_request.json").read_text(encoding="utf-8"))
    written_schedule = json.loads((recovery.ARTIFACT / "recovery_schedule.json").read_text(encoding="utf-8"))["rows"]
    written_combined = json.loads((recovery.ARTIFACT / "combined_analysis_plan.json").read_text(encoding="utf-8"))["rows"]
    completion = json.loads((recovery.ARTIFACT / "completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result
    assert written_request == request
    assert written_schedule == schedule
    assert written_combined == combined
    assert completion["proposed_calls"] == completion["completed_calls"] == completion["rows"] == 28
    assert completion["combined_analysis_rows"] == 100
    assert completion["provider_calls_executed"] == 0
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
