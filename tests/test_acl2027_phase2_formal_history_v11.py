from pathlib import Path


def test_v11_preflight_and_authorization_boundary(tmp_path, monkeypatch):
    import scripts.run_acl2027_phase2_formal_history_v11 as module

    artifact = tmp_path / "artifact"
    monkeypatch.setattr(module, "CONFIG", tmp_path / "preflight.json")
    monkeypatch.setattr(module, "AUTH", tmp_path / "authorization.json")
    monkeypatch.setattr(module, "ARTIFACT", artifact)
    monkeypatch.setattr(module, "SCHEDULE", artifact / "schedule.json")
    monkeypatch.setattr(module, "MANIFEST", artifact / "manifest.json")
    monkeypatch.setattr(module, "REGISTRY", artifact / "registry.json")
    monkeypatch.setattr(module, "LEDGER", artifact / "ledger.json")
    monkeypatch.setattr(module, "PACING", artifact / "pacing.json")
    monkeypatch.setattr(module, "CANDIDATES", artifact / "candidates.json")
    monkeypatch.setattr(module, "AUDIT", artifact / "audit.json")
    monkeypatch.setattr(module, "CLOSURE", artifact / "closure.json")
    monkeypatch.setattr(module, "REPORT", tmp_path / "report.md")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-v11-key")

    manifest = module.prepare()
    assert manifest["request_count"] == 160
    assert manifest["family_counts"] == {family: 32 for family in module.FAMILIES}
    _, rows = module.validate_preflight()
    assert len({row["request_hash"] for row in rows}) == 160
    assert all("max_tokens" not in row["canonical_request_body"] for row in rows)

    auth = module.open_auth()
    assert auth["authorized_stage"] == "formal_history"
    assert auth["authorized_calls"] == 160
    assert auth["forbidden_stages"] == ["probe", "held_out", "formal_scaling"]
    assert module.validate_auth()[0]["formal_scaling_allowed"] is False
