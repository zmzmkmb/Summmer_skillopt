from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_preflight_v3 import (
    CONDITIONS,
    CONFIG,
    FAMILIES,
    validate_config,
)


def test_tg8_v3_config_is_closed_and_identifiable():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["development_task_count"] == 30
    assert config["replicate_count"] == 3
    assert config["planned_episode_rows"] == 360
    assert config["max_steps_per_episode"] == 75
    assert config["primary_step_landmark"] == 50
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS
    assert config["execution_authorized"] is False


def test_tg8_v3_schedule_has_unique_templates_and_explicit_rows():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_preflight_v3"
    pre = json.loads((artifact / "preflight.json").read_text(encoding="utf-8"))
    sched = json.loads((artifact / "development_schedule.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact / "completion_manifest.json").read_text(encoding="utf-8"))
    assert len(sched["tasks"]) == 30
    assert len(sched["rows"]) == 360
    assert len({row["run_id"] for row in sched["rows"]}) == 360
    for split in ("valid_seen", "valid_unseen"):
        for family in FAMILIES:
            tasks = [row for row in sched["tasks"] if row["split"] == split and row["task_family"] == family]
            assert len(tasks) == 5
            assert len({row["template_key"] for row in tasks}) == 5
    grouped = Counter((row["task_identity"], row["replicate_index"], row["condition"]) for row in sched["rows"])
    assert len(grouped) == 360
    assert set(grouped.values()) == {1}
    for task in sched["tasks"]:
        rows = [row for row in sched["rows"] if row["task_identity"] == task["task_identity"]]
        assert len(rows) == 12
        for replicate in range(3):
            replicate_rows = [row for row in rows if row["replicate_index"] == replicate]
            assert {row["condition"] for row in replicate_rows} == set(CONDITIONS)
            assert {row["condition_position"] for row in replicate_rows} == {0, 1, 2, 3}
            assert len({row["seed"] for row in replicate_rows}) == 1
    assert set(pre["template_counts"].values()) == {5}
    assert pre["no_overlap_audit"]["selected_executed_identity_overlap"] == 0
    assert pre["no_overlap_audit"]["superseded_designs_all_zero_episode"] is True
    assert pre["readiness_allowed"] is False
    assert pre["execution_authorized"] is False
    assert manifest["completed_calls"] == 360
    assert manifest["episodes_run"] == 0
