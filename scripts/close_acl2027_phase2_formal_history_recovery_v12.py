#!/usr/bin/env python3
"""Close and report the Phase 2 v12 recovery authorization."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_acl2027_phase2_formal_history_recovery_live_v12 as live
from scripts.materialize_acl2027_phase2_candidates_recovery_v12 import RecoveryMaterializationError

AUTH = live.AUTH
REGISTRY = live.REGISTRY
AUDIT = live.AUDIT
CLOSURE = live.CLOSURE
REPORT = live.REPORT


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def close_authorization() -> dict[str, Any]:
    if not AUTH.is_file() or not REGISTRY.is_file():
        raise live.HardStop("v12 authorization lifecycle is absent")
    registry = load(REGISTRY)
    item = registry.get("authorizations", {}).get(live.AUTH_ID)
    if not item or (REGISTRY.parent / item["path"]).resolve() != AUTH.resolve() or item.get("sha256") != live.sha256_file(AUTH):
        raise live.HardStop("v12 closure authorization binding drift")
    try:
        result = live.audit()
    except RecoveryMaterializationError as exc:
        records = live.load(live.LEDGER) if live.LEDGER.exists() else []
        starts = live.load(live.PACING) if live.PACING.exists() else []
        schedule = live.load(live.RECOVERY_SCHEDULE)["schedule"]
        live.validate_prefix(records, starts, schedule, live.sha256_file(AUTH))
        duplicate_hashes = Counter(row["raw_response_sha256"] for row in records)
        duplicate_groups = sorted(
            {digest: count for digest, count in duplicate_hashes.items() if count > 1}.items()
        )
        auth = load(AUTH)
        manifest = live.load(live.MANIFEST)
        result = {
            "schema_version": 12,
            "status": "terminal_hard_stop",
            "terminal_reason": str(exc),
            "provider_attempts": len(records),
            "completed_calls": sum(row.get("status") == "completed" for row in records),
            "unique_logical_calls": len({row["logical_call_id"] for row in records}),
            "terminal_rows": sum(bool(row.get("terminal")) for row in records),
            "input_tokens": sum(live.usage(row)["input_tokens"] for row in records),
            "output_tokens": sum(live.usage(row)["output_tokens"] for row in records),
            "total_tokens": sum(live.usage(row)["total_tokens"] for row in records),
            "exact_local_cost_cny": live.cost(records),
            "retries": sum(row.get("retries", 0) for row in records),
            "duplicates": len(records) - len({row["logical_call_id"] for row in records}),
            "duplicate_response_hash_groups": [
                {"raw_response_sha256": digest, "count": count}
                for digest, count in duplicate_groups
            ],
            "max_tokens_present": any(row.get("max_tokens_present") for row in records),
            "model_ids": sorted({row["raw_provider_response"]["model"] for row in records}),
            "temperature": auth["temperature"],
            "request_start_pacing_valid": all(
                b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= live.INTERVAL_NS
                for a, b in zip(starts, starts[1:])
            ),
            "ledger_hash_chain_valid": True,
            "exact_prefix_valid": True,
            "aggregate_fingerprint": manifest["aggregate_fingerprint"],
            "coverage_status": "not_reached_materialization_hard_stop",
            "coverage_passed": False,
            "independent_verified_supports": {},
            "network_calls": len(records),
            "provider_calls": len(records),
            "model_calls": len(records),
            "paid_api_calls": len(records),
            "probe_calls": 0,
            "held_out_calls": 0,
            "formal_scaling_calls": 0,
            "authorization_closed": True,
        }
    if result["status"] not in {"completed", "terminal_hard_stop"}:
        raise live.HardStop("v12 incomplete authorization cannot be closed as terminal")
    write(AUDIT, result)
    closure = {
        "schema_version": 12,
        "status": "closed_completed" if result["status"] == "completed" else "closed_terminal_hard_stop",
        "authorization_id": live.AUTH_ID,
        "authorization_sha256": live.sha256_file(AUTH),
        "audit_sha256": live.sha256_file(AUDIT),
        "provider_attempts": result["provider_attempts"],
        "later_stages_authorized": False,
        "probe_authorized": False,
        "held_out_authorized": False,
        "formal_scaling_authorized": False,
    }
    write(CLOSURE, closure)
    auth_path = os.path.relpath(AUTH, REGISTRY.parent).replace("\\", "/")
    write(REGISTRY, {"schema_version": 12, "authorizations": {}, "closed_authorizations": {live.AUTH_ID: {"path": auth_path, "sha256": live.sha256_file(AUTH)}}})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Phase 2 Formal History Recovery Live v12\n\n```json\n" + json.dumps(result, indent=2, sort_keys=True) + "\n```\n\nProbe, held-out, later stages, and formal scaling remain unauthorized.\n", encoding="utf-8")
    return {"audit": result, "closure": closure}


if __name__ == "__main__":
    print(json.dumps(close_authorization(), indent=2, sort_keys=True))
