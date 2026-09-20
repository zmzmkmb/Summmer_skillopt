#!/usr/bin/env python3
"""Read-only cost-status correction for the closed Phase 2 v6 calibration audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/acl2027_phase2_calibration_live_v6"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_supplement(artifact: Path = ARTIFACT) -> dict[str, Any]:
    audit_path = artifact / "calibration_audit.json"
    closure_path = artifact / "authorization_closure.json"
    ledger_path = artifact / "ledger.json"
    pacing_path = artifact / "request_start_ledger.json"
    audit = load(audit_path)
    closure = load(closure_path)
    records = load(ledger_path)
    starts = load(pacing_path)
    if closure.get("status") != "closed_terminal_hard_stop" or closure.get("qwen_authorization_open") is not False:
        raise RuntimeError("v6 authorization is not closed terminal")
    if len(records) != len(starts) or len(records) != 1 or not records[0].get("terminal"):
        raise RuntimeError("v6 terminal ledger shape drift")
    if records[0].get("usage") is not None:
        raise RuntimeError("v6 correction only applies to unknown usage")
    if audit.get("provider_accepted_calls") != 0 or audit.get("provider_attempts") != 1:
        raise RuntimeError("v6 original audit attempt drift")
    return {
        "schema_version": "6.1",
        "status": "terminal_hard_stop",
        "supersedes_cost_fields_only": "calibration_audit.json",
        "original_audit_sha256": sha256_file(audit_path),
        "authorization_closure_sha256": sha256_file(closure_path),
        "ledger_sha256": sha256_file(ledger_path),
        "pacing_ledger_sha256": sha256_file(pacing_path),
        "provider_attempts": 1,
        "provider_accepted_calls": 0,
        "usage": None,
        "cost_status": "unknown_usage_terminal_hard_stop",
        "exact_local_cost_cny": None,
        "lower_bound_known_usage_cost_cny": 0.0,
        "authorization_closed": True,
        "later_stages_authorized": False,
        "correction_reason": "HTTP 401 supplied no usage metadata; summing the empty known-usage subset yields only a lower bound, not an exact cost.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    supplement = build_supplement()
    if args.write:
        path = ARTIFACT / "calibration_audit_v6_1.json"
        path.write_text(json.dumps(supplement, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(supplement, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
