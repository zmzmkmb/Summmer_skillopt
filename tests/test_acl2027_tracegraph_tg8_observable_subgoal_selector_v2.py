from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.run_acl2027_tracegraph_tg6_local_execution_runner_v1 import SkillIndex
from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_selector_v2 import (
    CONDITIONS,
    build_subgoals,
    select_condition,
    validate_selector_transition,
)


def _index() -> SkillIndex:
    records = [
        ("goto-cabinet", "GotoLocation", ["cabinet"]),
        ("goto-countertop", "GotoLocation", ["countertop"]),
        ("goto-fridge", "GotoLocation", ["fridge"]),
        ("pickup-apple", "PickupObject", ["apple"]),
        ("pickup-banana", "PickupObject", ["banana"]),
        ("put-apple-fridge", "PutObject", ["apple", "fridge"]),
        ("put-banana-fridge", "PutObject", ["banana", "fridge"]),
        ("clean-apple-sink", "CleanObject", ["apple", "sinkbasin"]),
    ]
    return SkillIndex([
        {
            "skill_id": skill_id,
            "source_split": "train",
            "canonical_actions": [{"action": action, "args": args}],
        }
        for skill_id, action, args in records
    ])


def runtime(observation: str, history: list[str], actions: list[str]) -> dict:
    return {
        "observation": observation,
        "historical_actions": history,
        "admissible_actions": actions,
    }


def test_realistic_subgoal_chain_uses_receptacle_search_then_pickup():
    goals = build_subgoals("Your task is to: put an apple in the fridge.")
    assert [row["kind"] for row in goals] == [
        "search_source", "pickup", "search_destination", "put"
    ]
    assert goals[0]["required_token_groups"] == [["apple"]]
    index = _index()
    first = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "You are in a room. Your task is to: put an apple in the fridge.",
            [],
            ["go to cabinet 1", "go to countertop 1"],
        ),
    )
    assert first["terminal_action_decision"] == "go to cabinet 1"
    second = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "You arrive at countertop 1. On the countertop 1, you see an apple 1.",
            [first["terminal_action_decision"]],
            ["take apple 1 from countertop 1", "go to cabinet 1"],
        ),
        previous_ledger=first["subgoal_ledger"],
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    assert second["newly_completed_subgoal_ids"] == ["search_source"]
    assert second["pending_subgoal_id"] == "pickup"
    assert second["terminal_action_decision"] == "take apple 1 from countertop 1"
    assert second["progress_event"] is True
    assert validate_selector_transition(second) == (True, "ok")


def test_pickup_event_advances_only_on_observable_pickup_text():
    index = _index()
    first = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "Your task is to: put an apple in the fridge.", [], ["go to countertop 1"]
        ),
    )
    second = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "You arrive at countertop 1. You see an apple 1.",
            ["go to countertop 1"],
            ["take apple 1 from countertop 1"],
        ),
        previous_ledger=first["subgoal_ledger"],
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    third = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "You pick up the apple 1 from the countertop 1.",
            ["go to countertop 1", "take apple 1 from countertop 1"],
            ["go to fridge 1", "go to cabinet 1"],
        ),
        previous_ledger=second["subgoal_ledger"],
        previous_snapshots=[
            first["observable_snapshot_fingerprint"],
            second["observable_snapshot_fingerprint"],
        ],
    )
    assert third["newly_completed_subgoal_ids"] == ["pickup"]
    assert third["pending_subgoal_id"] == "search_destination"
    assert third["terminal_action_decision"] == "go to fridge 1"


def test_destination_search_requires_both_object_and_destination_tokens():
    index = _index()
    first = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime("Your task is to: put an apple in the fridge.", [], ["go to countertop 1"]),
    )
    first_ledger = first["subgoal_ledger"]
    first_ledger["completed_subgoal_ids"] = ["search_source", "pickup"]
    first_ledger["unresolved_subgoal_ids"] = ["search_destination", "put"]
    first_ledger["pending_subgoal_id"] = "search_destination"
    first_ledger["last_selected_action"] = "take apple 1 from countertop 1"
    first_ledger["last_selected_subgoal_id"] = "pickup"
    row = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "You arrive at fridge 1. A banana is visible.",
            ["take apple 1 from countertop 1"],
            ["put banana 1 in fridge 1", "go to cabinet 1"],
        ),
        previous_ledger=first_ledger,
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    assert "search_destination" not in row["newly_completed_subgoal_ids"]
    assert row["pending_subgoal_id"] == "search_destination"


def test_same_snapshot_relevant_action_is_false_progress():
    index = _index()
    first = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime("Your task is to: put an apple in the fridge.", [], ["go to countertop 1"]),
    )
    repeated = select_condition(
        index,
        "observable_subgoal_greedy",
        runtime(
            "Your task is to: put an apple in the fridge.",
            ["go to countertop 1"],
            ["go to countertop 1"],
        ),
        previous_ledger=first["subgoal_ledger"],
        previous_snapshots=[first["observable_snapshot_fingerprint"]],
    )
    assert repeated["observable_delta_since_previous"] is False
    assert repeated["progress_event"] is False
    assert repeated["false_progress_event"] is True


def test_tamper_detection_recomputes_fingerprints_and_history_binding():
    index = _index()
    row = select_condition(
        index,
        "lexical_greedy",
        runtime("Your task is to: put an apple in the fridge.", [], ["go to apple"]),
    )
    tampered = deepcopy(row)
    tampered["observable_snapshot_fingerprint"] = "0" * 64
    assert validate_selector_transition(tampered) == (False, "observable snapshot fingerprint mismatch")
    tampered = deepcopy(row)
    tampered["cycle_triggered"] = True
    assert validate_selector_transition(tampered) == (False, "cycle field mismatch")
    tampered = deepcopy(row)
    tampered["subgoal_ledger"]["pending_subgoal_id"] = "put"
    assert validate_selector_transition(tampered) == (False, "pending subgoal invalid")

    next_row = select_condition(
        index,
        "lexical_greedy",
        runtime("You arrive at apple 1.", [row["terminal_action_decision"]], ["go to fridge"]),
        previous_ledger=row["subgoal_ledger"],
        previous_snapshots=[row["observable_snapshot_fingerprint"]],
    )
    assert validate_selector_transition(next_row, row["subgoal_ledger"]) == (True, "ok")


def test_missing_ledger_and_hidden_transition_fields_are_rejected():
    index = _index()
    with pytest.raises(ValueError, match="previous subgoal ledger"):
        select_condition(
            index,
            "lexical_greedy",
            runtime("Your task is to: put an apple in the fridge.", ["go to apple"], ["go to fridge"]),
        )
    row = select_condition(
        index,
        "lexical_greedy",
        runtime("Your task is to: put an apple in the fridge.", [], ["go to apple"]),
    )
    tampered = deepcopy(row)
    tampered["planner_state"] = {"hidden": True}
    assert validate_selector_transition(tampered) == (False, "forbidden runtime field present")
