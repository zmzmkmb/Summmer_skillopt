from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg7_progress_memory_runner_v1 import (
    ALLOWED_INPUTS,
    CONDITIONS,
    CONFIG,
    SkillIndex,
    extract_task_anchor,
    has_two_cycle,
    select_condition,
    validate_config,
)


def _index() -> SkillIndex:
    return SkillIndex(
        [
            {
                "skill_id": "skill-desk",
                "source_split": "train",
                "canonical_actions": [{"action": "GotoLocation", "args": ["desk"]}],
            },
            {
                "skill_id": "skill-fridge",
                "source_split": "train",
                "canonical_actions": [{"action": "GotoLocation", "args": ["fridge"]}],
            },
            {
                "skill_id": "skill-apple",
                "source_split": "train",
                "canonical_actions": [{"action": "PickupObject", "args": ["apple"]}],
            },
        ]
    )


def test_runner_config_is_closed_and_bound_to_frozen_preflight():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["execution_authorized"] is False
    assert config["episode_execution_allowed"] is False
    assert config["planned_episode_rows"] == 72
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS


def test_anchor_is_derived_from_initial_observation_only():
    anchor = extract_task_anchor(
        "You are in the kitchen. Your task is to put the apple in the fridge."
    )
    assert "apple" in anchor
    assert "fridge" in anchor
    assert "task" not in anchor


def test_anchor_and_progress_selectors_stay_admissible():
    index = _index()
    runtime = {
        "observation": "Your task is to put the apple in the fridge.",
        "historical_actions": ["go to desk"],
        "admissible_actions": ["go to desk", "go to fridge", "take apple"],
    }
    anchor = extract_task_anchor(runtime["observation"])
    anchor_row = select_condition(index, "task_anchor_aware", runtime, anchor, None, [], [], [])
    assert anchor_row["terminal_action_decision"] in runtime["admissible_actions"]
    progress_row = select_condition(
        index,
        "progress_memory",
        runtime,
        anchor,
        {
            "unresolved_anchor_tokens": ["apple", "fridge"],
            "attempted_actions": [],
            "observed_anchor_tokens": [],
            "attempted_anchor_tokens": [],
            "observable_snapshot_fingerprints": [],
        },
        [],
        [],
        [],
    )
    assert progress_row["terminal_action_decision"] == "go to fridge"
    assert progress_row["terminal_action_decision"] in runtime["admissible_actions"]
    assert progress_row["progress_ledger_valid"] is True
    assert progress_row["progress_ledger_provenance_complete"] is True
    assert list(progress_row["runtime_inputs"]) == ALLOWED_INPUTS


def test_progress_trace_contains_no_provider_or_hidden_state_path():
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts/run_acl2027_tracegraph_tg7_progress_memory_runner_v1.py"
    ).read_text(encoding="utf-8")
    assert "requests" not in source
    assert "skillopt.model" not in source
    assert "planner_state" not in source
    assert "pddl_params" not in source


def test_two_cycle_detector():
    assert has_two_cycle(["a", "b", "a", "b"]) is True
    assert has_two_cycle(["a", "b", "c", "b"]) is False
