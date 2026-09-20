from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_preflight_v1 import (
    CONFIG,
    CONDITIONS,
    FAMILIES,
    validate_config,
)


def test_tg8_config_is_closed_and_factorial():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["development_task_count"] == 24
    assert config["planned_episode_rows"] == 96
    assert tuple(config["families"]) == FAMILIES
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS
    assert config["execution_authorized"] is False
    assert config["fresh_exact_user_authorization_required"] is True


def test_tg8_preflight_artifact_is_non_authorizing():
    root = Path(__file__).resolve().parents[1]
    preflight = json.loads((root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v1/preflight.json").read_text(encoding="utf-8"))
    schedule = json.loads((root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v1/development_schedule.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v1/completion_manifest.json").read_text(encoding="utf-8"))
    assert len(schedule["tasks"]) == 24
    assert len({row["task_identity"] for row in schedule["tasks"]}) == 24
    assert preflight["status"] == "complete"
    assert preflight["planned_episode_rows"] == 96
    assert preflight["execution_authorized"] is False
    assert preflight["no_overlap_audit"]["selected_task_identity_overlap"] == 0
    assert preflight["split_counts"] == {"valid_seen": 12, "valid_unseen": 12}
    assert preflight["family_counts"] == {family: 8 for family in FAMILIES}
    assert manifest["completed_calls"] == 96
    assert manifest["episodes_run"] == 0
