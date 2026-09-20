from __future__ import annotations

import json

import pytest

from scripts.acl2027_phase2_response_verifier_v3 import stable
from scripts.materialize_acl2027_phase2_candidates_recovery_v12 import RecoveryMaterializationError, build_recovery_candidate_artifact
from scripts.run_acl2027_phase2_formal_history_recovery_preflight_v12 import (
    COMBINED_SCHEDULE,
    CONFIG,
    FAMILIES,
    RECOVERY_SCHEDULE,
    ROOT,
    V11_LEDGER,
    load,
    validate,
)


def test_v12_preflight_is_closed_and_exact() -> None:
    manifest = validate()
    config = load(CONFIG)
    recovery = load(RECOVERY_SCHEDULE)["schedule"]
    combined = load(COMBINED_SCHEDULE)["schedule"]
    assert manifest["request_count"] == len(recovery) == 128
    assert len(combined) == 160
    assert config["recovery_contract"]["preserved_v11_completed_rows"] == 32
    assert config["recovery_contract"]["terminal_request_must_not_be_retried"] is True
    assert config["recovery_contract"]["terminal_spent_task_id"] not in {row["task_id"] for row in recovery}
    assert all(value is False for value in config["execution"].values())
    assert all("max_tokens" not in row["canonical_request_body"] for row in recovery)
    assert {family: sum(row["skill_family"] == family for row in combined) for family in FAMILIES} == {family: 32 for family in FAMILIES}
    assert len({row["logical_call_id"] for row in combined}) == len({row["task_id"] for row in combined}) == 160


def test_v12_mock_combined_materialization_passes() -> None:
    config = load(CONFIG)
    combined = load(COMBINED_SCHEDULE)["schedule"]
    gold = {row["task_id"]: row for row in load(ROOT / config["trusted_evaluation"]["combined_gold_path"])}
    preserved = [row for row in load(V11_LEDGER) if row.get("status") == "completed"]
    recovery = []
    for index, planned in enumerate(combined[32:], 1):
        answer = (gold[planned["task_id"]].get("answers") or [gold[planned["task_id"]].get("answer")])[0]
        raw = " " * index + json.dumps({"answer": answer})
        recovery.append({**{key: planned[key] for key in ("logical_call_id", "request_hash", "task_id", "skill_family", "payload_hash")}, "partition": "formal_history", "raw_response": raw, "raw_response_sha256": stable(raw), "terminal": False})
    artifact = build_recovery_candidate_artifact(preserved, recovery, combined, config, root=ROOT)
    assert artifact["history_rows"] == 160
    assert artifact["passed"] is True
    assert artifact["independent_verified_supports"]["fact_retrieval"] == 28
    assert all(artifact["independent_verified_supports"][family] == 32 for family in FAMILIES[1:])


def test_v12_rejects_terminal_retry_and_partial_materialization() -> None:
    config = load(CONFIG)
    combined = load(COMBINED_SCHEDULE)["schedule"]
    terminal_task = config["recovery_contract"]["terminal_spent_task_id"]
    assert terminal_task not in {row["task_id"] for row in combined}
    with pytest.raises(RecoveryMaterializationError, match="32 preserved plus 128"):
        build_recovery_candidate_artifact([], [], combined, config, root=ROOT)
