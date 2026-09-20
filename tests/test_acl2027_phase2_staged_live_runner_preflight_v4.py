from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.acl2027_phase2_provider_adapter_v3 import ProviderAdapterError, QwenProviderAdapter
from scripts.acl2027_phase2_response_verifier_v3 import VerificationError, load_gold, sha256_file, stable
from scripts.analyze_acl2027_phase2_probe_v3 import ProbeAnalysisError, build_probe_audit
from scripts.materialize_acl2027_phase2_candidates_v3 import MaterializationError, build_candidate_artifact
from scripts.acl2027_phase2_integrity_v4 import IntegrityError, manifest_payload, stable as integrity_stable, verify_integrity
from scripts.build_acl2027_phase2_v4_manifest import BINDING_PATHS, build_manifest
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import (
    AUTH, CONFIG, MANIFEST, FAMILIES, HardStop, execute_stage, load, run_local, schedule_rows,
    validate_authorization, validate_prefix,
)

CONFIG_DATA = load(CONFIG)
SCHEDULE = schedule_rows()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def integrity_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    for relative in BINDING_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(relative), target)
    manifest = build_manifest(root=root)
    manifest_path = root / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
    write(manifest_path, manifest)
    config = deepcopy(CONFIG_DATA)
    config["integrity_root"]["expected_aggregate_fingerprint"] = manifest["aggregate_fingerprint"]
    config_path = root / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
    write(config_path, config)
    return root, config_path, manifest_path


def auth(stage: str, ident: str, calls: int | None = None) -> dict:
    item = load(AUTH)
    n = calls if calls is not None else CONFIG_DATA["stages"][stage]
    item.update({"authorization_id": ident, "status": "open", "authorized_stage": stage,
                 "authorized_calls": n, "stage_call_ceiling": n,
                 "stage_cost_ceiling_cny": CONFIG_DATA["cost_control"]["stage_ceilings_cny"][stage],
                 "cumulative_cost_ceiling_cny": 7.5,
                 "paid_api_allowed": True, "provider_calls_allowed": True,
                 "qwen_authorization_open": True})
    return item


def registry(tmp_path: Path, auths: list[dict]) -> Path:
    entries = {}
    for item in auths:
        p = tmp_path / f"{item['authorization_id']}.json"
        write(p, item)
        entries[item["authorization_id"]] = {"path": p.name, "sha256": sha256_file(p)}
    p = tmp_path / "registry.json"
    write(p, {"schema_version": 3, "authorizations": entries})
    return p


