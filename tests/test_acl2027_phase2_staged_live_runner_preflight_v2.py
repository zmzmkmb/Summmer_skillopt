from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.run_acl2027_phase2_staged_live_runner_preflight_v1 import (
    AUTH as V1_AUTH, CONFIG as V1_CONFIG, FAMILIES as V1_FAMILIES,
    authorization_hash as v1_auth_hash, coverage_gate as v1_coverage_gate,
    execute_stage as v1_execute, load as v1_load, stage_allowed as v1_stage_allowed,
)
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v2 import (
    AUTH, CONFIG, COVERAGE_SCHEMA, PROBE_SCHEMA, ROOT, HARD, FAMILIES,
    audit_schedule, build_schedule, execute_stage, ledger_hash, load, original_rows,
    run_local, sha256_file, stable, validate_authorization, validate_ledger,
    verify_coverage, verify_probe_audit,
)


CONFIG_DATA = load(CONFIG)
SCHEDULE = build_schedule(original_rows(CONFIG_DATA))


class MockProvider:
    def __init__(self, bad_usage=None, error: Exception | None = None):
        self.calls = 0
        self.bad_usage = bad_usage
        self.error = error

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert "max_tokens" not in body
        if self.error:
            raise self.error
        usage = self.bad_usage if self.bad_usage is not None else {
            "input_tokens": 10, "output_tokens": 5, "total_tokens": 15
        }
        return {"content": f"mock-response-{self.calls}-{body['partition']}-{body['task_id']}-{body['condition']}", "usage": usage}


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def auth_for(stage, calls=None, *, stage_cost=None, cumulative=7.5, auth_id=None):
    auth = deepcopy(load(AUTH))
    calls = CONFIG_DATA["stages"][stage] if calls is None else calls
    auth.update({
        "experiment": f"mock-{stage}", "authorization_id": auth_id or f"mock-{stage}", "status": "test_open",
        "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True,
        "formal_scaling_allowed": False, "authorized_stage": stage, "authorized_calls": calls,
        "stage_call_ceiling": calls,
        "stage_cost_ceiling_cny": CONFIG_DATA["cost_control"]["stage_ceilings_cny"][stage] if stage_cost is None else stage_cost,
        "cumulative_cost_ceiling_cny": cumulative,
    })
    return auth


def registry(tmp_path, auths):
    entries = {}
    for auth in auths:
        path = tmp_path / f"{auth['authorization_id']}.json"
        write_json(path, auth)
        entries[auth["authorization_id"]] = {"path": path.name, "sha256": sha256_file(path)}
    path = tmp_path / "authorization_registry.json"
    write_json(path, {"schema_version": 2, "authorizations": entries})
    return path


def run_stage(tmp_path, ledger, stage, provider=None, calls=None, auth_id=None, **gates):
    auth = auth_for(stage, calls, auth_id=auth_id)
    old_auths = []
    if ledger:
        seen = set()
        for record in ledger:
            if record["authorization_id"] not in seen:
                seen.add(record["authorization_id"])
                old_auths.append(record.pop("_test_auth", None))
        old_auths = [a for a in old_auths if a]
    reg = registry(tmp_path, old_auths + [auth])
    result = execute_stage(CONFIG_DATA, SCHEDULE, reg, auth["authorization_id"], ledger, stage, provider or MockProvider(), **gates)
    for record in result:
        record["_test_auth"] = next((a for a in old_auths + [auth] if a["authorization_id"] == record["authorization_id"]), None)
    return result, auth, reg


def strip_test(ledger):
    for record in ledger:
        record.pop("_test_auth", None)
    return ledger


