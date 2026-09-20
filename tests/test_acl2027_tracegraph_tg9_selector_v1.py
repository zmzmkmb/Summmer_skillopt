from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.run_acl2027_tracegraph_tg6_local_execution_runner_v1 import SkillIndex
from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3 import (
    select_condition as select_tg8_condition,
)
from scripts.run_acl2027_tracegraph_tg9_selector_v1 import (
    CONDITIONS,
    classify_ledger_environment_consistency,
    classify_second_source,
    parse_observable_action,
    select_condition,
    validate_selector_transition,
)


def _skill_index(rows: list[tuple[str, str, list[str]]]) -> SkillIndex:
    return SkillIndex([
        {
            "skill_id": skill_id,
            "source_split": "train",
            "canonical_actions": [{"action": action, "args": args}],
        }
        for skill_id, action, args in rows
    ])


def _base_index() -> SkillIndex:
    return _skill_index([
        ("goto-drawer", "GotoLocation", ["drawer"]),
        ("goto-shelf", "GotoLocation", ["shelf"]),
        ("goto-toilet", "GotoLocation", ["toilet"]),
        ("pickup-spraybottle", "PickupObject", ["spraybottle"]),
        ("put-spraybottle-drawer", "PutObject", ["spraybottle", "drawer"]),
        ("put-spraybottle-toilet", "PutObject", ["spraybottle", "toilet"]),
    ])


def _interaction_index() -> SkillIndex:
    return _skill_index([
        ("open-drawer", "OpenObject", ["drawer"]),
        ("open-toilet", "OpenObject", ["toilet"]),
        ("close-drawer", "CloseObject", ["drawer"]),
        ("close-toilet", "CloseObject", ["toilet"]),
    ])


def runtime(observation: str, history: list[str], actions: list[str]) -> dict:
    return {
        "observation": observation,
        "historical_actions": history,
        "admissible_actions": actions,
    }


def _advance(
    rows: list[dict],
    condition: str,
    observation: str,
    actions: list[str],
    *,
    interaction_index: SkillIndex | None = None,
) -> dict:
    history = [row["terminal_action_decision"] for row in rows]
    snapshots = [row["observable_snapshot_fingerprint"] for row in rows]
    row = select_condition(
        _base_index(),
        condition,
        runtime(observation, history, actions),
        previous_ledger=rows[-1]["subgoal_ledger"] if rows else None,
        previous_snapshots=snapshots,
        interaction_index=interaction_index,
    )
    rows.append(row)
    return row


def _first_placement(condition: str) -> list[dict]:
    interaction = _interaction_index() if condition.endswith("open_close_coverage") else None
    rows: list[dict] = []
    _advance(
        rows,
        condition,
        "Your task is to: put two spraybottles in toilet.",
        ["go to shelf 1", "look"],
        interaction_index=interaction,
    )
    _advance(
        rows,
        condition,
        "At shelf 1, you see spraybottle 2 and spraybottle 3.",
        ["take spraybottle 2 from shelf 1", "go to toilet 1"],
        interaction_index=interaction,
    )
    _advance(
        rows,
        condition,
        "You pick up spraybottle 2 from shelf 1.",
        ["move spraybottle 2 to toilet 1", "go to toilet 1"],
        interaction_index=interaction,
    )
    return rows


def _picked_up_for_drawer(condition: str) -> list[dict]:
    interaction = _interaction_index() if condition.endswith("open_close_coverage") else None
    rows: list[dict] = []
    _advance(
        rows,
        condition,
        "Your task is to: put a spraybottle in drawer.",
        ["go to shelf 1", "look"],
        interaction_index=interaction,
    )
    _advance(
        rows,
        condition,
        "At shelf 1, you see spraybottle 2.",
        ["take spraybottle 2 from shelf 1"],
        interaction_index=interaction,
    )
    return rows


def test_first_placed_instance_is_rejected_for_second_slot_but_type_level_control_reuses_it():
    duplicate = "take spraybottle 2 from toilet 1"
    actions = [duplicate, "go to shelf 2", "look"]

    type_level_rows = _first_placement("type_level_current_coverage")
    type_level = _advance(
        type_level_rows,
        "type_level_current_coverage",
        "You put spraybottle 2 in toilet 1.",
        actions,
    )
    assert type_level["terminal_action_decision"] == duplicate
    assert type_level["pending_subgoal_id"] == "pickup_2"
    assert type_level["instance_binding_rejections"] == []

    bound_rows = _first_placement("instance_bound_current_coverage")
    bound = _advance(
        bound_rows,
        "instance_bound_current_coverage",
        "You put spraybottle 2 in toilet 1.",
        actions,
    )
    assert bound["terminal_action_decision"] == "go to shelf 2"
    assert bound["pending_subgoal_id"] == "search_source_2"
    assert [row["action"] for row in bound["instance_binding_rejections"]] == [duplicate]
    assert duplicate not in {row["action"] for row in bound["eligibility_rejections"]}
    assert bound["completed_instance_signatures"] == ["spraybottle 2"]
    assert bound["object_slot_1"]["source_signature"] == "shelf 1"
    assert bound["object_slot_1"]["destination_signature"] == "toilet 1"


