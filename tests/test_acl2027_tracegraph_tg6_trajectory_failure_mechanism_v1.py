from pathlib import Path

from scripts.audit_acl2027_tracegraph_tg6_trajectory_failure_mechanism_v1 import (
    CONFIG,
    audit,
    command_mentions,
    goal_surface_action,
    read_json,
    validate_config,
)


ROOT = Path(__file__).resolve().parents[1]


def test_mechanism_audit_config_is_closed_and_bound():
    config = read_json(CONFIG)
    assert validate_config(config, ROOT) == []
    assert config["episodes_run"] == 0
    assert config["runtime_allowed_inputs"] == [
        "observation",
        "historical_actions",
        "admissible_actions",
    ]


def test_goal_surface_classifier_is_posthoc_only():
    goal = {"family": "pick_and_place_simple", "target": "book", "destination": "sidetable"}
    assert command_mentions("take book 1 from table 1", "book")
    assert goal_surface_action("take book 1 from table 1", goal)
    assert not goal_surface_action("go to garbagecan 1", goal)


def test_audit_reads_completed_parent_without_running_episodes():
    result = audit(read_json(CONFIG), ROOT)
    assert result["status"] == "completed"
    assert result["task_count"] == 24
    assert result["episode_count"] == 72
    assert result["transition_count"] == 3600
    assert result["interpretation"]["episodes_run"] == 0
