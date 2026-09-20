from scripts.run_acl2027_tracegraph_tg1_skillbank_construction_preflight_v1 import CONFIG, validate_config
import json


def test_construction_protocol_is_disabled_and_train_only():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_config(config) == []
    assert config["construction_enabled"] is False
    assert config["allowed_split"] == "train"


def test_construction_protocol_rejects_runtime_privilege_leak():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["runtime_forbidden_fields"].remove("planner_state")
    assert "runtime forbidden fields are incomplete" in validate_config(config)
