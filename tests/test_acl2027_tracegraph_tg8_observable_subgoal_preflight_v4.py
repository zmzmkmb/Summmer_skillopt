from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_preflight_v4 import (
    CONDITIONS,
    CONFIG,
    FAMILIES,
    validate_config,
)


def test_tg8_v4_config_is_closed():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["development_task_count"] == 30
    assert config["replicate_count"] == 3
    assert config["planned_episode_rows"] == 360
    assert config["max_steps_per_episode"] == 75
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS
    assert config["execution_authorized"] is False


def test_tg8_v4_schedule_is_global_unique_and_counterbalanced():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v4"
    pre = json.loads((artifact / "preflight.json").read_text(encoding="utf-8"))
    sched = json.loads((artifact / "development_schedule.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact / "completion_manifest.json").read_text(encoding="utf-8"))
    assert len(sched["tasks"]) == 30
    assert len({row["template_key"] for row in sched["tasks"]}) == 30
    assert len(sched["rows"]) == 360
    assert len({row["run_id"] for row in sched["rows"]}) == 360
    for split in ("valid_seen", "valid_unseen"):
        for family in FAMILIES:
            cell = [row for row in sched["tasks"] if row["split"] == split and row["task_family"] == family]
            assert len(cell) == 5
            assert len({row["template_key"] for row in cell}) == 5
    counts = Counter((row["condition"], row["condition_position"]) for row in sched["rows"])
    assert set(counts.values()) <= {22, 23}
    assert len(counts) == 16
    for condition in CONDITIONS:
        assert sum(counts[(condition, position)] for position in range(4)) == 90
    assert pre["globally_unique_template_count"] == 30
    assert pre["no_overlap_audit"]["selected_executed_identity_overlap"] == 0
    assert pre["no_overlap_audit"]["superseded_designs_zero_execution_verified"] is True
    assert pre["readiness_allowed"] is False
    assert pre["execution_authorized"] is False
    assert manifest["planned_rows"] == 360
    assert manifest["materialized_rows"] == 360
    assert manifest["completed_calls"] == 0
    assert manifest["executed_calls"] == 0
    assert manifest["episodes_run"] == 0