def make_coverage(tmp_path, ledger, *, per_family=8, mutate=None):
    clean = deepcopy(strip_test(deepcopy(ledger)))
    rows = {r["logical_call_id"]: r for r in SCHEDULE if r["partition"] == "formal_history"}
    records = {r["logical_call_id"]: r for r in clean if r["partition"] == "formal_history"}
    trajectories = []
    for family in FAMILIES:
        selected = [r for r in rows.values() if r["skill_family"] == family][:per_family]
        for i, row in enumerate(selected):
            response = records[row["logical_call_id"]]
            trajectories.append({
                "trajectory_id": f"trajectory-{family}-{i}", "task_id": row["task_id"],
                "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"],
                "response_sha256": response["raw_response_sha256"], "verifier_confirmed_success": True,
                "family": family, "candidate_id": f"candidate-{family}", "support_id": f"support-{family}-{i}",
                "provenance": {"partition": "formal_history", "source": "mock-test-only"},
            })
    artifact = {
        "schema_version": 2, "schema_config_sha256": sha256_file(COVERAGE_SCHEMA),
        "verifier_config_sha256": CONFIG_DATA["coverage_gate"]["verifier_config_sha256"],
        "history_response_ledger_sha256": ledger_hash([r for r in clean if r["partition"] == "formal_history"]),
        "evaluation_leakage_audit": {"passed": True, "probe_gold_accessed": False, "held_out_gold_accessed": False},
        "trajectories": trajectories,
    }
    if mutate:
        mutate(artifact)
    path = tmp_path / "candidate_materialization.json"
    write_json(path, artifact)
    return path, sha256_file(path)


def lifecycle_to_history(tmp_path):
    provider = MockProvider()
    cal = auth_for("calibration", auth_id="auth-cal")
    reg = registry(tmp_path, [cal])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "auth-cal", [], "calibration", provider)
    dev = auth_for("development_acquisition", auth_id="auth-dev")
    reg = registry(tmp_path, [cal, dev])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "auth-dev", ledger, "development_acquisition", provider)
    hist = auth_for("formal_history", auth_id="auth-history")
    reg = registry(tmp_path, [cal, dev, hist])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "auth-history", ledger, "formal_history", provider)
    return ledger, provider, [cal, dev, hist]


def test_v1_original_interleaving_and_silent_12_call_failure():
    rows = v1_load(V1_CONFIG)
    plan = v1_load(ROOT / rows["frozen_bindings"]["request_plan"]["path"])["plan"]
    assert [(r["partition"], r["skill_family"]) for r in plan[:46]] == (
        [("calibration", "fact_retrieval")] * 12 + [("development_acquisition", "fact_retrieval")] * 2 +
        [("formal_history", "fact_retrieval")] * 32)
    auth = deepcopy(v1_load(V1_AUTH))
    auth.update(status="audit", paid_api_allowed=True, provider_calls_allowed=True, qwen_authorization_open=True,
                authorized_stages=["calibration"], authorized_calls=60, stage_call_ceilings={"calibration": 60},
                stage_cost_ceilings_cny={"calibration": .5}, cumulative_cost_ceiling_cny=7.5)
    assert len(v1_execute(rows, auth, [], "calibration", lambda _: {"content": "x", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}})) == 12


