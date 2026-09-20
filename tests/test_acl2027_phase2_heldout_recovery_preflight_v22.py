from scripts import run_acl2027_phase2_heldout_recovery_preflight_v22 as recovery
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable


def test_v22_is_closed_and_zero_network() -> None:
    result = recovery.validate()
    assert result["status"] == "preflight-passed-recovery-plan"
    assert all(value is False for value in result["execution"].values())
    assert result["network_calls"] == result["provider_calls"] == result["model_calls"] == result["paid_api_calls"] == 0
    assert result["authorization_opened"] is False
    assert result["authorization_request_status"] == "fresh_explicit_authorization_required"


def test_v22_excludes_all_spent_v21_requests_and_orphan_row() -> None:
    result = recovery.validate()
    provenance = result["v21_provenance"]
    assert provenance["spent_rows"] == 234
    assert provenance["completed_rows"] == 233
    assert provenance["reusable_completed_rows"] == 232
    assert provenance["orphan_completed_rows"] == 1
    assert provenance["carry_forward_rows"] == 84
    assert provenance["authorization_closed"] is True
    assert result["spent_v21_requests_excluded"] == 234
    assert result["orphan_completed_row_reused"] is False


def test_v22_restores_balanced_80_by_4_grid_with_88_new_requests() -> None:
    result = recovery.validate()
    assert result["recovery_calls"] == 88
    assert result["recovery_condition_counts"] == {condition: 22 for condition in recovery.CONDITIONS}
    assert result["combined_analysis_rows"] == 320
    assert result["combined_task_count"] == 80
    assert result["combined_condition_counts"] == {condition: 80 for condition in recovery.CONDITIONS}
    assert result["all_recovery_logical_ids_new"] is True
    assert result["all_recovery_request_hashes_new"] is True


def test_v22_replacement_is_deterministic_fresh_entity_bridge() -> None:
    result = recovery.validate()
    replacement = result["replacement_selection"]
    assert replacement["replacement_task_id"] == "933d94640bd911eba7f7acde48001122"
    assert replacement["replacement_selector_hash"] == "0000a5ecd4d66adc79451ed003ef05024b8c0c72cb0cb0346736cb418d20a203"
    assert replacement["candidate_pool_size"] == 5058
    assert replacement["replacement_not_in_prior_or_prior_partitions_or_v17_v19_v21"] is True


def test_v22_route_is_frozen_but_future_authorization_is_not_open() -> None:
    result = recovery.validate()
    rows, _, _ = recovery.build_schedule(result["v21_provenance"], recovery.select_replacement())
    assert len(rows) == 88
    for row in rows:
        body = row["canonical_request_body"]
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert body["enable_thinking"] is False
        assert body["response_format"] == {"type": "json_object"}
        assert "max_tokens" not in body
        assert row["expected_accounting"]["retries"] == 0


def test_v22_artifact_and_authorization_request_are_bound_and_closed() -> None:
    manifest = recovery.load(recovery.ARTIFACT / "run_manifest.json")
    request = recovery.load(recovery.AUTH_REQUEST)
    assert manifest["aggregate_fingerprint"] == stable({key: value for key, value in manifest.items() if key != "aggregate_fingerprint"})
    for name, digest in manifest["documents"].items():
        assert sha256_file(recovery.ARTIFACT / name) == digest
    assert request["status"] == "awaiting_fresh_explicit_user_authorization"
    assert request["requested_calls"] == request["max_provider_attempts"] == 88
    assert request["cost_ceilings"]["stage_cost_ceiling_cny"] is None
    assert request["cost_ceilings"]["cumulative_cost_ceiling_cny"] is None
    assert all(value is False for value in request["execution"].values())
    assert request["user_authorization"]["held_out_recovery_authorized"] is False
    assert request["bindings"]["preflight_aggregate_fingerprint"] == manifest["aggregate_fingerprint"]
    assert request["bindings"]["preflight_config_sha256"] == sha256_file(recovery.CONFIG)
    assert request["bindings"]["preflight_manifest_sha256"] == sha256_file(recovery.ARTIFACT / "run_manifest.json")
    assert request["bindings"]["recovery_schedule_sha256"] == sha256_file(recovery.ARTIFACT / "held_out_recovery_schedule.json")
