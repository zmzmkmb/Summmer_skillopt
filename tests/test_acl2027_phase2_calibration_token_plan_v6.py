from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_acl2027_phase2_calibration_token_plan_v6 import (
    HardStop,
    execute_calibration,
    required_bindings,
    sha256_file,
    validate_execution_preflight,
)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def authorization() -> dict[str, object]:
    return {
        "authorization_id": "phase2-calibration-token-plan-v6-test",
        "status": "open",
        "bindings": required_bindings(),
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
        "request_interval_seconds": 1.0,
        "retries": 0,
        "max_tokens_present": False,
        "formal_scaling_allowed": False,
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "forbidden_stages": ["development_acquisition", "formal_history", "probe", "held_out", "formal_scaling"],
    }


def registry(tmp_path: Path) -> tuple[Path, str]:
    auth = tmp_path / "authorization.json"
    write(auth, authorization())
    auth_hash = sha256_file(auth)
    registry_path = tmp_path / "registry.json"
    write(registry_path, {"authorizations": {"phase2-calibration-token-plan-v6-test": {"path": "authorization.json", "sha256": auth_hash}}})
    return registry_path, "phase2-calibration-token-plan-v6-test"


def provider(body: dict[str, object]) -> dict[str, object]:
    assert body["model_id"] == "qwen3.7-plus" and body["temperature"] == 0 and "max_tokens" not in body
    return {"content": "ok", "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}, "request_id": "mock", "raw_provider_response": {"mock": True}}


def test_execution_preflight_is_closed() -> None:
    config = validate_execution_preflight()
    assert all(value is False for value in config["execution"].values())


def test_complete_60_call_mock_lifecycle(tmp_path: Path) -> None:
    registry_path, auth_id = registry(tmp_path)
    ledger = tmp_path / "ledger.json"
    records = execute_calibration(registry_path, auth_id, ledger, provider)
    assert len(records) == len({record["logical_call_id"] for record in records}) == 60
    assert all(not record["terminal"] for record in records)


def test_interruption_resumes_exact_prefix_without_duplicates(tmp_path: Path) -> None:
    registry_path, auth_id = registry(tmp_path)
    ledger = tmp_path / "ledger.json"
    with pytest.raises(KeyboardInterrupt):
        execute_calibration(registry_path, auth_id, ledger, provider, interrupt_after=10)
    records = execute_calibration(registry_path, auth_id, ledger, provider)
    assert len(records) == len({record["logical_call_id"] for record in records}) == 60


def test_terminal_provider_error_is_durable_and_not_resumable(tmp_path: Path) -> None:
    registry_path, auth_id = registry(tmp_path)
    ledger = tmp_path / "ledger.json"

    def fail(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("provider failed")

    with pytest.raises(HardStop):
        execute_calibration(registry_path, auth_id, ledger, fail)
    records = json.loads(ledger.read_text(encoding="utf-8"))
    assert len(records) == 1 and records[0]["terminal"] is True
    with pytest.raises(HardStop, match="terminal ledger is not resumable"):
        execute_calibration(registry_path, auth_id, ledger, provider)
