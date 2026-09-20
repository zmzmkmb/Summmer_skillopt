from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_acl2027_phase2_calibration_v6 import build_audit, close_authorization
from scripts.run_acl2027_phase2_calibration_token_plan_v6 import execute_calibration, load, sha256_file, validate_authorization
from scripts.run_acl2027_phase2_calibration_token_plan_live_v6 import (
    AUTH,
    REGISTRY,
    HardStop,
    PersistentRequestStartPacer,
    stable,
    validate_live_authorization,
)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class FakeClock:
    def __init__(self, now_ns: int = 10_000_000_000):
        self.now_ns = now_ns
        self.sleeps: list[float] = []

    def time_ns(self) -> int:
        return self.now_ns

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now_ns += round(seconds * 1_000_000_000)


def test_pacer_enforces_one_second_and_persists_before_transport(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    starts = tmp_path / "starts.json"
    clock = FakeClock()
    seen: list[int] = []

    def provider(_: dict[str, object]) -> dict[str, object]:
        persisted = json.loads(starts.read_text(encoding="utf-8"))
        seen.append(len(persisted))
        return {"ok": True}

    pacer = PersistentRequestStartPacer(provider, ledger, starts, clock_ns=clock.time_ns, sleeper=clock.sleep)
    body = {"model_id": "qwen3.7-plus", "temperature": 0, "messages": []}
    pacer(body)
    write(ledger, [{"done": 1}])
    clock.now_ns += 100_000_000
    pacer(body)
    events = json.loads(starts.read_text(encoding="utf-8"))
    assert seen == [1, 2]
    assert events[1]["request_started_at_unix_ns"] - events[0]["request_started_at_unix_ns"] == 1_000_000_000
    assert clock.sleeps == [0.9]
    assert events[0]["request_body_sha256"] == stable(body)


def test_pacer_enforces_spacing_after_restart(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    starts = tmp_path / "starts.json"
    clock = FakeClock()
    body = {"model_id": "qwen3.7-plus", "temperature": 0, "messages": []}
    PersistentRequestStartPacer(lambda _: {}, ledger, starts, clock_ns=clock.time_ns, sleeper=clock.sleep)(body)
    write(ledger, [{"done": 1}])
    clock.now_ns += 250_000_000
    PersistentRequestStartPacer(lambda _: {}, ledger, starts, clock_ns=clock.time_ns, sleeper=clock.sleep)(body)
    assert clock.sleeps == [0.75]


def test_ambiguous_started_request_is_not_retried(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    starts = tmp_path / "starts.json"
    write(starts, [{"sequence": 1}])
    pacer = PersistentRequestStartPacer(lambda _: {}, ledger, starts)
    with pytest.raises(HardStop, match="ambiguous started request"):
        pacer({"model_id": "qwen3.7-plus", "temperature": 0, "messages": []})


def test_closed_authorization_remains_auditable_but_cannot_reactivate() -> None:
    auth = load(AUTH)
    validate_authorization(auth, sha256_file(AUTH))
    assert auth["authorized_calls"] == auth["stage_call_ceiling"] == auth["max_provider_attempts"] == 60
    assert auth["max_tokens_present"] is False and auth["retries"] == 0
    assert auth["formal_scaling_allowed"] is False
    assert auth["user_authorization"]["user_cny_limit_requested"] is False
    assert auth["repository_safety_ceiling_not_user_budget"] is True
    with pytest.raises(HardStop, match="missing or closed"):
        validate_live_authorization(REGISTRY, auth["authorization_id"])


def test_mock_60_call_paced_audit_and_irrevocable_closure(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    auth_path = tmp_path / "authorization.json"
    auth_path.write_bytes(AUTH.read_bytes())
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    registry = artifact / "authorization_registry.json"
    write(registry, {"schema_version": 6, "authorizations": {auth["authorization_id"]: {"path": "../authorization.json", "sha256": sha256_file(auth_path)}}})
    ledger = artifact / "ledger.json"
    starts = artifact / "request_start_ledger.json"
    clock = FakeClock()

    def provider(_: dict[str, object]) -> dict[str, object]:
        return {
            "content": json.dumps({"answer": "mock"}),
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            "request_id": "mock",
            "raw_provider_response": {"mock": True},
        }

    paced = PersistentRequestStartPacer(provider, ledger, starts, clock_ns=clock.time_ns, sleeper=clock.sleep)
    records = execute_calibration(registry, auth["authorization_id"], ledger, paced)
    assert len(records) == 60
    audit = build_audit(auth_path, artifact)
    assert audit["status"] == "completed" and audit["provider_attempts"] == 60
    assert audit["request_start_pacing_valid"] is True
    closed = close_authorization(auth_path, artifact)
    assert closed["authorization_closed"] is True
    assert json.loads(registry.read_text(encoding="utf-8"))["authorizations"] == {}