class MockProvider:
    def __init__(self, *, error: Exception | None = None, invalid_usage: bool = False, tokens: tuple[int, int] = (10, 5)):
        self.calls = 0
        self.error = error
        self.invalid_usage = invalid_usage
        self.tokens = tokens
        self.gold = {}
        for part in ("calibration", "development_acquisition", "formal_history", "probe", "held_out"):
            path = Path("data/searchqa_phase2_verified") / f"{part}.json"
            self.gold.update({row["task_id"]: row for row in load(path)})

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus" and body["temperature"] == 0 and "max_tokens" not in body
        if self.error:
            raise self.error
        if self.invalid_usage:
            return {"content": "{bad", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 3}}
        row = self.gold[body["task_id"]]
        answer = (row.get("answers") or [row.get("answer")])[0]
        # Preserve the verified answer while giving each provider attempt a distinct raw response identity.
        input_tokens, output_tokens = self.tokens
        return {"content": json.dumps({"answer": answer + (" " * self.calls)}), "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens}, "request_id": f"mock-{self.calls}"}


def run_stage(tmp_path, ledger_path, stage, old, provider=None, interrupt_after=None):
    item = auth(stage, f"auth-{stage}")
    reg = registry(tmp_path, old + [item])
    result = execute_stage(CONFIG_DATA, reg, item["authorization_id"], ledger_path, provider or MockProvider(), stage, interrupt_after=interrupt_after)
    return result, old + [item]


def complete_history(tmp_path):
    ledger = tmp_path / "ledger.json"
    old = []
    for stage in ("calibration", "development_acquisition", "formal_history"):
        _, old = run_stage(tmp_path, ledger, stage, old)
    return ledger, old


def test_frozen_v2_schedule_is_staged_bijection_and_costs() -> None:
    assert len(SCHEDULE) == 710
    assert [r["staged_execution_index"] for r in SCHEDULE] == list(range(1, 711))
    assert [r["partition"] for r in SCHEDULE] == [s for s, n in CONFIG_DATA["stages"].items() for _ in range(n)]
    assert len({r["logical_call_id"] for r in SCHEDULE}) == 710
    assert len({r["request_hash"] for r in SCHEDULE}) == 710


def test_closed_default_cli_missing_auth_and_key_are_zero_calls() -> None:
    result = run_local()
    assert [result[k] for k in ("network_calls", "provider_calls", "model_calls", "qwen_calls", "paid_api_calls")] == [0] * 5


def test_v4_manifest_recomputes_all_disk_bindings_and_root(tmp_path) -> None:
    root, config_path, manifest_path = integrity_fixture(tmp_path)
    config, manifest = verify_integrity(config_path, manifest_path, root=root)
    assert config["integrity_root"]["expected_aggregate_fingerprint"] == manifest["aggregate_fingerprint"]
    assert set(manifest["bindings"]) == set(BINDING_PATHS)
    assert all(len(binding["sha256"]) == 64 for binding in manifest["bindings"].values())


def test_v4_rejects_noncanonical_65_character_sha256(tmp_path) -> None:
    root, config_path, manifest_path = integrity_fixture(tmp_path)
    manifest = load(manifest_path)
    manifest["bindings"]["runner_source"]["sha256"] += "0"
    manifest["aggregate_fingerprint"] = integrity_stable(manifest_payload(manifest))
    write(manifest_path, manifest)
    with pytest.raises(IntegrityError, match="non-canonical SHA-256"):
        verify_integrity(config_path, manifest_path, root=root)


@pytest.mark.parametrize("binding", ["runner_source", "test_source"])
def test_v4_rejects_bound_source_byte_drift(tmp_path, binding) -> None:
    root, config_path, manifest_path = integrity_fixture(tmp_path)
    path = root / BINDING_PATHS[binding]
    path.write_bytes(path.read_bytes() + b"\n# drift\n")
    with pytest.raises(IntegrityError, match="disk hash drift"):
        verify_integrity(config_path, manifest_path, root=root)


def test_v4_rejects_manifest_field_and_aggregate_tampering(tmp_path) -> None:
    root, config_path, manifest_path = integrity_fixture(tmp_path)
    manifest = load(manifest_path)
    manifest["unexpected"] = True
    write(manifest_path, manifest)
    with pytest.raises(IntegrityError, match="field drift"):
        verify_integrity(config_path, manifest_path, root=root)

    root, config_path, manifest_path = integrity_fixture(tmp_path / "aggregate")
    manifest = load(manifest_path)
    manifest["aggregate_fingerprint"] = "0" * 64
    write(manifest_path, manifest)
    with pytest.raises(IntegrityError, match="aggregate fingerprint drift"):
        verify_integrity(config_path, manifest_path, root=root)


def test_v4_frozen_root_rejects_attacker_rehashed_manifest(tmp_path) -> None:
    root, config_path, manifest_path = integrity_fixture(tmp_path)
    runner_path = root / BINDING_PATHS["runner_source"]
    runner_path.write_bytes(runner_path.read_bytes() + b"\n# attacker rewrite\n")
    manifest = load(manifest_path)
    manifest["bindings"]["runner_source"]["sha256"] = sha256_file(runner_path)
    manifest["aggregate_fingerprint"] = integrity_stable(manifest_payload(manifest))
    write(manifest_path, manifest)
    with pytest.raises(IntegrityError, match="frozen integrity root mismatch"):
        verify_integrity(config_path, manifest_path, root=root)


def test_v4_integrity_failure_precedes_provider_invocation() -> None:
    calls = 0

    def provider(_body):
        nonlocal calls
        calls += 1
        return {}

    config = deepcopy(CONFIG_DATA)
    config["integrity_root"]["expected_aggregate_fingerprint"] = "0" * 64
    with pytest.raises(HardStop, match="preflight config hash drift"):
        execute_stage(config, Path("unused-registry.json"), "unused", Path("unused-ledger.json"), provider, "calibration")
    assert calls == 0


def test_crash_resume_after_durable_append_has_no_duplicate(tmp_path) -> None:
    ledger = tmp_path / "ledger.json"
    item = auth("calibration", "cal")
    reg = registry(tmp_path, [item])
    provider = MockProvider()
    with pytest.raises(KeyboardInterrupt):
        execute_stage(CONFIG_DATA, reg, "cal", ledger, provider, "calibration", interrupt_after=17)
    assert len(load(ledger)) == 17 and provider.calls == 17
    result = execute_stage(CONFIG_DATA, reg, "cal", ledger, provider, "calibration")
    assert len(result) == provider.calls == 60
    assert len({r["logical_call_id"] for r in result}) == 60


def test_incomplete_stage_and_ceiling_are_hard_stops(tmp_path) -> None:
    ledger = tmp_path / "ledger.json"
    item = auth("calibration", "cal", 59)
    reg = registry(tmp_path, [item])
    with pytest.raises(HardStop, match="ceiling"):
        execute_stage(CONFIG_DATA, reg, "cal", ledger, MockProvider(), "calibration")


def test_cross_authorization_resume_keeps_old_hash_and_quota(tmp_path) -> None:
    ledger, old = complete_history(tmp_path)
    rows = load(ledger)
    assert len(rows) == 230 and len({r["authorization_sha256"] for r in rows}) == 3
    assert sum(r["authorization_id"] == "auth-development_acquisition" for r in rows) == 10


def test_materializer_recomputes_verdict_and_rejects_forged_coverage(tmp_path) -> None:
    ledger, old = complete_history(tmp_path)
    rows = load(ledger)
    artifact = build_candidate_artifact(rows, SCHEDULE, CONFIG_DATA)
    assert artifact["passed"] and artifact["independent_verified_supports"] == {f: 32 for f in FAMILIES}
    forged = deepcopy(artifact)
    for row in forged["trajectories"][:40]:
        row["verifier_confirmed_success"] = True
    forged["trajectories"] = forged["trajectories"][:40]
    forged["passed"] = True
    with pytest.raises(HardStop, match="coverage artifact"):
        path = tmp_path / "forged.json"; write(path, forged)
        execute_stage(CONFIG_DATA, registry(tmp_path, old + [auth("probe", "probe")]), "probe", ledger_path=tmp_path / "ledger.json", provider=MockProvider(), stage="probe", coverage_path=path)


def test_wrong_gold_parser_family_duplicate_and_leakage_fail(tmp_path) -> None:
    ledger, _ = complete_history(tmp_path)
    rows = load(ledger)
    broken = deepcopy(rows[-1]); broken["raw_response"] = "{bad"; rows[-1] = broken
    with pytest.raises(MaterializationError):
        build_candidate_artifact(rows, SCHEDULE, CONFIG_DATA)
    with pytest.raises(ProbeAnalysisError):
        build_probe_audit([], SCHEDULE, {"passed": True}, "x" * 64, CONFIG_DATA)
    with pytest.raises(Exception):
        load_gold("held_out")


def test_probe_audit_is_deterministic_and_forged_passed_rejected(tmp_path) -> None:
    ledger, old = complete_history(tmp_path)
    coverage = build_candidate_artifact(load(ledger), SCHEDULE, CONFIG_DATA)
    coverage_path = tmp_path / "coverage.json"; write(coverage_path, coverage)
    provider = MockProvider(); probe_auth = auth("probe", "probe")
    reg = registry(tmp_path, old + [probe_auth])
    execute_stage(CONFIG_DATA, reg, "probe", ledger, provider, "probe", coverage_path=coverage_path)
    rows = load(ledger)
    audit = build_probe_audit(rows, SCHEDULE, coverage, sha256_file(coverage_path), CONFIG_DATA)
    assert audit["probe_rows"] == 160
    forged = {"schema_version": 3, "passed": True,
              "coverage_artifact_sha256": sha256_file(coverage_path),
              "probe_ledger_sha256": audit["probe_ledger_sha256"]}
    assert forged != audit
    with pytest.raises(HardStop, match="probe audit"):
        audit_path = tmp_path / "forged-audit.json"; write(audit_path, forged)
        held = auth("held_out", "held")
        execute_stage(CONFIG_DATA, registry(tmp_path, old + [probe_auth, held]), "held", ledger, MockProvider(), "held_out", coverage_path=coverage_path, probe_audit_path=audit_path)


def test_provider_exception_and_invalid_usage_once_terminal(tmp_path) -> None:
    for index, provider in enumerate((MockProvider(error=RuntimeError("offline")), MockProvider(invalid_usage=True))):
        ledger = tmp_path / f"terminal-{index}.json"
        item = auth("calibration", "x" + str(id(provider)))
        with pytest.raises(HardStop):
            execute_stage(CONFIG_DATA, registry(tmp_path, [item]), item["authorization_id"], ledger, provider, "calibration")
        assert provider.calls == 1 and load(ledger)[0]["terminal"]


def test_full_mock_lifecycle_is_710_rows_five_authorizations(tmp_path) -> None:
    ledger, old = complete_history(tmp_path)
    coverage = build_candidate_artifact(load(ledger), SCHEDULE, CONFIG_DATA)
    cp = tmp_path / "coverage.json"; write(cp, coverage)
    probe = auth("probe", "probe"); execute_stage(CONFIG_DATA, registry(tmp_path, old + [probe]), "probe", ledger, MockProvider(), "probe", coverage_path=cp)
    audit = build_probe_audit(load(ledger), SCHEDULE, coverage, sha256_file(cp), CONFIG_DATA)
    ap = tmp_path / "audit.json"; write(ap, audit)
    held = auth("held_out", "held"); result = execute_stage(CONFIG_DATA, registry(tmp_path, old + [probe, held]), "held", ledger, MockProvider(), "held_out", coverage_path=cp, probe_audit_path=ap)
    assert len(result) == 710 and len({r["authorization_sha256"] for r in result}) == 5


def test_handwritten_forged_coverage_with_recomputed_file_hash_is_rejected(tmp_path) -> None:
    ledger, old = complete_history(tmp_path)
    forged = {
        "schema_version": 3,
        "artifact_type": "acl2027_phase2_candidate_materialization_v3",
        "passed": True,
        "trajectories": [
            {"family": family, "verifier_confirmed_success": True, "support_id": f"fake-{family}-{index}"}
            for family in FAMILIES for index in range(8)
        ],
    }
    path = tmp_path / "attacker-rehashed-coverage.json"
    write(path, forged)
    attacker_hash = sha256_file(path)
    assert len(attacker_hash) == 64
    with pytest.raises(HardStop, match="coverage artifact"):
        probe = auth("probe", "probe-forged")
        execute_stage(CONFIG_DATA, registry(tmp_path, old + [probe]), probe["authorization_id"], ledger, MockProvider(), "probe", coverage_path=path)


def test_wrong_gold_yields_coverage_incomplete_not_method_failure(tmp_path) -> None:
    ledger, _ = complete_history(tmp_path)
    rows = load(ledger)
    family = FAMILIES[0]
    changed = 0
    for record in rows:
        if record["partition"] == "formal_history" and record["skill_family"] == family and changed < 25:
            record["raw_response"] = json.dumps({"answer": f"certainly-wrong-{changed}"})
            record["raw_response_sha256"] = stable(record["raw_response"])
            changed += 1
    artifact = build_candidate_artifact(rows, SCHEDULE, CONFIG_DATA)
    assert changed == 25
    assert artifact["coverage_status"] == "coverage-incomplete"
    assert artifact["passed"] is False and artifact["method_failure"] is False
    assert artifact["independent_verified_supports"][family] == 7


def test_family_duplicate_and_source_binding_drifts_are_rejected(tmp_path) -> None:
    ledger, _ = complete_history(tmp_path)
    rows = load(ledger)
    family_drift = deepcopy(rows)
    family_drift[-1]["skill_family"] = FAMILIES[0]
    with pytest.raises(MaterializationError, match="binding drift"):
        build_candidate_artifact(family_drift, SCHEDULE, CONFIG_DATA)
    duplicate = deepcopy(rows)
    history = [index for index, row in enumerate(duplicate) if row["partition"] == "formal_history"]
    duplicate[history[1]]["raw_response"] = duplicate[history[0]]["raw_response"]
    duplicate[history[1]]["raw_response_sha256"] = duplicate[history[0]]["raw_response_sha256"]
    with pytest.raises(MaterializationError, match="duplicate identity"):
        build_candidate_artifact(duplicate, SCHEDULE, CONFIG_DATA)
    drifted_config = deepcopy(CONFIG_DATA)
    drifted_config["trusted_evaluation"]["verifier_source_sha256"] = "0" * 64
    with pytest.raises(MaterializationError, match="source hash drift"):
        build_candidate_artifact(rows, SCHEDULE, drifted_config)


def test_gold_access_boundaries_reject_history_probe_and_heldout_leakage() -> None:
    assert load_gold("formal_history")[0] and load_gold("probe")[0]
    for forbidden in ("calibration", "development_acquisition", "held_out"):
        with pytest.raises(VerificationError, match="forbidden"):
            load_gold(forbidden)


def test_authorization_exact_bindings_route_and_switches(tmp_path) -> None:
    item = auth("calibration", "bound")
    path = tmp_path / "bound.json"
    write(path, item)
    validate_authorization(CONFIG_DATA, item, sha256_file(path), "calibration")
    for mutation in (
        lambda value: value["bindings"].update(schedule_sha256="0" * 64),
        lambda value: value.update(endpoint_route="wrong"),
        lambda value: value.update(max_tokens_present=True),
        lambda value: value.update(formal_scaling_allowed=True),
        lambda value: value.update(stage_cost_ceiling_cny=999),
    ):
        changed = deepcopy(item)
        mutation(changed)
        with pytest.raises(HardStop):
            validate_authorization(CONFIG_DATA, changed, "0" * 64, "calibration")


def test_ledger_hash_chain_and_terminal_attempt_are_not_resumable(tmp_path) -> None:
    ledger = tmp_path / "ledger.json"
    item = auth("calibration", "chain")
    reg = registry(tmp_path, [item])
    provider = MockProvider()
    with pytest.raises(KeyboardInterrupt):
        execute_stage(CONFIG_DATA, reg, "chain", ledger, provider, "calibration", interrupt_after=2)
    rows = load(ledger)
    rows[0]["request_id"] = "tampered"
    write(ledger, rows)
    with pytest.raises(HardStop, match="hash chain"):
        validate_prefix(SCHEDULE, rows, reg)

    terminal_ledger = tmp_path / "terminal.json"
    failing = MockProvider(error=RuntimeError("offline"))
    with pytest.raises(HardStop):
        execute_stage(CONFIG_DATA, reg, "chain", terminal_ledger, failing, "calibration")
    with pytest.raises(HardStop, match="terminal ledger"):
        execute_stage(CONFIG_DATA, reg, "chain", terminal_ledger, failing, "calibration")
    assert failing.calls == 1


def test_stage_and_cumulative_cost_ceilings_persist_terminal_ledger(tmp_path) -> None:
    for index, ceiling_key in enumerate(("stage_cost_ceiling_cny", "cumulative_cost_ceiling_cny")):
        item = auth("calibration", f"cost-{index}")
        item[ceiling_key] = 0.000001
        ledger = tmp_path / f"cost-ledger-{index}.json"
        provider = MockProvider(tokens=(1, 1))
        with pytest.raises(HardStop, match="cost ceiling"):
            execute_stage(CONFIG_DATA, registry(tmp_path, [item]), item["authorization_id"], ledger, provider, "calibration")
        rows = load(ledger)
        assert provider.calls == 1 and rows[-1]["terminal"] and rows[-1]["raw_response"]


def test_closed_adapter_and_missing_key_never_call_transport() -> None:
    key_reads = 0
    transports = 0

    def key_source():
        nonlocal key_reads
        key_reads += 1
        return None

    def transport(*_args):
        nonlocal transports
        transports += 1
        return {}

    with pytest.raises(ProviderAdapterError, match="activation denied"):
        QwenProviderAdapter(load(AUTH), key_source=key_source, transport=transport)
    assert key_reads == transports == 0
    opened = auth("calibration", "missing-key")
    with pytest.raises(ProviderAdapterError, match="key missing"):
        QwenProviderAdapter(opened, key_source=key_source, transport=transport)
    assert key_reads == 1 and transports == 0


def test_crash_resume_in_every_stage_is_exact_prefix_and_zero_duplicate(tmp_path) -> None:
    ledger = tmp_path / "all-stage-ledger.json"
    auths = []
    coverage_path = tmp_path / "coverage.json"
    audit_path = tmp_path / "probe-audit.json"
    expected_end = 0
    for stage in ("calibration", "development_acquisition", "formal_history", "probe", "held_out"):
        item = auth(stage, f"crash-{stage}")
        auths.append(item)
        reg = registry(tmp_path, auths)
        provider = MockProvider()
        kwargs = {}
        if stage in ("probe", "held_out"):
            kwargs["coverage_path"] = coverage_path
        if stage == "held_out":
            kwargs["probe_audit_path"] = audit_path
        stage_size = CONFIG_DATA["stages"][stage]
        interrupt_at = expected_end + max(1, stage_size // 2)
        with pytest.raises(KeyboardInterrupt):
            execute_stage(CONFIG_DATA, reg, item["authorization_id"], ledger, provider, stage, interrupt_after=interrupt_at, **kwargs)
        execute_stage(CONFIG_DATA, reg, item["authorization_id"], ledger, provider, stage, **kwargs)
        expected_end += stage_size
        rows = load(ledger)
        assert len(rows) == expected_end and provider.calls == stage_size
        assert len({row["logical_call_id"] for row in rows}) == expected_end
        if stage == "formal_history":
            write(coverage_path, build_candidate_artifact(rows, SCHEDULE, CONFIG_DATA))
        if stage == "probe":
            coverage = load(coverage_path)
            write(audit_path, build_probe_audit(rows, SCHEDULE, coverage, sha256_file(coverage_path), CONFIG_DATA))
    assert expected_end == 710
    assert len({row["authorization_sha256"] for row in load(ledger)}) == 5
