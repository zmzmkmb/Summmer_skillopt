from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_acl2027_phase2_probe_only_preflight_v14 import HardStop, SCHEDULE, validate


def test_v14_closed_preflight_is_zero_network_and_exact_probe_plan() -> None:
    result = validate()
    assert result["status"] == "preflight-passed-closed"
    assert result["probe_calls"] == 160
    assert result["coverage_status"] == "coverage-passed"
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0


def test_v14_schedule_has_frozen_probe_prefix() -> None:
    rows = json.loads(SCHEDULE.read_text(encoding="utf-8"))["schedule"]
    probe = [row for row in rows if row["partition"] == "probe"]
    assert len(probe) == 160
    assert [row["staged_execution_index"] for row in probe] == list(range(231, 391))
    assert len({row["logical_call_id"] for row in probe}) == 160
    assert len({row["request_hash"] for row in probe}) == 160


def test_v14_rejects_missing_candidate() -> None:
    from scripts import run_acl2027_phase2_probe_only_preflight_v14 as module
    old = module.CANDIDATE
    module.CANDIDATE = Path("missing-v14-candidate.json")
    try:
        with pytest.raises((FileNotFoundError, HardStop)):
            validate()
    finally:
        module.CANDIDATE = old
