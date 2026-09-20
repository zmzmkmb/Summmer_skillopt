from __future__ import annotations

import os

import pytest


@pytest.mark.parametrize("status,closed", [("completed", "closed_completed"), ("terminal_hard_stop", "closed_terminal_hard_stop")])
def test_v12_closure_moves_registry(tmp_path, monkeypatch, status, closed):
    import scripts.close_acl2027_phase2_formal_history_recovery_v12 as module

    auth = tmp_path / "authorization.json"
    registry = tmp_path / "live" / "registry.json"
    audit = tmp_path / "live" / "audit.json"
    closure = tmp_path / "live" / "closure.json"
    report = tmp_path / "report.md"
    monkeypatch.setattr(module, "AUTH", auth)
    monkeypatch.setattr(module, "REGISTRY", registry)
    monkeypatch.setattr(module, "AUDIT", audit)
    monkeypatch.setattr(module, "CLOSURE", closure)
    monkeypatch.setattr(module, "REPORT", report)
    module.write(auth, {"authorization_id": module.live.AUTH_ID})
    rel = os.path.relpath(auth, registry.parent).replace("\\", "/")
    module.write(registry, {"schema_version": 12, "authorizations": {module.live.AUTH_ID: {"path": rel, "sha256": module.live.sha256_file(auth)}}})
    monkeypatch.setattr(module.live, "audit", lambda: {"status": status, "provider_attempts": 128 if status == "completed" else 1})
    result = module.close_authorization()
    assert result["closure"]["status"] == closed
    assert module.load(registry)["authorizations"] == {}
    assert module.live.AUTH_ID in module.load(registry)["closed_authorizations"]


def test_v12_closure_refuses_incomplete(tmp_path, monkeypatch):
    import scripts.close_acl2027_phase2_formal_history_recovery_v12 as module

    auth = tmp_path / "authorization.json"
    registry = tmp_path / "registry.json"
    monkeypatch.setattr(module, "AUTH", auth)
    monkeypatch.setattr(module, "REGISTRY", registry)
    module.write(auth, {"authorization_id": module.live.AUTH_ID})
    module.write(registry, {"schema_version": 12, "authorizations": {module.live.AUTH_ID: {"path": auth.name, "sha256": module.live.sha256_file(auth)}}})
    monkeypatch.setattr(module.live, "audit", lambda: {"status": "incomplete", "provider_attempts": 3})
    with pytest.raises(module.live.HardStop, match="incomplete"):
        module.close_authorization()
