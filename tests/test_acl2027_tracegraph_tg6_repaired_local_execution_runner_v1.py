import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg6_repaired_local_execution_preflight_v1 import CONFIG
from scripts.run_acl2027_tracegraph_tg6_repaired_local_execution_runner_v1 import load_derived_gamefiles, validate_authorized_config


def test_unauthorized_preflight_cannot_run_as_authorized_config():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    errors = validate_authorized_config(config)
    assert "wrong repaired runner phase" in errors
    assert "fresh exact repaired-execution authorization is not bound" in errors


def test_runner_resolves_all_gamefiles_from_frozen_derived_manifest():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    schedule = json.loads(Path(config["heldout_schedule"]).read_text(encoding="utf-8"))
    gamefiles = load_derived_gamefiles(config, schedule["tasks"])
    assert len(gamefiles) == 40
    derived_root = Path(config["derived_gamefile_root"]).resolve()
    assert all(path.resolve().is_relative_to(derived_root) for path in gamefiles.values())


def test_runner_source_has_no_official_data_fallback_or_provider_import():
    source = Path("scripts/run_acl2027_tracegraph_tg6_repaired_local_execution_runner_v1.py").read_text(encoding="utf-8")
    assert "ALFWORLD_DATA" not in source
    assert "requests" not in source
    assert "skillopt.model" not in source
    assert "provider_adapter" not in source