def test_v1_cross_auth_quota_coverage_and_fingerprint_defects():
    config = v1_load(V1_CONFIG)
    cal = deepcopy(v1_load(V1_AUTH)); cal.update(status="audit", paid_api_allowed=True, provider_calls_allowed=True,
        qwen_authorization_open=True, authorized_stages=["calibration"], authorized_calls=60,
        stage_call_ceilings={"calibration": 60}, stage_cost_ceilings_cny={"calibration": .5}, cumulative_cost_ceiling_cny=7.5)
    response = lambda _: {"content": "x", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
    ledger = v1_execute(config, cal, [], "calibration", response)
    dev = deepcopy(cal); dev.update(authorized_stages=["development_acquisition"], authorized_calls=10,
        stage_call_ceilings={"development_acquisition": 10}, stage_cost_ceilings_cny={"development_acquisition": .11})
    with pytest.raises(Exception, match="authorization hash drift"):
        v1_execute(config, dev, ledger, "development_acquisition", response)
    for row in ledger:
        row["authorization_sha256"] = v1_auth_hash(dev)
    assert not v1_stage_allowed("development_acquisition", config, dev, ledger, v1_coverage_gate({}), False)
    fake = {f: [f"fake-{f}-{i}" for i in range(8)] for f in V1_FAMILIES}
    assert v1_coverage_gate(fake)["passed"]
    manifest = load(ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v1/run_manifest.json")
    assert "runner_source_sha256" not in manifest and "test_source_sha256" not in manifest


def test_schedule_is_strict_710_request_bijection():
    audit = audit_schedule(original_rows(CONFIG_DATA), SCHEDULE)
    assert audit["strict_bijection"] and audit["stage_counts"] == CONFIG_DATA["stages"]
    assert [r["staged_execution_index"] for r in SCHEDULE] == list(range(1, 711))


def test_calibration_executes_60_not_12(tmp_path):
    auth = auth_for("calibration")
    reg = registry(tmp_path, [auth])
    provider = MockProvider()
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, auth["authorization_id"], [], "calibration", provider)
    assert len(ledger) == provider.calls == 60


def test_incomplete_calibration_cannot_start_development(tmp_path):
    cal = auth_for("calibration", 59, auth_id="cal-59")
    reg = registry(tmp_path, [cal])
    with pytest.raises(HARD, match="call ceiling") as stopped:
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "cal-59", [], "calibration", MockProvider())
    dev = auth_for("development_acquisition", auth_id="dev")
    reg = registry(tmp_path, [cal, dev])
    with pytest.raises(HARD, match="stage skipped"):
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "dev", stopped.value.ledger, "development_acquisition", MockProvider())


def test_cross_authorization_60_plus_10_and_quota_is_independent(tmp_path):
    provider = MockProvider()
    cal, dev = auth_for("calibration", auth_id="cal"), auth_for("development_acquisition", auth_id="dev")
    reg = registry(tmp_path, [cal])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "cal", [], "calibration", provider)
    reg = registry(tmp_path, [cal, dev])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "dev", ledger, "development_acquisition", provider)
    assert len(ledger) == 70 and sum(r["authorization_id"] == "dev" for r in ledger) == 10


def test_formal_history_appends_160_and_old_hashes_resolve(tmp_path):
    ledger, _, auths = lifecycle_to_history(tmp_path)
    reg = registry(tmp_path, auths)
    validate_ledger(SCHEDULE, ledger, reg)
    assert len(ledger) == 230 and len({r["authorization_sha256"] for r in ledger}) == 3


def test_raw_string_supports_api_does_not_exist():
    import scripts.run_acl2027_phase2_staged_live_runner_preflight_v2 as runner
    assert not hasattr(runner, "coverage_gate")
    with pytest.raises(HARD, match="immutable artifact path"):
        verify_coverage(CONFIG_DATA, SCHEDULE, [], {f: ["x"] * 8 for f in FAMILIES}, "0" * 64)


@pytest.mark.parametrize("mutation", [
    lambda a: a["trajectories"][0].pop("verifier_confirmed_success"),
    lambda a: a.update(history_response_ledger_sha256="0" * 64),
    lambda a: a["trajectories"][0].pop("response_sha256"),
    lambda a: a["trajectories"][0].update(family="relation_inference"),
])
def test_coverage_missing_verdict_ledger_response_or_family_fails(tmp_path, mutation):
    ledger, _, _ = lifecycle_to_history(tmp_path)
    path, sha = make_coverage(tmp_path, ledger, mutate=mutation)
    with pytest.raises(HARD, match="coverage"):
        verify_coverage(CONFIG_DATA, SCHEDULE, ledger, path, sha)


