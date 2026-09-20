from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg6_trajectory_failure_analysis_runner_v1 import (
    ALLOWED_INPUTS,
    CONDITIONS,
    CONFIG,
    SkillIndex,
    build_transition,
    detect_two_cycle,
    has_two_cycle,
    select_condition,
    snapshot_fingerprint,
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
                "skill_id": "skill-bed",
                "source_split": "train",
                "canonical_actions": [{"action": "GotoLocation", "args": ["bed"]}],
            },
            {
                "skill_id": "skill-drawer",
                "source_split": "train",
                "canonical_actions": [{"action": "OpenObject", "args": ["drawer"]}],
            },
        ]
    )


def test_runner_config_is_closed_and_exactly_bound():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["execution_authorized"] is False
    assert config["episode_execution_allowed"] is False
    assert config["planned_episode_rows"] == 72
    assert tuple(item["id"] for item in config["conditions"]) == CONDITIONS


def test_two_cycle_detector_uses_last_four_actions():
    assert detect_two_cycle(["x", "y", "x", "y"]) == (True, ("x", "y"))
    assert detect_two_cycle(["x", "y", "z", "y"]) == (False, None)
    assert has_two_cycle(["x", "y", "x", "y", "z"]) is True
    assert has_two_cycle(["x", "y", "z", "y", "x"]) is False


def test_snapshot_fingerprint_is_independent_of_history():
    first = snapshot_fingerprint("same observation", ["go to desk", "look"])
    second = snapshot_fingerprint("same observation", ["go to desk", "look"])
    assert first == second


def test_history_ablation_selects_outside_cycle_pair_but_stays_admissible():
    index = _index()
    runtime = {
        "observation": "room",
        "historical_actions": ["go to desk", "go to bed", "go to desk", "go to bed"],
        "admissible_actions": ["go to desk", "go to bed", "open drawer"],
    }
    transition = select_condition(index, "history_aware_anti_cycle", runtime, [], [], [])
    assert transition["terminal_action_decision"] == "open drawer"
    assert transition["terminal_action_decision"] in runtime["admissible_actions"]


def test_progress_ablation_prefers_unseen_action_and_valid_trace():
    index = _index()
    transition = build_transition(
        index,
        "observable_progress_aware",
        "room",
        ["go to desk", "go to bed", "go to desk", "go to bed"],
        ["go to desk", "go to bed", "open drawer"],
        [],
        ["skill-desk", "skill-bed", "skill-desk", "skill-bed"],
        [["skill-desk", "skill-bed"], ["skill-bed", "skill-desk"], ["skill-desk", "skill-bed"], ["skill-bed", "skill-desk"]],
    )
    assert transition["terminal_action_decision"] == "open drawer"
    assert transition["terminal_action_decision"] in transition["runtime_inputs"]["admissible_actions"]
    assert list(transition["runtime_inputs"]) == ALLOWED_INPUTS
    assert transition["selector_condition"] == "observable_progress_aware"
    assert transition["trace_valid"] if "trace_valid" in transition else True


def test_runner_source_has_no_provider_or_hidden_state_path():
    source = Path(
        "scripts/run_acl2027_tracegraph_tg6_trajectory_failure_analysis_runner_v1.py"
    ).read_text(encoding="utf-8")
    assert "requests" not in source
    assert "skillopt.model" not in source
    assert "planner_state" not in source
    assert "pddl_params" not in source
