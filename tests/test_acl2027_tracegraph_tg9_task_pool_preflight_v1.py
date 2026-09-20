from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg9_task_pool_preflight_v1 import (
    CONDITIONS,
    CONFIG,
    OUTPUT_DIR,
    build_artifacts,
    read_json,
    validate_config,
)


def test_tg9_config_is_closed_and_uses_the_correct_factorial_cells():
    config = read_json(CONFIG)
    assert validate_config(config) == []
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS
    assert tuple(item["id"] for item in config["conditions"]) == (
        "type_level_current_coverage",
        "instance_bound_current_coverage",
        "type_level_open_close_coverage",
        "instance_bound_open_close_coverage",
    )
    assert config["planned_episode_rows"] == 180
    assert config["execution_authorized"] is False
    assert config["readiness_allowed"] is False
    assert config["episode_execution_allowed"] is False


def test_tg9_pool_labels_exposure_and_strict_schedule_blindness():
    pool = read_json(OUTPUT_DIR / "task_pool.json")
    tasks = pool["tasks"]
    assert len(tasks) == 41
    assert len({row["task_identity"] for row in tasks}) == 41
    assert sum(row["tg9_role"] == "diagnosis_only_tg8_executed" for row in tasks) == 10
    assert sum(row["tg9_role"] == "historical_executed_excluded" for row in tasks) == 16
    internal = [row for row in tasks if row["tg9_role"] == "internal_validation"]
    assert len(internal) == 15
    assert sum(row["schedule_contaminated"] for row in internal) == 13
    assert sum(row["prior_schedule_identity_blind"] for row in internal) == 2
    assert {
        row["task_identity"] for row in internal if row["prior_schedule_identity_blind"]
    } == {
        "636f12ec414272e08fb20759618a008de9bebb084ccee16e2076b34284547add",
        "f965e61b35a96d3bff980a93f387a7073422ae9951a4123c09cbc115669a5f4e",
    }


def test_tg9_schedule_has_180_rows_and_balanced_conditions():
    schedule = read_json(OUTPUT_DIR / "internal_validation_schedule.json")
    assert schedule["task_count"] == 15
    assert len(schedule["tasks"]) == 15
    assert len(schedule["rows"]) == 180
    assert len({row["run_id"] for row in schedule["rows"]}) == 180
    assert Counter(row["condition"] for row in schedule["rows"]) == Counter(
        {condition: 45 for condition in CONDITIONS}
    )
    assert set(schedule["condition_position_counts"].values()) <= {11, 12}
    assert all(
        row["runtime_inputs"] if "runtime_inputs" in row else True
        for row in schedule["rows"]
    )
    assert schedule["runtime_allowed_inputs"] == [
        "observation",
        "historical_actions",
        "admissible_actions",
    ]
    assert schedule["execution_authorized"] is False
    assert schedule["episode_execution_allowed"] is False
    assert schedule["network_calls"] == 0
    assert schedule["provider_calls"] == 0
    assert schedule["model_calls"] == 0
    assert schedule["api_calls"] == 0
    assert schedule["paid_api_calls"] == 0


def test_tg9_preflight_is_zero_execution_and_rebuild_is_deterministic():
    config = read_json(CONFIG)
    artifacts = build_artifacts(config, OUTPUT_DIR)
    observed_preflight = read_json(OUTPUT_DIR / "preflight.json")
    observed_manifest = read_json(OUTPUT_DIR / "completion_manifest.json")
    assert observed_preflight == artifacts["preflight.json"]
    assert observed_manifest == artifacts["completion_manifest.json"]
    assert observed_preflight["planned_episode_rows"] == 180
    assert observed_preflight["materialized_rows"] == 180
    assert observed_preflight["completed_calls"] == 0
    assert observed_preflight["executed_calls"] == 0
    assert observed_preflight["episodes_run"] == 0
    assert observed_preflight["actions_taken"] == 0
    assert observed_preflight["execution_authorized"] is False
    assert observed_preflight["readiness_allowed"] is False
    assert observed_manifest["completed_calls"] == 0
    assert observed_manifest["executed_calls"] == 0
    assert observed_manifest["episodes_run"] == 0
    assert observed_manifest["actions_taken"] == 0
