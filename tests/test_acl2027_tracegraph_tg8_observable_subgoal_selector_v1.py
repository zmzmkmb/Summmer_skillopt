from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_acl2027_tracegraph_tg6_local_execution_runner_v1 import SkillIndex
from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_selector_v1 import (
    ALLOWED_INPUTS,
    build_subgoals,
    select_condition,
    validate_selector_transition,
)


def _index() -> SkillIndex:
    actions = [
        ("goto-apple", "GotoLocation", ["apple"]),
        ("goto-fridge", "GotoLocation", ["fridge"]),
        ("goto-desk", "GotoLocation", ["desk"]),
        ("goto-sink", "GotoLocation", ["sinkbasin"]),
        ("pickup-apple", "PickupObject", ["apple"]),
        ("put-apple-fridge", "PutObject", ["apple", "fridge"]),
        ("clean-apple", "CleanObject", ["apple", "sinkbasin"]),
    ]
    return SkillIndex([
        {
            "skill_id": skill_id,
            "source_split": "train",
            "canonical_actions": [{"action": action, "args": args}],
        }
        for skill_id, action, args in actions
    ])


def _runtime(observation: str, history: list[str], admissible: list[str]) -> dict:
    return {
        "observation": observation,
        "historical_actions": history,
        "admissible_actions": admissible,
    }


def test_subgoal_grammar_covers_three_frozen_families():
    simple = build_subgoals("Your task is to: put an apple in the fridge.")
    assert [(row["family"], row["entity_tokens"]) for row in simple] == [
        ("goto", ["apple"]),
        ("pickup", ["apple"]),
        ("goto", ["fridge"]),
        ("put", ["apple", "fridge"]),
    ]
    two = build_subgoals("Your task is to: put two apples in the fridge.")
    assert [row["family"] for row in two] == [
        "goto", "pickup", "goto", "pickup", "goto", "put", "put",
    ]
    clean = build_subgoals("Your task is to: put a clean apple in the fridge.")
    assert [row["family"] for row in clean] == [
        "goto", "pickup", "goto", "clean", "goto", "put",
    ]
    assert clean[2]["entity_tokens"] == ["sinkbasin"]


def test_structured_selector_consumes_observable_delta_before_ranking():
    index = _index()
    first = select_condition(
        index,
        "observable_subgoal_greedy",
        _runtime(
            "You are in a room. Your task is to: put an apple in the fridge.",
            [],
            ["go to fridge", "go to apple"],
        ),
    )
    assert first["terminal_action_decision"] == "go to apple"
    second = select_condition(
        index,
        "observable_subgoal_greedy",
        _runtime(
            "You arrive at apple 1.",
            ["go to apple"],
            ["go to fridge", "take apple from countertop"],
        ),
        previous_ledger=first["subgoal_ledger"],
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    assert second["progress_event"] is True
    assert second["false_progress_event"] is False
    assert "sg0" in second["completed_subgoal_ids"]
    assert second["pending_subgoal_id"] == "sg1"
    assert second["terminal_action_decision"] == "take apple from countertop"
    assert validate_selector_transition(second) == (True, "ok")


def test_target_action_without_observable_delta_is_false_progress():
    index = _index()
    runtime = _runtime(
        "You are in a room. Your task is to: put an apple in the fridge.",
        [],
        ["go to apple", "go to fridge"],
    )
    first = select_condition(index, "observable_subgoal_greedy", runtime)
    repeated = select_condition(
        index,
        "observable_subgoal_greedy",
        _runtime(runtime["observation"], ["go to apple"], runtime["admissible_actions"]),
        previous_ledger=first["subgoal_ledger"],
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    assert repeated["progress_event"] is False
    assert repeated["false_progress_event"] is True
    assert "sg0" not in repeated["completed_subgoal_ids"]
    assert repeated["pending_subgoal_id"] == "sg0"


def test_state_delta_from_nonmatching_action_does_not_complete_subgoal():
    index = _index()
    first = select_condition(
        index,
        "observable_subgoal_greedy",
        _runtime(
            "You are in a room. Your task is to: put an apple in the fridge.",
            [],
            ["go to apple", "go to desk"],
        ),
    )
    ledger = dict(first["subgoal_ledger"])
    ledger["last_selected_action"] = "go to desk"
    ledger["last_selected_subgoal_id"] = "sg0"
    changed = select_condition(
        index,
        "observable_subgoal_greedy",
        _runtime("You arrive at desk 1.", ["go to desk"], ["go to apple", "go to fridge"]),
        previous_ledger=ledger,
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    assert changed["observable_delta_since_previous"] is True
    assert changed["progress_event"] is False
    assert changed["false_progress_event"] is False
    assert changed["completed_subgoal_ids"] == []


def test_representation_and_controller_factors_can_each_change_action():
    index = _index()
    runtime = _runtime(
        "Your task is to: put an apple in the fridge.",
        ["go to apple", "go to fridge", "go to apple", "go to fridge"],
        ["go to fridge", "go to apple", "take apple from countertop"],
    )
    lexical_greedy = select_condition(index, "lexical_greedy", runtime)
    lexical_anti = select_condition(index, "lexical_anti_cycle", runtime)
    structured = select_condition(index, "observable_subgoal_greedy", runtime)
    assert lexical_greedy["terminal_action_decision"] == "go to fridge"
    assert lexical_anti["terminal_action_decision"] == "take apple from countertop"
    assert structured["terminal_action_decision"] == "go to apple"
    assert lexical_anti["cycle_triggered"] is True


def test_runtime_input_boundary_is_exact():
    index = _index()
    with pytest.raises(ValueError, match="exactly the three observable fields"):
        select_condition(
            index,
            "lexical_greedy",
            {
                "observation": "Your task is to put an apple in the fridge.",
                "historical_actions": [],
                "admissible_actions": ["go to apple"],
                "planner_state": {},
            },
        )
    row = select_condition(
        index,
        "lexical_greedy",
        _runtime("Your task is to put an apple in the fridge.", [], ["go to apple"]),
    )
    assert list(row["runtime_inputs"]) == ALLOWED_INPUTS


def test_selector_source_has_no_environment_or_provider_execution_path():
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts/run_acl2027_tracegraph_tg8_observable_subgoal_selector_v1.py"
    ).read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "skillopt.model" not in source
    assert "load_alfworld_builder" not in source
    assert ".step(" not in source
