import json

from scripts import run_acl2027_phase4b_contract_repair_preflight_v1 as phase


def test_contract_repair_preflight_is_closed_and_disjoint():
    result = phase.validate()
    assert result["status"] == "zero-network-contract-repair-preflight-passed-closed"
    assert result["task_count"] == 20
    assert result["proposal_rows"] == 100
    assert not any(result["identity_overlap_audit"].values())
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0
    assert result["authorization_status"] == "not-authorized"


def test_repaired_contract_survives_transport_projection():
    tasks, _ = phase.select_tasks()
    rows = phase.build_schedule(tasks)
    assert len(rows) == 100
    for row in rows:
        projection = row["transport_projection"]
        system = projection["messages"][0]["content"]
        user = json.loads(projection["messages"][1]["content"])
        assert all(key in system for key in phase.EXACT_KEYS)
        assert user["response_contract"]["exact_keys"] == list(phase.EXACT_KEYS)
        assert all(sentence["id"] for block in user["context"] for sentence in block["sentences"])
        assert set(projection) == {"model", "messages", "temperature", "enable_thinking", "response_format"}


def test_original_failure_is_diagnosed_without_provider_claim():
    diagnostic = phase.diagnose_original()
    assert diagnostic["rows_whose_transmitted_system_message_omits_exact_keys"] == 100
    assert diagnostic["classification"] == "prompt_transport_contract_visibility_failure"
    assert diagnostic["provider_exact_http_or_internal_cause_claimed"] is False
