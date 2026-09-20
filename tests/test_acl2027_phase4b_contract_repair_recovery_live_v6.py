import hashlib

from scripts import run_acl2027_phase4b_contract_repair_recovery_live_v6 as live


def test_r6_preflight_binds_exact_recovery_schedule_and_excludes_spent_ids() -> None:
    rows = live.preflight()
    assert len(rows) == 28
    assert len({row["logical_call_id"] for row in rows}) == 28
    assert len({row["request_hash"] for row in rows}) == 28


def test_r6_receipt_matches_verbatim_r5_statement_and_closed_defaults() -> None:
    receipt = live.receipt()
    statement = live.load(live.PREFLIGHT_REQUEST)["authorization_statement_verbatim"]
    assert receipt["authorization_statement_sha256"] == hashlib.sha256(statement.encode("utf-8")).hexdigest()
    assert receipt["source_recovery_fingerprint"] == live.R4_FINGERPRINT
    assert receipt["live_preflight_fingerprint"] == live.R5_FINGERPRINT
    assert all(value is False for value in receipt["execution"].values())


def test_r6_contract_has_exact_route_cost_and_stop_terms() -> None:
    contract = live.contract()
    assert contract["authorized_calls"] == contract["max_provider_attempts"] == 28
    assert contract["temperature"] == 0 and contract["enable_thinking"] is False
    assert contract["retries"] == 0 and contract["max_tokens_present"] is False
    assert contract["stage_cost_ceiling_cny"] == 0.30
    assert contract["cumulative_cost_ceiling_cny"] == 15.00
    assert contract["orphan_usage_reserve_cny"] == 0.011136
    assert contract["terminal_stop_on_first_failed_attempt"] is True
    assert contract["authorization_closes_on_completion_or_terminal_stop"] is True


def test_r6_cost_accounting_uses_conservative_prior() -> None:
    assert live.CONSERVATIVE_PRIOR == 12.340056
    assert round(live.CONSERVATIVE_PRIOR + live.STAGE_CEILING, 6) == 12.640056
