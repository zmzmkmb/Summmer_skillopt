"""Contracts for the no-network Phase 1D triage development pilot."""
from __future__ import annotations

import json

from scripts.analyze_acl2027_phase1d_triage import CONFIG_PATH, analyze


def test_phase1d_is_fabricated_development_only():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["execution"]["paid_api_allowed"] is False
    assert config["execution"]["formal_scaling_allowed"] is False
    assert config["execution"]["network_calls_allowed"] is False
    assert config["execution"]["evidence_kind"] == "fabricated_development_only"
    assert config["protocol"]["decision_actions"] == ["accept", "reject", "abstain"]
    assert config["protocol"]["discard_is_gate_action"] is False


def test_phase1d_has_exact_prior_by_evidence_grid():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    result = analyze(config)
    assert result["protocol"]["n_cases"] == 144
    assert result["protocol"]["prior_types"] == ["contextual", "copied-global", "global-only"]
    assert result["protocol"]["evidence_regimes"] == ["conflicted", "sparse", "sufficient"]


def test_triage_reduces_unsafe_deployment_and_retains_candidates():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    result = analyze(config)
    binary = next(row for row in result["policies"] if row["policy"] == "binary_proxy_gate")
    triage = next(row for row in result["policies"] if row["policy"] == "triage_gate")
    assert binary["unsafe_deployments"] == 16
    assert triage["unsafe_deployments"] == 0
    assert triage["helpful_deployments"] == 16
    assert triage["actions"]["abstain"] == 64
    assert triage["retained_candidates"] == 144
    assert result["interpretation"]["real_task_accuracy_claim"] is False