def test_distinct_second_instance_is_selected_even_when_completed_instance_is_listed_first():
    rows = _first_placement("instance_bound_current_coverage")
    duplicate = "take spraybottle 2 from toilet 1"
    distinct = "take spraybottle 3 from shelf 2"
    row = _advance(
        rows,
        "instance_bound_current_coverage",
        "You put spraybottle 2 in toilet 1. Another spraybottle is on shelf 2.",
        [duplicate, distinct, "go to shelf 2"],
    )
    assert row["pending_subgoal_id"] == "pickup_2"
    assert row["terminal_action_decision"] == distinct
    assert row["second_source_is_distinct"] is True
    assert row["instance_binding_confidence"] == "explicit_instance"
    assert row["instance_binding_rejections"][0]["classification"] == "duplicate_explicit_instance"


def test_legal_open_action_is_a_skill_eligibility_rejection_when_coverage_is_off():
    rows = _picked_up_for_drawer("type_level_current_coverage")
    row = _advance(
        rows,
        "type_level_current_coverage",
        "You pick up spraybottle 2 from shelf 1. Drawer 1 is closed.",
        ["open drawer 1", "go to drawer 1"],
    )
    assert row["pending_subgoal_id"] == "search_destination"
    assert row["terminal_action_decision"] == "go to drawer 1"
    assert {item["action"] for item in row["eligibility_rejections"]} == {"open drawer 1"}
    assert row["instance_binding_rejections"] == []


def test_open_coverage_selects_open_and_new_put_action_advances_destination_search():
    interaction = _interaction_index()
    rows = _picked_up_for_drawer("type_level_open_close_coverage")
    opened = _advance(
        rows,
        "type_level_open_close_coverage",
        "You pick up spraybottle 2 from shelf 1. Drawer 1 is closed.",
        ["open drawer 1", "go to drawer 1"],
        interaction_index=interaction,
    )
    assert opened["terminal_action_decision"] == "open drawer 1"
    assert opened["selected_skill_id"] == "open-drawer"
    put = _advance(
        rows,
        "type_level_open_close_coverage",
        "You open drawer 1.",
        ["move spraybottle 2 to drawer 1", "close drawer 1"],
        interaction_index=interaction,
    )
    assert put["newly_completed_subgoal_ids"] == ["search_destination"]
    assert put["pending_subgoal_id"] == "put"
    assert put["terminal_action_decision"] == "move spraybottle 2 to drawer 1"
    assert "close-drawer" in put["candidate_skill_ids"]


def test_completed_ledger_and_false_environment_label_are_classified_offline_only():
    ledger = deepcopy(_first_placement("instance_bound_current_coverage")[-1]["subgoal_ledger"])
    ledger["completed_subgoal_ids"] = [row["id"] for row in ledger["subgoals"]]
    ledger["unresolved_subgoal_ids"] = []
    ledger["pending_subgoal_id"] = None
    assert classify_ledger_environment_consistency(ledger, False) == "ledger_complete_but_env_fail"
    with pytest.raises(ValueError, match="exactly the three observable fields"):
        select_condition(
            _base_index(),
            "instance_bound_current_coverage",
            {
                **runtime("Your task is to: put two spraybottles in toilet.", [], ["look"]),
                "environment_success": False,
            },
        )


def test_same_object_type_from_different_source_container_is_distinct_without_hidden_id():
    first_slot = {
        "object_type": "spraybottle",
        "object_signature": "spraybottle",
        "source_signature": "shelf 1",
        "destination_signature": "toilet 1",
    }
    result = classify_second_source(first_slot, "take spraybottle from shelf 2")
    assert result["classification"] == "distinct_source_container"
    assert result["is_distinct"] is True
    assert result["confidence"] == "source_distinguished"
    parsed = parse_observable_action("move spraybottle 2 to toilet 1")
    assert parsed == {
        "family": "put",
        "object_type": "spraybottle",
        "object_signature": "spraybottle 2",
        "explicit_instance": True,
        "source_signature": None,
        "destination_signature": "toilet 1",
    }


def test_unbound_no_coverage_preserves_tg8_control_decision_and_validator_recomputes():
    inputs = runtime(
        "Your task is to: put two spraybottles in toilet.",
        [],
        ["go to shelf 1", "go to toilet 1", "look"],
    )
    tg8_row = select_tg8_condition(_base_index(), "observable_subgoal_anti_cycle", inputs)
    tg9_row = select_condition(_base_index(), "type_level_current_coverage", inputs)
    for field in (
        "candidate_skill_ids",
        "eligibility_rejections",
        "selected_skill_id",
        "selected_edge",
        "terminal_action_decision",
        "pending_subgoal_id",
        "completed_subgoal_ids",
        "representation_score",
    ):
        assert tg9_row[field] == tg8_row[field]
    assert validate_selector_transition(tg9_row, index=_base_index()) == (True, "ok")

    tampered = deepcopy(tg9_row)
    tampered["instance_binding_rejections"] = [{
        "action": tampered["terminal_action_decision"],
        "reason": "tampered",
    }]
    assert validate_selector_transition(tampered, index=_base_index()) == (
        False,
        "instance-rejected action selected",
    )


def test_all_conditions_exist_and_selector_source_has_no_execution_or_network_surface():
    assert set(CONDITIONS) == {
        "type_level_current_coverage",
        "instance_bound_current_coverage",
        "type_level_open_close_coverage",
        "instance_bound_open_close_coverage",
    }
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts/run_acl2027_tracegraph_tg9_selector_v1.py"
    ).read_text(encoding="utf-8")
    assert "load_alfworld_builder" not in source
    assert ".step(" not in source
    assert "requests" not in source
    assert "provider" not in source.lower()
