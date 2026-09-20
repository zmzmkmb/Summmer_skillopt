import copy
import json

from scripts.run_acl2027_tracegraph_tg6_pddl_derived_repair_v2_preflight import (
    FORMAL_MANIFEST,
    PENDING_ZERO_STEP,
    validate_source_zero_step,
)
from scripts.run_acl2027_tracegraph_tg6_repaired_local_execution_preflight_v2 import (
    CONFIG,
    validate,
)


def test_existing_zero_step_evidence_is_passed_and_zero_action():
    result = json.loads(PENDING_ZERO_STEP.read_text(encoding="utf-8"))
    validate_source_zero_step(result)
    assert result["passed_task_count"] == 40
    assert result["actions_taken"] == 0


def test_formal_repair_manifest_is_finalized():
    manifest = json.loads(FORMAL_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed_zero_network_textworld_reset_preflight"
    assert manifest["task_count"] == 40
    assert manifest["repaired_task_count"] == 10


def test_execution_preflight_is_closed_and_bound():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate(config) == []
    assert config["execution_authorized"] is False
    assert config["episode_count"] == 40
    assert config["max_retries"] == 0


def test_execution_preflight_rejects_authorization_drift():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    changed = copy.deepcopy(config)
    changed["execution_authorized"] = True
    assert "execution_authorized must be false" in validate(changed)
