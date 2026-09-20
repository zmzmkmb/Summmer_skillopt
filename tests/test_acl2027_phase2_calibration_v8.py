from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.audit_acl2027_phase2_calibration_v8 import build_audit, close_authorization
from scripts.run_acl2027_phase2_calibration_prompt_repair_preflight_v8 import (
    MANIFEST,
    build_manifest,
    build_schedule,
)
from scripts.run_acl2027_phase2_calibration_token_plan_live_v8 import PersistentRequestStartPacer
from scripts.run_acl2027_phase2_calibration_token_plan_v8 import (
    HardStop,
    execute_calibration,
    load,
    required_bindings,
    sha256_file,
    stable,
    validate_execution_preflight,
)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def authorization() -> dict[str, object]:
    key = os.environ.get("DASHSCOPE_API_KEY", "test-key")
    root = Path(__file__).resolve().parents[1]
    return {
        "authorization_id": "phase2-calibration-token-plan-v8-test",
        "status": "open",
        "bindings": required_bindings(),
        "live_execution_bindings": {
            "live_orchestrator_sha256": sha256_file(root / "scripts/run_acl2027_phase2_calibration_token_plan_live_v8.py"),
            "audit_source_sha256": sha256_file(root / "scripts/audit_acl2027_phase2_calibration_v8.py"),
        },
        "credential_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "user_authorization": {"scope": "phase2_v8_calibration_only", "not_inherited_by_later_stages": True},
        "authorized_stage": "calibration",
        "authorized_calls": 60,
        "stage_call_ceiling": 60,
        "max_provider_attempts": 60,
        "stage_cost_ceiling_cny": 0.5,
        "cumulative_cost_ceiling_cny": 0.5,
        "model_id": "qwen3.7-plus",
        "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "retries": 0,
        "max_tokens_present": False,
        "formal_scaling_allowed": False,
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "forbidden_stages": ["development_acquisition", "formal_history", "probe", "held_out", "formal_scaling"],
    }


class FakeClock:
    def __init__(self) -> None:
        self.now_ns = 10_000_000_000

    def time_ns(self) -> int:
        return self.now_ns

    def sleep(self, seconds: float) -> None:
        self.now_ns += round(seconds * 1_000_000_000)


def test_repaired_schedule_has_new_exact_json_contract() -> None:
    rows = build_schedule()
    assert len(rows) == len({row["logical_call_id"] for row in rows}) == len({row["request_hash"] for row in rows}) == 60
    for row in rows:
        body = row["canonical_request_body"]
        assert row["logical_call_id"].startswith("phase2-v8:calibration:")
        assert row["request_hash"] == stable(body)
        assert body["response_format"] == {"type": "json_object"}
        assert body["prompt_template_version"] == "phase2-prompt-v8-exact-json"
        assert '{"answer":"<short answer>"}' in body["messages"][0]["content"]
        assert "no other text" in body["messages"][0]["content"]
        assert "max_tokens" not in body


def test_v8_manifest_and_preflight_are_closed_and_recomputed() -> None:
    assert load(MANIFEST) == build_manifest()
    config = validate_execution_preflight()
    assert all(value is False for value in config["execution"].values())


def test_adapter_forwards_json_object_mode() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, headers: dict[str, str], data: bytes) -> dict[str, object]:
        captured.update(url=url, headers=headers, payload=json.loads(data))
        return {"id": "mock", "choices": [{"message": {"content": '{"answer":"mock"}'}}], "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}

    adapter = QwenTokenPlanProviderAdapter(authorization(), key_source=lambda: "test-key", transport=transport)
    response = adapter(build_schedule()[0]["canonical_request_body"])
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert response["content"] == '{"answer":"mock"}'


def test_complete_mock_lifecycle_is_paced_audited_and_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    auth_path = tmp_path / "authorization.json"
    write(auth_path, authorization())
    auth = load(auth_path)
    registry = artifact / "authorization_registry.json"
    write(registry, {"schema_version": 8, "authorizations": {auth["authorization_id"]: {"path": "../authorization.json", "sha256": sha256_file(auth_path)}}})
    ledger = artifact / "ledger.json"
    starts = artifact / "request_start_ledger.json"
    clock = FakeClock()

    def provider(body: dict[str, object]) -> dict[str, object]:
        assert body["response_format"] == {"type": "json_object"}
        return {"content": '{"answer":"mock"}', "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}, "request_id": "mock", "raw_provider_response": {"mock": True}}

    paced = PersistentRequestStartPacer(provider, ledger, starts, clock_ns=clock.time_ns, sleeper=clock.sleep)
    records = execute_calibration(registry, auth["authorization_id"], ledger, paced)
    assert len(records) == 60
    audit = build_audit(auth_path, artifact)
    assert audit["status"] == "completed" and audit["contract_valid"] == 60
    assert audit["request_start_pacing_valid"] is True
    close_authorization(auth_path, artifact)
    assert load(registry)["authorizations"] == {}


def test_interruption_resumes_exact_prefix_without_duplicates(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    auth_path = tmp_path / "authorization.json"
    write(auth_path, authorization())
    auth = load(auth_path)
    registry = artifact / "authorization_registry.json"
    write(registry, {"schema_version": 8, "authorizations": {auth["authorization_id"]: {"path": "../authorization.json", "sha256": sha256_file(auth_path)}}})
    ledger = artifact / "ledger.json"
    starts = artifact / "request_start_ledger.json"
    clock = FakeClock()

    def provider(_: dict[str, object]) -> dict[str, object]:
        return {"content": '{"answer":"mock"}', "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}, "raw_provider_response": {"mock": True}}

    paced = PersistentRequestStartPacer(provider, ledger, starts, clock_ns=clock.time_ns, sleeper=clock.sleep)
    with pytest.raises(KeyboardInterrupt):
        execute_calibration(registry, auth["authorization_id"], ledger, paced, interrupt_after=10)
    records = execute_calibration(registry, auth["authorization_id"], ledger, paced)
    assert len(records) == len({row["logical_call_id"] for row in records}) == 60
    assert len(load(starts)) == 60


def test_terminal_unknown_usage_is_closed_and_not_resumable(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    auth_path = tmp_path / "authorization.json"
    write(auth_path, authorization())
    auth = load(auth_path)
    registry = artifact / "authorization_registry.json"
    write(registry, {"schema_version": 8, "authorizations": {auth["authorization_id"]: {"path": "../authorization.json", "sha256": sha256_file(auth_path)}}})
    ledger = artifact / "ledger.json"
    starts = artifact / "request_start_ledger.json"

    def fail(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("provider failed")

    paced = PersistentRequestStartPacer(fail, ledger, starts)
    with pytest.raises(HardStop):
        execute_calibration(registry, auth["authorization_id"], ledger, paced)
    audit = build_audit(auth_path, artifact)
    assert audit["status"] == "terminal_hard_stop"
    assert audit["cost_status"] == "unknown_usage_terminal_hard_stop"
    assert audit["exact_local_cost_cny"] is None
    with pytest.raises(HardStop, match="terminal ledger is not resumable"):
        execute_calibration(registry, auth["authorization_id"], ledger, paced)
