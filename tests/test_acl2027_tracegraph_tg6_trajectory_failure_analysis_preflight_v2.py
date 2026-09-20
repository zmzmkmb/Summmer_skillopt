from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg6_trajectory_failure_analysis_preflight_v2 import (
    CONFIG,
    validate_config,
)


def test_v2_design_is_closed_and_stratified():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["development_task_count"] == 24
    assert config["development_split_counts"] == {"valid_seen": 12, "valid_unseen": 12}
    assert config["planned_episode_rows"] == 72
    assert config["runtime_allowed_inputs"] == [
        "observation",
        "historical_actions",
        "admissible_actions",
    ]
    assert config["execution_authorized"] is False
    assert config["fresh_exact_user_authorization_required"] is True
    assert len(config["conditions"]) == 3
    assert config["strata"][0]["split_counts"] == {
        "valid_seen": 2,
        "valid_unseen": 7,
    }


def test_v2_preflight_artifact_has_exact_strata():
    root = Path(__file__).resolve().parents[1]
    schedule_path = root / "artifacts/acl2027_tracegraph_tg6_trajectory_failure_analysis_preflight_v2/development_schedule.json"
    preflight_path = root / "artifacts/acl2027_tracegraph_tg6_trajectory_failure_analysis_preflight_v2/preflight.json"
    assert schedule_path.is_file()
    assert preflight_path.is_file()
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    assert len(schedule["tasks"]) == 24
    assert len({row["task_identity"] for row in schedule["tasks"]}) == 24
    assert preflight["status"] == "complete"
    assert preflight["completed_calls"] == 72
    assert preflight["rows"] == 72
    assert preflight["execution_authorized"] is False
    assert preflight["no_overlap_audit"]["heldout_task_identity_overlap"] == 0
    assert preflight["no_overlap_audit"]["parent_result_identity_overlap"] == 0
    assert preflight["stratum_counts"] == {
        "direct_cycle_replication": 9,
        "multi_step_transfer": 15,
    }
    assert preflight["family_counts"]["look_at_obj_in_light"] == 9
