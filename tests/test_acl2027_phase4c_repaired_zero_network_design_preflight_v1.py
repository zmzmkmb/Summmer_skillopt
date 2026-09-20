from scripts import run_acl2027_phase4c_repaired_zero_network_design_preflight_v1 as design


def test_repaired_phase4c_design_is_closed_and_balanced() -> None:
    result = design.validate()
    assert result["rows"] == 400
    assert result["heldout_tasks"] == 80
    assert result["condition_counts"] == {condition: 80 for condition in sorted(design.CONDITIONS)}
    assert result["phase4c_live_authorized"] is False
    assert result["network_calls"] == result["provider_calls"] == 0


def test_repaired_phase4c_design_exposes_contract_ids_and_distinct_payloads() -> None:
    result = design.validate()
    assert result["contract_visible_rows"] == 400
    assert result["evidence_ids_visible_rows"] == 400
    assert result["unique_transport_payloads"] == 400
    assert result["duplicate_transport_pairs"] == 0
    assert result["identity_overlap"] == {"logical_call_ids": 0, "request_hashes": 0}