def test_coverage_eight_per_family_passes_and_seven_is_incomplete(tmp_path):
    ledger, _, _ = lifecycle_to_history(tmp_path)
    path, sha = make_coverage(tmp_path, ledger)
    assert verify_coverage(CONFIG_DATA, SCHEDULE, ledger, path, sha)["passed"]
    path, sha = make_coverage(tmp_path, ledger, per_family=7)
    result = verify_coverage(CONFIG_DATA, SCHEDULE, ledger, path, sha)
    assert result["status"] == "coverage-incomplete" and result["method_failure"] is False


@pytest.mark.parametrize("field", ["trajectory_id", "task_id", "logical_call_id", "response_sha256", "support_id"])
def test_cross_family_duplicate_identity_fails(tmp_path, field):
    ledger, _, _ = lifecycle_to_history(tmp_path)
    def mutate(a):
        first = a["trajectories"][0]
        other = next(x for x in a["trajectories"] if x["family"] != first["family"])
        other[field] = first[field]
    path, sha = make_coverage(tmp_path, ledger, mutate=mutate)
    with pytest.raises(HARD):
        verify_coverage(CONFIG_DATA, SCHEDULE, ledger, path, sha)


def test_coverage_hash_drift_and_incomplete_blocks_probe(tmp_path):
    ledger, provider, auths = lifecycle_to_history(tmp_path)
    path, sha = make_coverage(tmp_path, ledger, per_family=7)
    with pytest.raises(HARD, match="hash drift"):
        verify_coverage(CONFIG_DATA, SCHEDULE, ledger, path, "0" * 64)
    probe = auth_for("probe", auth_id="probe")
    reg = registry(tmp_path, auths + [probe])
    with pytest.raises(HARD, match="coverage not passed"):
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "probe", ledger, "probe", provider, coverage_path=path, coverage_sha=sha)


def test_probe_incomplete_and_audit_hash_drift_block_held_out(tmp_path):
    ledger, provider, auths = lifecycle_to_history(tmp_path)
    coverage_path, coverage_sha = make_coverage(tmp_path, ledger)
    probe = auth_for("probe", 159, auth_id="probe-159")
    reg = registry(tmp_path, auths + [probe])
    with pytest.raises(HARD, match="call ceiling") as stopped:
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "probe-159", ledger, "probe", provider, coverage_path=coverage_path, coverage_sha=coverage_sha)
    held = auth_for("held_out", auth_id="held")
    reg = registry(tmp_path, auths + [probe, held])
    with pytest.raises(HARD):
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "held", stopped.value.ledger, "held_out", provider,
                      coverage_path=coverage_path, coverage_sha=coverage_sha)

    probe = auth_for("probe", auth_id="probe-full")
    reg = registry(tmp_path, auths + [probe])
    complete = execute_stage(CONFIG_DATA, SCHEDULE, reg, "probe-full", ledger, "probe", provider,
                             coverage_path=coverage_path, coverage_sha=coverage_sha)
    audit_path = tmp_path / "probe_audit.json"
    probe_rows = [r for r in complete if r["partition"] == "probe"]
    write_json(audit_path, {"passed": True, "coverage_artifact_sha256": coverage_sha,
        "probe_ledger_sha256": ledger_hash(probe_rows), "analyzer_config_sha256": sha256_file(PROBE_SCHEMA)})
    held = auth_for("held_out", auth_id="held")
    reg = registry(tmp_path, auths + [probe, held])
    with pytest.raises(HARD, match="probe audit hash drift"):
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "held", complete, "held_out", provider,
            coverage_path=coverage_path, coverage_sha=coverage_sha, probe_audit_path=audit_path, probe_audit_sha="0" * 64)


