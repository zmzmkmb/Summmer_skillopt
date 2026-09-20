"""Tests for the TraceGraph TG1 ALFWorld SkillBank preflight."""
from __future__ import annotations

import copy

from scripts.run_acl2027_tracegraph_tg1_skillbank_preflight_v1 import load_config, validate_config


def test_tg1_skillbank_preflight_config_is_zero_network_and_train_only():
    assert validate_config(load_config()) == []


def test_tg1_rejects_evaluation_split_source():
    config = copy.deepcopy(load_config())
    config["source_contract"]["allowed_relative_root"] = "json_2.1.1/valid_seen"
    errors = validate_config(config)
    assert "source_contract.allowed_relative_root must be json_2.1.1/train" in errors


def test_tg1_rejects_privileged_runtime_payload():
    config = copy.deepcopy(load_config())
    config["skillbank_contract"]["runtime_payload_forbidden"].remove("planner_state")
    errors = validate_config(config)
    assert "skillbank_contract must forbid raw or privileged expert payloads at runtime" in errors


def test_tg1_rejects_phase0_to_phase6_reuse():
    config = copy.deepcopy(load_config())
    config["contamination_isolation"]["phase0_to_phase6_status"] = "reusable"
    errors = validate_config(config)
    assert "contamination_isolation.phase0_to_phase6_status must be frozen-read-only" in errors