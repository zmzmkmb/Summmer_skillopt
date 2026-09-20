from pathlib import Path

from scripts.run_acl2027_tracegraph_tg6_local_execution_runner_v1 import (
    ALLOWED_INPUTS,
    SkillIndex,
    build_transition,
    fingerprint,
    validate_transition,
)


def test_observable_transition_is_deterministic_and_admissible():
    index = SkillIndex(
        [
            {
                "skill_id": "a",
                "source_split": "train",
                "canonical_actions": [{"action": "GotoLocation", "args": ["countertop"]}],
            }
        ]
    )
    transition = build_transition(index, "A kitchen observation.", [], ["go to countertop", "look"])
    assert list(transition["runtime_inputs"]) == ALLOWED_INPUTS
    assert transition["selected_skill_id"] == "a"
    assert transition["terminal_action_decision"] == "go to countertop"
    assert transition["observable_state_fingerprint"] == fingerprint(transition["runtime_inputs"])
    assert validate_transition(transition) == (True, "ok")


def test_ineligible_state_abstains_without_hidden_inputs():
    index = SkillIndex(
        [
            {
                "skill_id": "a",
                "source_split": "train",
                "canonical_actions": [{"action": "GotoLocation", "args": ["countertop"]}],
            }
        ]
    )
    transition = build_transition(index, "An observation.", ["look"], ["open fridge", "look"])
    assert transition["selected_skill_id"] is None
    assert transition["abstained"] is True
    assert transition["terminal_action_decision"] == "open fridge"
    assert all(key not in transition for key in {"planner_state", "pddl_params", "evaluation_label"})


def test_runner_source_has_no_model_or_provider_import():
    source = Path("scripts/run_acl2027_tracegraph_tg6_local_execution_runner_v1.py").read_text(encoding="utf-8")
    assert "chat_target" not in source
    assert "skillopt.model" not in source
    assert "requests" not in source