def test_complete_710_call_mock_lifecycle_distinct_authorizations(tmp_path):
    ledger, provider, auths = lifecycle_to_history(tmp_path)
    coverage_path, coverage_sha = make_coverage(tmp_path, ledger)
    probe = auth_for("probe", auth_id="auth-probe")
    reg = registry(tmp_path, auths + [probe])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "auth-probe", ledger, "probe", provider,
                           coverage_path=coverage_path, coverage_sha=coverage_sha)
    audit_path = tmp_path / "probe_audit.json"
    write_json(audit_path, {"passed": True, "coverage_artifact_sha256": coverage_sha,
        "probe_ledger_sha256": ledger_hash([r for r in ledger if r["partition"] == "probe"]),
        "analyzer_config_sha256": sha256_file(PROBE_SCHEMA)})
    held = auth_for("held_out", auth_id="auth-held")
    reg = registry(tmp_path, auths + [probe, held])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "auth-held", ledger, "held_out", provider,
        coverage_path=coverage_path, coverage_sha=coverage_sha,
        probe_audit_path=audit_path, probe_audit_sha=sha256_file(audit_path))
    assert len(ledger) == provider.calls == 710
    assert [r["logical_call_id"] for r in ledger] == [r["logical_call_id"] for r in SCHEDULE]
    assert len({r["authorization_sha256"] for r in ledger}) == 5


def test_zero_retries_no_max_tokens_and_provider_exception_terminal(tmp_path):
    auth = auth_for("calibration", auth_id="error")
    reg = registry(tmp_path, [auth])
    provider = MockProvider(error=RuntimeError("offline mock failure"))
    with pytest.raises(HARD, match="provider exception") as stopped:
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "error", [], "calibration", provider)
    assert provider.calls == 1 and stopped.value.ledger[0]["terminal"]
    assert stopped.value.ledger[0]["error"] == "offline mock failure"


def test_invalid_usage_attempted_once_and_preserved(tmp_path):
    auth = auth_for("calibration", auth_id="usage")
    reg = registry(tmp_path, [auth])
    provider = MockProvider(bad_usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 3})
    with pytest.raises(HARD, match="usage") as stopped:
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "usage", [], "calibration", provider)
    assert provider.calls == 1 and stopped.value.ledger[0]["usage"]["total_tokens"] == 3
    assert stopped.value.ledger[0]["raw_response"]


@pytest.mark.parametrize("stage_cost,cumulative,match", [(0.000001, 7.5, "stage cost"), (0.5, 0.000001, "global cumulative")])
def test_stage_and_cumulative_cost_ceiling(tmp_path, stage_cost, cumulative, match):
    auth = auth_for("calibration", stage_cost=stage_cost, cumulative=cumulative, auth_id="cost")
    reg = registry(tmp_path, [auth])
    with pytest.raises(HARD, match=match) as stopped:
        execute_stage(CONFIG_DATA, SCHEDULE, reg, "cost", [], "calibration", MockProvider())
    assert len(stopped.value.ledger) == 1 and stopped.value.ledger[0]["terminal"]


def test_authorization_hash_registry_and_stage_drift_stop(tmp_path):
    auth = auth_for("calibration", auth_id="cal")
    reg = registry(tmp_path, [auth])
    ledger = execute_stage(CONFIG_DATA, SCHEDULE, reg, "cal", [], "calibration", MockProvider())
    registry_doc = load(reg)
    registry_doc["authorizations"]["cal"]["sha256"] = "0" * 64
    write_json(reg, registry_doc)
    with pytest.raises(HARD, match="registry"):
        validate_ledger(SCHEDULE, ledger, reg)
    changed = deepcopy(auth); changed["authorized_stage"] = "development_acquisition"
    with pytest.raises(HARD, match="stage not authorized"):
        validate_authorization(CONFIG_DATA, changed, "0" * 64, "calibration")


def test_closed_preflight_zero_provider_model_paid_calls():
    calls = 0
    def provider(_):
        nonlocal calls
        calls += 1
    with pytest.raises(HARD, match="forbids"):
        run_local(CONFIG_DATA, provider)
    assert calls == 0
    if (ROOT / CONFIG_DATA["schedule_binding"]["path"]).exists():
        result = run_local(CONFIG_DATA)
        assert [result[k] for k in ("network_calls", "provider_calls", "model_calls", "qwen_calls", "paid_api_calls")] == [0] * 5
