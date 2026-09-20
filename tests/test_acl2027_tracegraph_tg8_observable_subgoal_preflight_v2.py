from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_preflight_v2 import (
    CONFIG,
    CONDITIONS,
    FAMILIES,
    validate_config,
)


def test_tg8_v2_config_is_closed_and_factorial():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["development_task_count"] == 36
    assert config["replicate_count"] == 3
    assert config["planned_episode_rows"] == 432
    assert tuple(config["families"]) == FAMILIES
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS
    assert config["execution_authorized"] is False


def test_tg8_v2_preflight_is_non_authorizing_and_disjoint():
    root = Path(__file__).resolve().parents[1]
    pre = json.loads((root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2/preflight.json").read_text(encoding="utf-8"))
    sched = json.loads((root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2/development_schedule.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v2/completion_manifest.json").read_text(encoding="utf-8"))
    assert len(sched["tasks"]) == 36
    assert len({row["task_identity"] for row in sched["tasks"]}) == 36
    assert pre["no_overlap_audit"]["selected_task_identity_overlap"] == 0
    assert pre["split_counts"] == {"valid_seen": 18, "valid_unseen": 18}
    assert pre["family_counts"] == {family: 12 for family in FAMILIES}
    assert pre["planned_episode_rows"] == 432
    assert pre["execution_authorized"] is False
    assert manifest["completed_calls"] == 432
    assert manifest["episodes_run"] == 0
