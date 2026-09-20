from copy import deepcopy

import pytest

from scripts.run_acl2027_phase2_staged_live_runner_preflight_v1 import (
    AUTH, CONFIG, HARD, authorization_hash, cost, coverage_gate, exact_prefix,
    execute_stage, load, plan_rows, probe_audit_gate, run_local, stable,
    stage_allowed, validate_authorization, validate_bindings,
)


def open_auth(config, stages, calls, costs=None):
    auth = deepcopy(load(AUTH))
    auth.update({
        "status": "explicit_test_authorization",
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "formal_scaling_allowed": False,
        "authorized_stages": list(stages),
        "authorized_calls": calls,
        "stage_call_ceilings": {stage: config["stages"][stage] for stage in stages},
        "stage_cost_ceilings_cny": costs or {stage: config["cost_control"]["stage_ceilings_cny"][stage] for stage in stages},
        "cumulative_cost_ceiling_cny": 7.5,
    })
    return auth


def response(input_tokens=10, output_tokens=5):
    return {"content": "fake", "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens}}


def supports():
    return {family: [f"{family}:{i}" for i in range(8)] for family in load(CONFIG)["coverage_gate"]["families"]}


def test_json_and_frozen_bindings_are_exact():
    config = load(CONFIG)
    rows = validate_bindings(config)
    assert len(rows) == 710
    assert [sum(row["partition"] == stage for row in rows) for stage in ("calibration", "development_acquisition", "formal_history", "probe", "held_out")] == [60, 10, 160, 160, 320]
    assert "TO_BE_FILLED" not in CONFIG.read_text(encoding="utf-8")


def test_closed_authorization_and_zero_provider_calls():
    config, auth = load(CONFIG), load(AUTH)
    assert validate_authorization(config, auth) == authorization_hash(auth)
    assert auth["formal_scaling_allowed"] is False
    result = run_local(config)
    assert [result[key] for key in ("network_calls", "provider_calls", "model_calls", "paid_api_calls")] == [0, 0, 0, 0]


def test_closed_mode_never_invokes_provider():
    called = 0
    def provider(_):
        nonlocal called
        called += 1
        return response()
    with pytest.raises(HARD, match="disabled"):
        run_local(load(CONFIG), provider=provider)
    assert called == 0


def test_frozen_and_authorization_hash_drift_stop():
    config = deepcopy(load(CONFIG))
    config["frozen_bindings"]["request_plan"]["sha256"] = "0" * 64
    with pytest.raises(HARD, match="request_plan hash drift"):
        validate_bindings(config)
    auth = deepcopy(load(AUTH))
    auth["preflight_binding"]["sha256"] = "0" * 64
    with pytest.raises(HARD, match="preflight hash binding"):
        validate_authorization(load(CONFIG), auth)


def test_exact_prefix_resume_and_authorization_hash_binding():
    config = load(CONFIG)
    auth = open_auth(config, ["calibration"], 2)
    records = execute_stage(config, auth, [], "calibration", lambda _: response(), max_new_calls=1)
    assert records[0]["authorization_sha256"] == authorization_hash(auth)
    records = execute_stage(config, auth, records, "calibration", lambda _: response(), max_new_calls=1)
    assert len(records) == 2
    records[0]["request_hash"] = "0" * 64
    with pytest.raises(HARD, match="non-prefix"):
        exact_prefix(records, plan_rows(config))


def test_resume_rejects_different_authorization_hash():
    config = load(CONFIG)
    auth = open_auth(config, ["calibration"], 2)
    records = execute_stage(config, auth, [], "calibration", lambda _: response(), max_new_calls=1)
    changed = deepcopy(auth)
    changed["endpoint_route"] = "different authorized route"
    with pytest.raises(HARD, match="authorization hash drift"):
        execute_stage(config, changed, records, "calibration", lambda _: response(), max_new_calls=1)


@pytest.mark.parametrize("bad", [None, {}, {"input_tokens": 1, "output_tokens": 2, "total_tokens": 4}, {"input_tokens": -1, "output_tokens": 2, "total_tokens": 1}])
def test_bad_usage_stops_after_one_attempt_without_retry(bad):
    config = load(CONFIG)
    auth = open_auth(config, ["calibration"], 1)
    calls = 0
    def provider(_):
        nonlocal calls
        calls += 1
        return {"content": "x", "usage": bad}
    with pytest.raises(HARD, match="usage") as stopped:
        execute_stage(config, auth, [], "calibration", provider)
    assert calls == 1
    assert stopped.value.ledger[0]["terminal"] is True
    assert "raw_response" in stopped.value.ledger[0]


def test_cost_accounting_and_hard_ceilings():
    config = load(CONFIG)
    assert cost(config, {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}) == pytest.approx(10.0)
    auth = open_auth(config, ["calibration"], 1, {"calibration": 0.00001})
    auth["cumulative_cost_ceiling_cny"] = 0.00001
    with pytest.raises(HARD, match="cost ceiling") as stopped:
        execute_stage(config, auth, [], "calibration", lambda _: response(10, 10))
    assert stopped.value.ledger[0]["usage"]["total_tokens"] == 20
    with pytest.raises(HARD, match="not resumable"):
        execute_stage(config, auth, stopped.value.ledger, "calibration", lambda _: response())


def test_stage_boundary_and_call_ceiling():
    config = load(CONFIG)
    with pytest.raises(HARD, match="stage boundary"):
        execute_stage(config, open_auth(config, ["development_acquisition"], 10), [], "development_acquisition", lambda _: response())
    auth = open_auth(config, ["calibration"], 1)
    records = execute_stage(config, auth, [], "calibration", lambda _: response(), max_new_calls=1)
    with pytest.raises(HARD, match="not authorized"):
        execute_stage(config, auth, records, "calibration", lambda _: response())


def test_formal_scaling_not_required_but_three_switches_are():
    config = load(CONFIG)
    auth = open_auth(config, ["calibration"], 1)
    assert stage_allowed("calibration", config, auth, [], coverage_gate({}), False)
    for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open"):
        changed = deepcopy(auth)
        changed[key] = False
        assert not stage_allowed("calibration", config, changed, [], coverage_gate({}), False)


def test_coverage_requires_independent_eight_per_family():
    valid = supports()
    assert coverage_gate(valid)["passed"]
    valid["entity_bridge"] = valid["entity_bridge"][:7]
    assert coverage_gate(valid)["status"] == "coverage-incomplete"
    duplicate = supports()
    duplicate["relation_inference"][0] = duplicate["fact_retrieval"][0]
    assert not coverage_gate(duplicate)["passed"]


def test_probe_audit_gate_and_held_out_authorization():
    config = load(CONFIG)
    rows = plan_rows(config)
    auth = open_auth(config, ["probe", "held_out"], 480)
    gate = coverage_gate(supports())
    assert stage_allowed("probe", config, auth, [], gate, False)
    assert not stage_allowed("held_out", config, auth, [], gate, False)
    probe_rows = [row for row in rows if row["partition"] == "probe"]
    ledger = [{"partition": "probe", "request_hash": row["request_hash"]} for row in probe_rows]
    audit = {"passed": True, "probe_calls": 160, "probe_request_hashes_sha256": stable([row["request_hash"] for row in probe_rows]), "coverage_gate_passed": True}
    assert probe_audit_gate(rows, ledger, audit)
    assert not probe_audit_gate(rows, ledger, {**audit, "probe_request_hashes_sha256": "0" * 64})


def test_authorization_rejects_stage_overreach():
    config = load(CONFIG)
    auth = open_auth(config, ["calibration"], 60)
    auth["stage_call_ceilings"]["calibration"] = 61
    with pytest.raises(HARD, match="stage call ceiling"):
        validate_authorization(config, auth)
    auth = open_auth(config, ["calibration"], 60)
    auth["stage_cost_ceilings_cny"]["calibration"] = 0.51
    with pytest.raises(HARD, match="stage cost ceiling"):
        validate_authorization(config, auth)
