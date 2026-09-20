"""Zero-call preflight for the immutable Phase 1F pilot config."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase1f_real_cross_task_triage_pilot_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight(config: dict[str, Any]) -> dict[str, Any]:
    execution = config["execution"]
    assert config["phase"] == "1F"
    assert execution["default_mode"] == "dry-run"
    assert execution["formal_scaling_allowed"] is False
    assert execution["paid_api_allowed"] is True
    assert execution["batch_requires_separate_review"] is True
    assert execution["stop_on_missing_usage"] is True
    assert execution["stop_on_unknown_provider_error"] is True
    assert "no fixed" in execution["cost_accounting"].lower()
    assert config["triage_actions"] == ["accept", "reject", "abstain"]
    assert config["discard"] == "not emitted by validation gate"
    assert config["pairing"]["smoke_logical_calls"] == 2
    for name, task in config["data"].items():
        manifest = ROOT / task["source_manifest"]
        payload_key = "payload_csv" if name == "OfficeQA" else "payload_dataset"
        hash_key = "payload_csv_sha256" if name == "OfficeQA" else "payload_dataset_sha256"
        payload = ROOT / task[payload_key]
        assert sha256_file(manifest) == task["source_manifest_sha256"]
        assert sha256_file(payload) == task[hash_key]
        assert task["smoke_ids"]
    return {
        "analysis": "phase1f_config_preflight_only_no_network_no_model_calls",
        "config_sha256": sha256_file(CONFIG_PATH),
        "api_key_present": bool(os.environ.get(execution["api_key_env"])),
        "checks": {
            "immutable_input_hashes": True,
            "dry_run_default": True,
            "batch_review_required": True,
            "no_fixed_cny_ceiling": True,
            "two_smoke_calls": True,
            "formal_scaling_disabled": True,
        },
        "decision": "ready_for_two_call_bounded_smoke" if os.environ.get(execution["api_key_env"]) else "blocked_missing_api_key",
    }


if __name__ == "__main__":
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    print(json.dumps(preflight(config), indent=2, ensure_ascii=True))
