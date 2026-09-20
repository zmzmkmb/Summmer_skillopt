from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_acl2027_phase2_development_acquisition_v10 import (
    AUTHORIZATION_ID,
    PersistentRequestStartPacer,
    build_schedule,
    execute_requests,
    load,
    stable,
)


class FakeClock:
    def __init__(self) -> None:
        self.now_ns = 10_000_000_000

    def time_ns(self) -> int:
        return self.now_ns

    def sleep(self, seconds: float) -> None:
        self.now_ns += round(seconds * 1_000_000_000)


def test_schedule_has_exact_scope_and_json_contract() -> None:
    rows = build_schedule()
    assert len(rows) == 10
    assert len({row["logical_call_id"] for row in rows}) == 10
    assert len({row["request_hash"] for row in rows}) == 10
    assert {row["skill_family"] for row in rows} == {
        "fact_retrieval",
        "attribute_comparison",
        "bridge_attribute_comparison",
        "entity_bridge",
        "relation_inference",
    }
    for family in {row["skill_family"] for row in rows}:
        assert sum(row["skill_family"] == family for row in rows) == 2
    for row in rows:
        body = row["canonical_request_body"]
        assert row["logical_call_id"].startswith("phase2-v10:development_acquisition:")
        assert row["request_hash"] == stable(body)
        assert body["response_format"] == {"type": "json_object"}
        assert body["development_outputs_not_formal_history"] is True
        assert '{"answer":"<short answer>"}' in body["messages"][0]["content"]
        assert "max_tokens" not in body


def test_mock_requests_are_paced_and_exact_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_acl2027_phase2_development_acquisition_v10 as module

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    auth_path = tmp_path / "authorization.json"
    auth = module.build_authorization("test-key")
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    registry = artifact / "authorization_registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 10,
                "authorizations": {
                    AUTHORIZATION_ID: {
                        "path": "../authorization.json",
                        "sha256": module.sha256_file(auth_path),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    ledger = artifact / "ledger.json"
    starts = artifact / "request_start_ledger.json"
    clock = FakeClock()

    def provider(_: dict[str, object]) -> dict[str, object]:
        return {
            "content": '{"answer":"mock"}',
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            "request_id": "mock",
            "raw_provider_response": {"mock": True},
        }

    monkeypatch.setattr(module, "AUTH", auth_path)
    monkeypatch.setattr(module, "REGISTRY", registry)
    paced = PersistentRequestStartPacer(
        provider,
        ledger,
        starts,
        clock_ns=clock.time_ns,
        sleeper=clock.sleep,
    )
    records = execute_requests(paced, registry_path=registry, ledger_path=ledger)
    assert len(records) == 10
    assert len(load(starts)) == 10
    assert all(
        b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= 1_000_000_000
        for a, b in zip(load(starts), load(starts)[1:])
    )


def test_interruption_resumes_without_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_acl2027_phase2_development_acquisition_v10 as module

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    auth_path = tmp_path / "authorization.json"
    auth_path.write_text(json.dumps(module.build_authorization("test-key")), encoding="utf-8")
    registry = artifact / "authorization_registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 10,
                "authorizations": {
                    AUTHORIZATION_ID: {
                        "path": "../authorization.json",
                        "sha256": module.sha256_file(auth_path),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    ledger = artifact / "ledger.json"

    def provider(_: dict[str, object]) -> dict[str, object]:
        return {
            "content": '{"answer":"mock"}',
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            "raw_provider_response": {"mock": True},
        }

    monkeypatch.setattr(module, "AUTH", auth_path)
    monkeypatch.setattr(module, "REGISTRY", registry)
    with pytest.raises(KeyboardInterrupt):
        execute_requests(provider, registry_path=registry, ledger_path=ledger, interrupt_after=4)
    records = execute_requests(provider, registry_path=registry, ledger_path=ledger)
    assert len(records) == len({row["logical_call_id"] for row in records}) == 10
