from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg7_progress_memory_preflight_v1 import (
    CONFIG,
    FAMILIES,
    validate_config,
)


def test_tg7_config_is_closed_and_balanced():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["development_task_count"] == 24
    assert config["planned_episode_rows"] == 72
    assert config["split_counts"] == {"valid_seen": 12, "valid_unseen": 12}
    assert tuple(config["families"]) == FAMILIES
    assert [item["id"] for item in config["conditions"]] == [
        "baseline_first_eligible",
        "task_anchor_aware",
        "progress_memory",
    ]
    assert config["execution_authorized"] is False
    assert config["fresh_exact_user_authorization_required"] is True


def test_tg7_preflight_artifact_is_fresh_and_non_authorizing():
    root = Path(__file__).resolve().parents[1]
    schedule_path = root / "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/development_schedule.json"
    preflight_path = root / "artifacts/acl2027_tracegraph_tg7_progress_memory_preflight_v1/preflight.json"
    assert schedule_path.is_file()
    assert preflight_path.is_file()
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    assert len(schedule["tasks"]) == 24
    assert len({row["task_identity"] for row in schedule["tasks"]}) == 24
    assert preflight["status"] == "complete"
    assert preflight["planned_episode_rows"] == 72
    assert preflight["execution_authorized"] is False
    assert preflight["no_overlap_audit"]["selected_task_identity_overlap"] == 0
    assert preflight["split_counts"] == {"valid_seen": 12, "valid_unseen": 12}
    assert preflight["family_counts"] == {
        "pick_and_place_simple": 8,
        "pick_two_obj_and_place": 8,
        "pick_clean_then_place_in_recep": 8,
    }
