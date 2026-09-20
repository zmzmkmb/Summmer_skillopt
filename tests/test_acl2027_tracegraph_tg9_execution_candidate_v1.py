import json

from scripts.freeze_acl2027_tracegraph_tg9_execution_candidate_v1 import CONFIG, freeze


def test_candidate_is_fully_bound_but_closed():
    payload = freeze(json.loads(CONFIG.read_text(encoding="utf-8")))
    assert len(payload["aggregate_fingerprint"]) == 64
    assert payload["execution_authorized"] is False
    assert payload["episodes_run"] == payload["actions_taken"] == 0
    assert payload["primary_endpoint"] == "completion_by_step_50"
    assert payload["bindings"]["planned_rows"] == 180
