from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.materialize_acl2027_phase2_candidates_recovery_v13 import (
    RecoveryMaterializationV13Error,
    build_recovery_candidate_artifact,
    load,
)
from scripts.run_acl2027_phase2_formal_history_recovery_preflight_v13 import (
    CONFIG,
    COMBINED_SCHEDULE,
    ROOT,
    V11_LEDGER,
    V12_LEDGER,
    execute,
    validate_inputs,
)


def _inputs():
    config = load(CONFIG)
    preserved = [row for row in load(V11_LEDGER) if row.get("status") == "completed"]
    recovery = load(V12_LEDGER)
    schedule = load(COMBINED_SCHEDULE)["schedule"]
    return config, preserved, recovery, schedule


def test_v13_binds_closed_v12_and_has_no_network() -> None:
    result = validate_inputs()
    assert result["status"] == "inputs-bound-zero-network"
    assert result["counters"] == {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0}


def test_v13_replay_passes_and_allows_duplicate_answer_hashes() -> None:
    config, preserved, recovery, schedule = _inputs()
    artifact = build_recovery_candidate_artifact(preserved, recovery, schedule, config, root=ROOT)
    assert artifact["passed"] is True
    assert artifact["history_rows"] == 160
    assert artifact["duplicate_logical_requests"] == 0
    assert artifact["duplicate_provider_response_ids"] == 0
    assert len(artifact["duplicate_answer_hash_groups"]) == 4


def test_v13_rejects_duplicate_provider_response_id() -> None:
    config, preserved, recovery, schedule = _inputs()
    tampered = copy.deepcopy(recovery)
    tampered[1]["raw_provider_response"] = copy.deepcopy(tampered[0]["raw_provider_response"])
    with pytest.raises(RecoveryMaterializationV13Error, match="duplicate provider response identity"):
        build_recovery_candidate_artifact(preserved, tampered, schedule, config, root=ROOT)


def test_v13_execute_manifest_is_zero_network() -> None:
    manifest = execute()
    assert manifest["status"] == "preflight-passed-correction"
    assert manifest["counters"] == {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0}
    assert manifest["candidate"]["passed"] is True
