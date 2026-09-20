from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import (
    CONFIG,
    HardStop,
    load,
    schedule_rows,
    sha256_file,
    validate_authorization,
)
from scripts.audit_acl2027_phase2_calibration_v5 import validate_v5_authorization

AUTH_PATH = CONFIG.parents[2] / "configs/acl2027/phase2_calibration_live_authorization_v5.json"


def test_v5_authorization_is_exactly_calibration_only() -> None:
    config = load(CONFIG)
    auth = load(AUTH_PATH)
    validate_v5_authorization()
    validate_authorization(config, auth, sha256_file(AUTH_PATH), "calibration")
    assert auth["authorized_calls"] == auth["stage_call_ceiling"] == auth["max_provider_attempts"] == 60
    assert auth["stage_cost_ceiling_cny"] == auth["cumulative_cost_ceiling_cny"] == 0.5
    assert auth["model_id"] == "qwen3.7-plus" and auth["temperature"] == auth["retries"] == 0
    assert auth["max_tokens_present"] is False and auth["formal_scaling_allowed"] is False
    assert set(auth["forbidden_stages"]) == {"development_acquisition", "formal_history", "probe", "held_out", "formal_scaling"}


def test_calibration_schedule_is_exact_unique_prefix() -> None:
    rows = schedule_rows()
    calibration = [row for row in rows if row["partition"] == "calibration"]
    assert calibration == rows[:60]
    assert len(calibration) == len({row["logical_call_id"] for row in calibration}) == len({row["request_hash"] for row in calibration}) == 60
    assert {family: sum(row["skill_family"] == family for row in calibration) for family in {row["skill_family"] for row in calibration}} == {
        "fact_retrieval": 12,
        "attribute_comparison": 12,
        "bridge_attribute_comparison": 12,
        "entity_bridge": 12,
        "relation_inference": 12,
    }


@pytest.mark.parametrize("field,value", [
    ("authorized_stage", "formal_history"),
    ("authorized_calls", 61),
    ("stage_call_ceiling", 61),
    ("stage_cost_ceiling_cny", 0.51),
    ("cumulative_cost_ceiling_cny", 0.51),
    ("model_id", "qwen3.8-max"),
    ("temperature", 1),
    ("retries", 1),
    ("max_tokens_present", True),
    ("formal_scaling_allowed", True),
])
def test_authorization_boundary_drift_is_rejected(field, value) -> None:
    config = load(CONFIG)
    auth = deepcopy(load(AUTH_PATH))
    auth[field] = value
    if field == "cumulative_cost_ceiling_cny":
        auth["cumulative_cost_ceiling_cny"] = value
    with pytest.raises((HardStop, RuntimeError)):
        if field == "cumulative_cost_ceiling_cny":
            validate_v5_authorization(auth)
        else:
            validate_authorization(config, auth, "0" * 64, "calibration")
