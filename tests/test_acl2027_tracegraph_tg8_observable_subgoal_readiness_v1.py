from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_readiness_v1_ubuntu_wsl import (
    CONFIG,
    validate_config,
)
from scripts import run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3 as selector_v3


def test_readiness_config_is_closed_and_bound():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    # This test is intentionally static: validate_config must not instantiate
    # ALFWorld or call any provider/model/network endpoint.
    assert config["selector"].endswith("selector_v3.py")
    assert config["selector_audit"].endswith("selector_audit_v3/selector_audit.json")
    assert validate_config(config) == []
    assert config["task_count"] == 30
    assert config["selector_probe_count"] == 120
    assert config["episodes_run"] == 0
    assert config["actions_taken"] == 0
    assert config["execution_authorized"] is False
    assert config["readiness_only"] is True


def test_readiness_runner_imports_v3_and_requires_index_for_validation():
    from scripts import run_acl2027_tracegraph_tg8_observable_subgoal_readiness_v1_ubuntu_wsl as runner

    assert runner.selector is selector_v3
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "validate_selector_transition(transition, index=index)" in source


def test_readiness_artifact_is_immutable_passed_evidence():
    root = Path(__file__).resolve().parents[1]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    output = root / config["readiness_output"]
    assert output.is_file()
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["status"] == "passed"
    assert artifact["task_count"] == 30
    assert artifact["passed_task_count"] == 30
    assert artifact["selector_probe_count"] == 120
    assert artifact["episodes_run"] == 0
    assert artifact["actions_taken"] == 0
    assert artifact["execution_authorized"] is False
    assert artifact["readiness_only"] is True
