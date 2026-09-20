from __future__ import annotations

import json
from pathlib import Path

from scripts.run_acl2027_tracegraph_tg6_repaired_local_execution_runner_v4 import (
    CONFIG,
    validate_v4,
)


def test_repair_v2_runner_v4_is_exactly_bound_to_current_preflight():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert validate_v4(config) == []
    assert config["parent_scope_config"].endswith("tracegraph_tg6_repaired_local_execution_preflight_v2.json")
    assert config["pddl_repair_manifest"].endswith("tracegraph_tg6_pddl_derived_repair_v2/repair_manifest.json")
    assert "pending" not in config["pddl_repair_manifest"]
    assert "pending" not in config["derived_gamefile_root"]


def test_repair_v2_runner_v4_output_is_preserved_after_execution():
    root = Path(__file__).resolve().parents[1]
    result_path = root / "artifacts/acl2027_tracegraph_tg6_repaired_local_execution_runner_v4/result.json"
    manifest_path = root / "artifacts/acl2027_tracegraph_tg6_repaired_local_execution_runner_v4/run_manifest.json"
    assert result_path.is_file()
    assert manifest_path.is_file()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["task_count"] == 40
    assert result["episodes_started"] == 40
    assert result["episodes_completed"] == 40
    assert result["hard_invariant_violation"] is None
