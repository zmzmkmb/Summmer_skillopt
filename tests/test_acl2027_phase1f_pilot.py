"""Contracts for the immutable Phase 1F pilot preflight."""
from __future__ import annotations

import json

from scripts.validate_acl2027_phase1f_pilot import CONFIG_PATH, preflight


def test_phase1f_preflight_freezes_data_and_two_call_smoke():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    result = preflight(config)
    assert result["checks"]["immutable_input_hashes"] is True
    assert result["checks"]["two_smoke_calls"] is True
    assert result["checks"]["batch_review_required"] is True


def test_phase1f_has_no_fixed_cny_ceiling_and_no_formal_scaling():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    result = preflight(config)
    assert result["checks"]["no_fixed_cny_ceiling"] is True
    assert result["checks"]["formal_scaling_disabled"] is True
    assert config["triage_actions"] == ["accept", "reject", "abstain"]
