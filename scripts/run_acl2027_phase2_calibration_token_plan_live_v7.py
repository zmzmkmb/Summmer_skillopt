#!/usr/bin/env python3
"""Live-only orchestration for the authorized Phase 2 Token Plan calibration."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_token_plan_provider_adapter_v6 import QwenTokenPlanProviderAdapter
from scripts.audit_acl2027_phase2_calibration_v7 import close_authorization
from scripts.run_acl2027_phase2_calibration_token_plan_v6 import (
    HardStop,
    execute_calibration,
    load,
    resolve_registry,
    sha256_file,
    stable,
)

AUTH = ROOT / "configs/acl2027/phase2_calibration_live_authorization_v7.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_calibration_live_v7"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING_LEDGER = ARTIFACT / "request_start_ledger.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
AUDIT_SOURCE = ROOT / "scripts/audit_acl2027_phase2_calibration_v7.py"
LIVE_SOURCE = Path(__file__).resolve()
INTERVAL_NS = 1_000_000_000


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_live_authorization(registry_path: Path, authorization_id: str) -> dict[str, Any]:
    registry = resolve_registry(registry_path)
    if authorization_id not in registry:
        raise HardStop("v7 live authorization missing or closed")
    auth = registry[authorization_id][0]
    expected = {
        "live_orchestrator_sha256": sha256_file(LIVE_SOURCE),
        "audit_source_sha256": sha256_file(AUDIT_SOURCE),
    }
    if auth.get("live_execution_bindings") != expected:
        raise HardStop("v7 live execution source binding drift")
    if auth.get("user_authorization", {}).get("scope") != "phase2_v7_calibration_only":
        raise HardStop("v7 user authorization scope drift")
    if auth.get("user_authorization", {}).get("not_inherited_by_later_stages") is not True:
        raise HardStop("v7 later-stage prohibition drift")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key or auth.get("credential_sha256") != hashlib.sha256(key.encode("utf-8")).hexdigest():
        raise HardStop("v7 credential binding drift")
    return auth


class PersistentRequestStartPacer:
    """Persist request starts before transport and enforce spacing across restarts."""

    def __init__(
        self,
        provider: Callable[[dict[str, Any]], dict[str, Any]],
        ledger_path: Path,
        pacing_ledger_path: Path,
        *,
        interval_ns: int = INTERVAL_NS,
        clock_ns: Callable[[], int] = time.time_ns,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.provider = provider
        self.ledger_path = ledger_path
        self.pacing_ledger_path = pacing_ledger_path
        self.interval_ns = interval_ns
        self.clock_ns = clock_ns
        self.sleeper = sleeper

    def _wait_until_allowed(self, last_start_ns: int | None) -> int:
        while True:
            now = self.clock_ns()
            if last_start_ns is None or now - last_start_ns >= self.interval_ns:
                return now
            self.sleeper((self.interval_ns - (now - last_start_ns)) / 1_000_000_000)

    def __call__(self, body: dict[str, Any]) -> dict[str, Any]:
        records = load(self.ledger_path) if self.ledger_path.exists() else []
        starts = load(self.pacing_ledger_path) if self.pacing_ledger_path.exists() else []
        if len(starts) != len(records):
            raise HardStop("v7 ambiguous started request; automatic retry forbidden", records)
        last_start_ns = starts[-1]["request_started_at_unix_ns"] if starts else None
        started_ns = self._wait_until_allowed(last_start_ns)
        event = {
            "sequence": len(starts) + 1,
            "request_body_sha256": stable(body),
            "request_started_at_unix_ns": started_ns,
            "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None,
        }
        event["start_entry_sha256"] = stable(event)
        starts.append(event)
        write_json_atomic(self.pacing_ledger_path, starts)
        return self.provider(body)


def execute_live(authorization_id: str) -> dict[str, Any]:
    if CLOSURE.exists():
        raise HardStop("v7 live authorization already closed")
    auth = validate_live_authorization(REGISTRY, authorization_id)
    adapter = QwenTokenPlanProviderAdapter(auth)
    paced_provider = PersistentRequestStartPacer(adapter, LEDGER, PACING_LEDGER)
    try:
        records = execute_calibration(REGISTRY, authorization_id, LEDGER, paced_provider)
    except KeyboardInterrupt:
        raise
    except BaseException:
        close_authorization(AUTH, ARTIFACT)
        raise
    audit = close_authorization(AUTH, ARTIFACT)
    return {"status": "calibration-complete-authorization-closed", "rows": len(records), "audit": audit}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("preflight")
    live = sub.add_parser("execute")
    live.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    if args.command in (None, "preflight"):
        auth = load(AUTH)
        validate_live_authorization(REGISTRY, auth["authorization_id"])
        print(json.dumps({"status": "live-preflight-passed-open", "network_calls": 0, "provider_calls": 0}, indent=2))
        return 0
    print(json.dumps(execute_live(args.authorization_id), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
