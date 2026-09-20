import json
from pathlib import Path

from scripts.audit_acl2027_tracegraph_tg9_readiness_v1 import audit, configured_horizon
from scripts.run_acl2027_tracegraph_tg9_runner_v1 import validate_config


ROOT = Path(__file__).resolve().parents[1]


def test_readiness_freezes_step_50_and_zero_execution():
    config = json.loads((ROOT / "configs/acl2027/tracegraph_tg9_readiness_v1.json").read_text(encoding="utf-8"))
    result = audit(config)
    assert result["effective_environment_horizon"] == 50
    assert result["completion_by_step_75_available"] is False
    assert result["episodes_run"] == result["actions_taken"] == 0


def test_horizon_parser_rejects_inconsistent_limits():
    assert configured_horizon("max_nb_steps_per_episode: 50\nmax_nb_steps_per_episode: 50") == 50
    try:
        configured_horizon("max_nb_steps_per_episode: 50\nmax_nb_steps_per_episode: 75")
    except ValueError:
        pass
    else:
        raise AssertionError("inconsistent horizons must fail readiness")


def test_runner_candidate_is_closed_without_a_fresh_bound_receipt():
    config = json.loads((ROOT / "configs/acl2027/tracegraph_tg9_runner_candidate_v1.json").read_text(encoding="utf-8"))
    errors = validate_config(config)
    assert "execution_authorized must be true" in errors
    assert "fresh authorization receipt missing or changed" in errors
