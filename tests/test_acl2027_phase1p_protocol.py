from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_acl2027_phase1p_protocol import (
    CONFIG_PATH,
    audit,
    read_json,
    write_artifact,
)


def test_phase1p_protocol_passes_all_zero_network_checks() -> None:
    result = audit(read_json(CONFIG_PATH))
    assert result["decision"] == "protocol_frozen_future_execution_closed"
    assert all(result["checks"].values())
    assert result["network_calls"] == 0
    assert result["paid_api_calls"] == 0
    assert result["design"]["expected_cells"] == 24


def test_phase1p_rejects_held_out_overlap() -> None:
    config = deepcopy(read_json(CONFIG_PATH))
    config["task_streams"]["OfficeQA"]["held_out_ids"][0] = "UID0001"
    result = audit(config)
    assert not result["checks"]["officeqa_stream_valid"]
    assert result["decision"] == "protocol_failed_execution_closed"


def test_phase1p_requires_candidate_retention() -> None:
    config = deepcopy(read_json(CONFIG_PATH))
    config["gate_policies"]["candidate_retaining_triage"][
        "candidate_state_mutated_on_abstain"
    ] = True
    result = audit(config)
    assert not result["checks"]["triage_retains_rejected_and_abstained"]
    assert result["decision"] == "protocol_failed_execution_closed"


def test_phase1p_refuses_artifact_overwrite(tmp_path) -> None:
    output = tmp_path / "immutable"
    output.mkdir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_artifact(read_json(CONFIG_PATH), output)
