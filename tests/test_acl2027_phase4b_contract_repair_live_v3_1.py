import json

from scripts import audit_acl2027_phase4b_contract_repair_live_v3_1 as audit


def test_terminal_audit_preserves_exact_prefix_and_orphan():
    result = audit.analyze()
    assert result["status"] == "terminal_closed_incomplete"
    assert result["decision"] == "no_gate_incomplete_terminal_prefix"
    assert result["request_starts"] == 73
    assert result["completed_responses"] == 72
    assert result["orphan_request_starts"] == 1
    assert result["unattempted_rows"] == 27
    assert result["prefix_integrity"]["completed_response_prefix_hash_chain_valid"] is True
    assert result["prefix_integrity"]["orphan_start_hash_chain_valid"] is True
    assert result["prefix_integrity"]["request_start_pacing_valid"] is True
    assert result["prefix_integrity"]["retries"] == 0
    assert result["authorization_provenance"]["receipt_hash_matches_preflight_statement"] is False


def test_terminal_audit_keeps_all_later_permissions_closed():
    result = audit.analyze()
    assert result["authorization_closed"] is True
    assert result["retry_or_resume_authorized"] is False
    assert result["phase4c_authorized"] is False
    assert result["replication_authorized"] is False
    assert result["cross_domain_scaling_authorized"] is False
    assert result["formal_scaling_authorized"] is False
    assert result["partial_non_gating_contract_diagnostic"]["cannot_trigger_frozen_gate"] is True


def test_terminal_written_outputs_match_analysis():
    result = audit.analyze()
    written = json.loads((audit.RUN / "terminal_audit_v3_1.json").read_text(encoding="utf-8"))
    completion = json.loads((audit.RUN / "completion_manifest.json").read_text(encoding="utf-8"))
    assert written == result
    assert completion["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert completion["planned_calls"] == 100
    assert completion["completed_calls"] == completion["rows"] == 72
    assert completion["provider_calls_executed"] == 73
    assert completion["orphan_request_starts"] == 1
