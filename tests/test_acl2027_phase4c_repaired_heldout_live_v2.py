from scripts import run_acl2027_phase4c_repaired_heldout_live_v2 as live


def test_phase4c_execution_preflight_binds_all_frozen_rows() -> None:
    rows = live.preflight()
    assert len(rows) == 400
    assert len({row["logical_call_id"] for row in rows}) == 400
    assert len({row["request_hash"] for row in rows}) == 400
    assert len({row["transport_payload_hash"] for row in rows}) == 400


def test_phase4c_receipt_binds_verbatim_authorization_and_scope() -> None:
    receipt = live.receipt()
    assert receipt["phase4c_design_fingerprint"] == live.DESIGN_FINGERPRINT
    assert receipt["phase4c_live_preflight_fingerprint"] == live.PREFLIGHT_FINGERPRINT
    assert receipt["authorized_calls"] == 400
    assert receipt["execution"]["qwen_authorization_open"] is False
    assert receipt["forbidden_stages"] == ["replication", "other_models", "cross_domain_scaling", "formal_scaling"]
