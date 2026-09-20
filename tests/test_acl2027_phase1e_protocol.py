"""Contracts for the frozen Phase 1E cross-task protocol audit."""
from __future__ import annotations

import json

from scripts.validate_acl2027_phase1e_protocol import CONFIG_PATH, audit


def test_phase1e_is_protocol_only_and_no_paid():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    result = audit(config)
    assert result["analysis"] == "protocol_audit_only_no_network"
    assert result["checks"]["no_paid_or_network"] is True
    assert result["checks"]["payloads_ready"] is False


def test_phase1e_protects_searchqa_heldout_and_adds_two_tasks():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    result = audit(config)
    assert result["checks"]["three_task_families"] is True
    assert result["checks"]["new_task_families"] is True
    assert result["checks"]["searchqa_held_out_protected"] is True


def test_phase1e_keeps_discard_outside_gate():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    result = audit(config)
    assert result["checks"]["three_way_actions"] is True
    assert result["decision"] == "protocol_frozen_pending_payload_materialization_and_provider_review"

