"""Tests for the zero-provider Phase 1Z adjudication and closure."""
from __future__ import annotations

import json

from scripts.run_acl2027_phase1z_final import DEFAULT_CONFIG, build_closure, write_artifact


def test_phase1z_closes_inconclusively_without_provider_execution():
    result = build_closure()
    assert result["decision"] == "inconclusive_without_phase1z_provider_execution"
    assert result["phase1_closed"] is True
    assert result["phase1z_scientifically_executable"] is False
    assert result["provider_attempts"] == 0
    assert result["network_calls"] == 0
    assert result["checks"]["complete_family_type_coverage"] is False
    assert result["checks"]["no_evaluation_leakage"] is True


def test_phase1z_observations_and_minimum_calls_are_frozen():
    observed = build_closure()["observed"]
    assert observed["verified_trajectories"] == 8
    assert observed["typed_candidates"] == 3
    assert observed["covered_skill_families"] == 3
    assert observed["required_skill_families"] == 5
    assert observed["missing_skill_families"] == ["entity_bridge", "relation_inference"]
    assert observed["theoretical_minimum_additional_successful_history_calls"] == 2
    assert observed["exact_guaranteed_additional_calls"] is None
    assert observed["currently_authorized_additional_calls"] == 0


def test_phase1z_writes_validator_compatible_manifest(tmp_path):
    output = tmp_path / "phase1z"
    manifest = write_artifact(DEFAULT_CONFIG, output)
    result = json.loads((output / "run_01.json").read_text(encoding="utf-8"))
    assert manifest["expected_runs"] == manifest["available_runs"] == 1
    assert manifest["complete_grid"] is True
    assert manifest["provider_attempts"] == 0
    assert result["scientific_fingerprint"]
