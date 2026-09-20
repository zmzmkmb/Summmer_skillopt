"""Contracts for the no-paid Phase 1C proxy reconciliation analysis."""
from __future__ import annotations

import json

from scripts.analyze_acl2027_searchqa_phase1c import CONFIG_PATH, ROOT, analyze


def test_phase1c_is_explicitly_no_paid_and_no_network():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["execution"]["paid_api_allowed"] is False
    assert config["execution"]["formal_scaling_allowed"] is False
    assert config["execution"]["network_calls_allowed"] is False
    assert config["diagnostics"]["development_eligible"] == []


def test_phase1c_inputs_have_expected_immutable_shapes():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    result = analyze(config)
    assert result["phase1b"]["total_calls"] == 2448
    assert result["phase1b"]["evaluation_calls"] == 2352
    assert result["phase1b"]["guard_probe_calls"] == 96
    assert result["phase0n"]["rows"] == 160
    assert all(row["n_pairs"] == 336 for row in result["phase1b"]["comparisons"])


def test_phase1c_preserves_held_out_integrity():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    result = analyze(config)
    assert result["analysis"] == "descriptive_only_held_out_and_immutable_summary"
    assert result["interpretation"]["held_out_tuning"] is False
    assert result["interpretation"]["development_eligible_evidence"] == []
