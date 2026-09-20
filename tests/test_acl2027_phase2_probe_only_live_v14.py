from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.acl2027_phase2_response_verifier_v3 import load_gold
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop
from scripts import run_acl2027_phase2_probe_only_live_v14 as live


class MockProvider:
    def __init__(self, error: Exception | None = None):
        self.calls = 0
        self.error = error
        self.gold, _ = load_gold("probe")

    def __call__(self, body):
        self.calls += 1
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert "max_tokens" not in body
        assert body["response_format"] == {"type": "json_object"}
        if self.error:
            raise self.error
        row = self.gold[body["task_id"]]
        answer = (row.get("answers") or [row.get("answer")])[0]
        return {"content": json.dumps({"answer": answer}), "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "request_id": f"mock-{self.calls}"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts" / "v14"
    monkeypatch.setattr(live, "AUTH", tmp_path / "configs" / "auth.json")
    monkeypatch.setattr(live, "ARTIFACT", artifact)
    monkeypatch.setattr(live, "REGISTRY", artifact / "authorization_registry.json")
    monkeypatch.setattr(live, "LEDGER", artifact / "ledger.json")
    monkeypatch.setattr(live, "PACING", artifact / "request_start_ledger.json")
    monkeypatch.setattr(live, "PROBE_AUDIT", artifact / "probe_audit.json")
    monkeypatch.setattr(live, "RUN_AUDIT", artifact / "run_audit.json")
    monkeypatch.setattr(live, "CLOSURE", artifact / "authorization_closure.json")
    monkeypatch.setattr(live, "INTERVAL_NS", 0)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-secret")
    live.open_authorization()
    return artifact


def test_v14_mock_full_probe_and_audit(isolated) -> None:
    provider = MockProvider()
    rows = live.execute(provider)
    result = live.audit()
    assert len(rows) == provider.calls == 160
    assert result["provider_attempts"] == result["unique_logical_requests"] == 160
    assert result["duplicates"] == result["retries"] == 0
    assert result["total_tokens"] == 1920
    assert result["max_tokens_present"] is False
    assert result["probe_gate_passed"] is True
    closure = live.close("completed_exact_160")
    assert closure["status"] == "closed"
    assert closure["held_out_calls"] == closure["formal_scaling_calls"] == 0


def test_v14_exact_prefix_resume_has_no_duplicate(isolated) -> None:
    provider = MockProvider()
    with pytest.raises(KeyboardInterrupt):
        live.execute(provider, interrupt_after=17)
    assert len(live.load(live.LEDGER)) == 17
    rows = live.execute(provider)
    assert len(rows) == provider.calls == 160
    assert len({row["logical_call_id"] for row in rows}) == 160


def test_v14_provider_error_is_terminal_and_not_resumable(isolated) -> None:
    provider = MockProvider(error=RuntimeError("offline"))
    with pytest.raises(HardStop):
        live.execute(provider)
    assert provider.calls == 1
    assert live.load(live.LEDGER)[0]["terminal"] is True
    with pytest.raises(HardStop, match="terminal ledger"):
        live.execute(MockProvider())


def test_v14_ambiguous_request_start_refuses_retry(isolated) -> None:
    live.write(live.PACING, [{"sequence": 1}])
    with pytest.raises(HardStop, match="ambiguous request start"):
        live.execute(MockProvider())


def test_v14_authorization_forbids_later_stages(monkeypatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-secret")
    auth = live.authorization_template("mock-secret")
    assert auth["authorized_stage"] == "probe"
    assert auth["authorized_calls"] == auth["max_provider_attempts"] == 160
    assert auth["stage_cost_ceiling_cny"] == auth["cumulative_cost_ceiling_cny"] == 7.5
    assert auth["user_authorization"]["held_out_authorized"] is False
    assert auth["user_authorization"]["later_stages_authorized"] is False
    assert auth["formal_scaling_allowed"] is False
