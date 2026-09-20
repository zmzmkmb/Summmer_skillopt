from scripts import run_acl2027_phase4c_zero_network_design_diagnostic_v1 as diagnostic


def test_phase4c_diagnostic_is_closed_and_binds_sources() -> None:
    result = diagnostic.validate()
    assert result["status"] == "closed_design_blocked_repair_required"
    assert result["source_phase4a_fingerprint"] == diagnostic.PHASE4A_FINGERPRINT
    assert result["source_phase4b_r6_analysis_fingerprint"] == diagnostic.R6_FINGERPRINT
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0
    assert result["phase4c_authorized"] is False


def test_phase4c_diagnostic_finds_transport_and_visibility_blockers() -> None:
    result = diagnostic.validate()
    assert result["heldout_rows_audited"] == 400
    assert result["heldout_tasks_audited"] == 80
    assert result["unique_transport_payloads"] == 320
    assert result["global_only_contextual_typed_equivalent_pairs"] == 80
    assert result["contract_visible_in_transmitted_messages_rows"] == 0
    assert result["evidence_ids_visible_in_transmitted_messages_rows"] == 0
    assert result["required_repair"]["fresh_live_preflight_and_explicit_authorization_required"] is True
