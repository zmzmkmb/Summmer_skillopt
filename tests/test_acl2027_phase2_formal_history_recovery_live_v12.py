from __future__ import annotations

import json
import os

import pytest


def setup_live(module, tmp_path, monkeypatch):
    key = "test-v12-key"
    artifact = tmp_path / "live"
    monkeypatch.setenv("DASHSCOPE_API_KEY", key)
    monkeypatch.setattr(module, "AUTH", tmp_path / "authorization.json")
    monkeypatch.setattr(module, "ARTIFACT", artifact)
    monkeypatch.setattr(module, "REGISTRY", artifact / "registry.json")
    monkeypatch.setattr(module, "LEDGER", artifact / "ledger.json")
    monkeypatch.setattr(module, "PACING", artifact / "pacing.json")
    monkeypatch.setattr(module, "CANDIDATES", artifact / "candidates.json")
    monkeypatch.setattr(module, "AUDIT", artifact / "audit.json")
    monkeypatch.setattr(module, "CLOSURE", artifact / "closure.json")
    monkeypatch.setattr(module, "REPORT", tmp_path / "report.md")
    monkeypatch.setattr(module, "INTERVAL_NS", 0)
    auth = module.authorization_template(key)
    module.write(module.AUTH, auth)
    rel = os.path.relpath(module.AUTH, module.REGISTRY.parent).replace("\\", "/")
    module.write(module.REGISTRY, {"schema_version": 12, "authorizations": {module.AUTH_ID: {"path": rel, "sha256": module.sha256_file(module.AUTH)}}})
    return artifact


class MockProvider:
    def __init__(self, module, fail_at=None):
        config = module.load(module.CONFIG)
        gold = {row["task_id"]: row for row in module.load(module.ROOT / config["trusted_evaluation"]["combined_gold_path"])}
        self.rows = module.load(module.RECOVERY_SCHEDULE)["schedule"]
        self.gold = gold
        self.calls = 0
        self.fail_at = fail_at

    def __call__(self, body):
        self.calls += 1
        if self.fail_at == self.calls:
            raise TimeoutError("mock timeout")
        planned = self.rows[self.calls - 1]
        private = self.gold[planned["task_id"]]
        answer = (private.get("answers") or [private.get("answer")])[0]
        return {"content": " " * self.calls + json.dumps({"answer": answer}), "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}


def test_v12_full_mock_lifecycle_and_materialization(tmp_path, monkeypatch):
    import scripts.run_acl2027_phase2_formal_history_recovery_live_v12 as module
    setup_live(module, tmp_path, monkeypatch)
    provider = MockProvider(module)
    rows = module.execute(provider)
    result = module.audit()
    assert len(rows) == provider.calls == 128
    assert result["coverage_passed"] is True
    assert result["independent_verified_supports"]["fact_retrieval"] == 28
    assert all(result["independent_verified_supports"][family] == 32 for family in ("attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference"))


def test_v12_exact_prefix_resume(tmp_path, monkeypatch):
    import scripts.run_acl2027_phase2_formal_history_recovery_live_v12 as module
    setup_live(module, tmp_path, monkeypatch)
    provider = MockProvider(module)
    with pytest.raises(KeyboardInterrupt):
        module.execute(provider, interrupt_after=17)
    assert len(module.load(module.LEDGER)) == len(module.load(module.PACING)) == 17
    module.execute(provider)
    assert provider.calls == 128


def test_v12_terminal_and_ambiguous_start_refuse_resume(tmp_path, monkeypatch):
    import scripts.run_acl2027_phase2_formal_history_recovery_live_v12 as module
    setup_live(module, tmp_path, monkeypatch)
    provider = MockProvider(module, fail_at=1)
    with pytest.raises(module.HardStop, match="mock timeout"):
        module.execute(provider)
    with pytest.raises(module.HardStop, match="terminal ledger"):
        module.execute(provider)
    module.LEDGER.unlink()
    with pytest.raises(module.HardStop, match="ambiguous request start"):
        module.execute(MockProvider(module))
