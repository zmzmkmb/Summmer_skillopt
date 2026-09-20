import copy
import json

from scripts.run_acl2027_tracegraph_tg6_repaired_local_execution_preflight_v1 import CONFIG, validate


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_repaired_execution_scope_is_closed_and_fully_bound():
    config = load_config()
    assert validate(config) == []
    assert config["episode_count"] == 40
    assert config["max_retries"] == 0
    assert config["execution_authorized"] is False
    assert config["official_source_fallback_allowed"] is False
    assert config["derived_gamefile_manifest_enforced"] is True


def test_repaired_execution_scope_rejects_authorization_or_retry_drift():
    config = load_config()
    authorized = copy.deepcopy(config)
    authorized["execution_authorized"] = True
    assert "execution_authorized must be false" in validate(authorized)
    retried = copy.deepcopy(config)
    retried["max_retries"] = 1
    assert "exact repaired local episode scope mismatch" in validate(retried)


def test_repaired_execution_scope_rejects_official_source_fallback():
    config = load_config()
    config["official_source_fallback_allowed"] = True
    assert "official_source_fallback_allowed must be false" in validate(config)
