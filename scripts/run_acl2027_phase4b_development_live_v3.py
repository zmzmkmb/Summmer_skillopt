#!/usr/bin/env python3
"""Versioned Phase 4B execution after the zero-call v2 local-runner closure."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_phase4b_development_live_v2 as live
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter

V2 = ROOT / "artifacts/acl2027_phase4b_development_live_v2"
WRAPPER = Path(__file__).resolve()
_base_bindings = live.bindings

live.VERSION = 3
live.AUTH_ID = "phase4b-development-live-v3"
live.RECEIPT = ROOT / "configs/acl2027/phase4b_development_user_authorization_receipt_v3.json"
live.ARTIFACT = ROOT / "artifacts/acl2027_phase4b_development_live_v3"
live.AUTH = live.ARTIFACT / "authorization_open.json"
live.REGISTRY = live.ARTIFACT / "authorization_registry.json"
live.STARTS = live.ARTIFACT / "request_start_ledger.json"
live.LEDGER = live.ARTIFACT / "ledger.json"
live.AUDIT = live.ARTIFACT / "run_audit.json"
live.CLOSURE = live.ARTIFACT / "authorization_closure.json"


def bindings() -> dict[str, str]:
    values = _base_bindings()
    values.update({
        "wrapper_sha256": live.sha256_file(WRAPPER),
        "prior_v2_closure_sha256": live.sha256_file(V2 / "authorization_closure.json"),
        "prior_v2_correction_sha256": live.sha256_file(V2 / "provider_call_correction_v2_1.json"),
    })
    return values


live.bindings = bindings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = {"rows": len(live.preflight()), "bindings": bindings(), "network_calls": 0}
    elif args.command == "authorize":
        result = live.authorize()
    elif args.command == "audit":
        result = live.audit()
    elif args.command == "close":
        result = live.close("operator_close")
    else:
        try:
            provider = QwenTokenPlanProviderAdapter(live.load(live.AUTH))
            result = {"rows": len(live.execute(provider)), "closure": live.close("completed_exact_100")}
        except Exception as exc:
            if live.AUTH.exists() and not live.CLOSURE.exists():
                live.close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
