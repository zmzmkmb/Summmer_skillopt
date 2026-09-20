#!/usr/bin/env python3
"""Authorization-gated live runner for the exact v19 112-row probe recovery."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.analyze_acl2027_phase2_probe_recovery_v20 import build_probe_audit
from scripts.run_acl2027_phase2_probe_recovery_preflight_v19 import validate as validate_v19

_ENGINE_SPEC = importlib.util.spec_from_file_location(
    "scripts._acl2027_phase2_probe_recovery_engine_v20",
    ROOT / "scripts/run_acl2027_phase2_probe_only_live_v18.py",
)
if _ENGINE_SPEC is None or _ENGINE_SPEC.loader is None:
    raise ImportError("unable to load isolated v20 live-runner engine")
engine = importlib.util.module_from_spec(_ENGINE_SPEC)
sys.modules[_ENGINE_SPEC.name] = engine
_ENGINE_SPEC.loader.exec_module(engine)

VERSION = 20
CALLS = 112
COST_CEILING = 7.5
AUTH_ID = "phase2-probe-recovery-only-v20"

RECEIPT = ROOT / "configs/acl2027/phase2_probe_recovery_user_authorization_receipt_v20.json"
REQUEST = ROOT / "configs/acl2027/phase2_probe_recovery_authorization_request_v20.json"
AUTH = ROOT / "configs/acl2027/phase2_probe_recovery_live_authorization_v20.json"
AUTH_CLOSED = ROOT / "configs/acl2027/phase2_probe_recovery_live_authorization_closed_v20.json"
V19_CONFIG = ROOT / "configs/acl2027/phase2_probe_recovery_preflight_v19.json"
V19_ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19"
V19_MANIFEST = V19_ARTIFACT / "run_manifest.json"
SCHEDULE = V19_ARTIFACT / "probe_recovery_schedule.json"
PRIOR_BUNDLES = V19_ARTIFACT / "prior_bundles.json"
RECOVERY_GOLD = V19_ARTIFACT / "recovery_probe_gold.json"
V18_LEDGER = ROOT / "artifacts/acl2027_phase2_probe_only_live_v18/ledger.json"
V17_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/probe_schedule.json"
CANDIDATE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/combined_candidates_v13.json"
PROVIDER_ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ANALYZER = ROOT / "scripts/analyze_acl2027_phase2_probe_recovery_v20.py"
TEST = ROOT / "tests/test_acl2027_phase2_probe_recovery_live_v20.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20"
PREFLIGHT_AUDIT = ARTIFACT / "zero_network_preflight.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
PROBE_AUDIT = ARTIFACT / "probe_audit.json"
RUN_AUDIT = ARTIFACT / "run_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"


def _configure_engine() -> None:
    values = {
        "VERSION": VERSION, "CALLS": CALLS, "COST_CEILING": COST_CEILING, "AUTH_ID": AUTH_ID,
        "RECEIPT": RECEIPT, "REQUEST": REQUEST, "AUTH": AUTH, "AUTH_CLOSED": AUTH_CLOSED,
        "V17_CONFIG": V19_CONFIG, "V17_ARTIFACT": V19_ARTIFACT, "V17_MANIFEST": V19_MANIFEST,
        "SCHEDULE": SCHEDULE, "PRIOR_BUNDLES": PRIOR_BUNDLES, "REPLACEMENT_GOLD": RECOVERY_GOLD,
        "CANDIDATE": CANDIDATE, "PROVIDER_ADAPTER": PROVIDER_ADAPTER, "ANALYZER": ANALYZER, "TEST": TEST,
        "ARTIFACT": ARTIFACT, "PREFLIGHT_AUDIT": PREFLIGHT_AUDIT, "REGISTRY": REGISTRY, "LEDGER": LEDGER,
        "PACING": PACING, "PROBE_AUDIT": PROBE_AUDIT, "RUN_AUDIT": RUN_AUDIT, "CLOSURE": CLOSURE,
    }
    for name, value in values.items():
        setattr(engine, name, value)


_configure_engine()
load = engine.load
write = engine.write
usage = engine.usage
known_cost = engine.known_cost
local_cost_from_usage = engine.local_cost_from_usage
HardStop = engine.HardStop


def preflight() -> dict[str, Any]:
    gate = validate_v19()
    request = load(REQUEST)
    receipt = load(RECEIPT)
    if gate.get("aggregate_fingerprint") != request.get("bindings", {}).get("v19_aggregate_fingerprint"):
        raise HardStop("v20 v19 aggregate/request binding drift")
    if sha256_file(REQUEST) != receipt.get("request_binding", {}).get("authorization_request_sha256") or receipt.get("request_binding", {}).get("v19_aggregate_fingerprint") != gate["aggregate_fingerprint"]:
        raise HardStop("v20 user authorization receipt binding drift")
    exact = {
        "scope": "probe_recovery_only", "authorized_stage": "probe", "authorized_calls": CALLS,
        "max_provider_attempts": CALLS, "model_id": "qwen3.7-plus", "temperature": 0,
        "retries": 0, "max_tokens_present": False, "enable_thinking": False,
        "response_format": {"type": "json_object"}, "stage_cost_ceiling_cny": COST_CEILING,
        "cumulative_cost_ceiling_cny": COST_CEILING, "held_out_authorized": False,
        "later_stages_authorized": False, "formal_scaling_authorized": False,
    }
    if any(receipt.get(key) != value for key, value in exact.items()) or receipt.get("status") != "explicit_user_authorization_received_execution_not_open":
        raise HardStop("v20 user authorization boundary drift")
    if any(receipt.get("execution", {}).get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v20 receipt must remain execution-closed")
    bindings = request["bindings"]
    expected = {"v19_config_sha256": V19_CONFIG, "v19_manifest_sha256": V19_MANIFEST, "v19_schedule_sha256": SCHEDULE}
    if any(bindings.get(name) != sha256_file(path) for name, path in expected.items()):
        raise HardStop("v20 v19 artifact binding drift")
    rows = load(SCHEDULE)["schedule"]
    if len(rows) != CALLS or len({row["logical_call_id"] for row in rows}) != CALLS or len({row["request_hash"] for row in rows}) != CALLS:
        raise HardStop("v20 schedule cardinality/identity drift")
    spent = load(V18_LEDGER)
    if {row["logical_call_id"] for row in rows} & {row["logical_call_id"] for row in spent} or {row["request_hash"] for row in rows} & {row["request_hash"] for row in spent}:
        raise HardStop("v20 schedule retries spent v18 request")
    if any(
        row.get("staged_execution_index") != index
        or row.get("partition") != "probe"
        or row["request_hash"] != stable(row["canonical_request_body"])
        or "max_tokens" in row["canonical_request_body"]
        or row["canonical_request_body"].get("model_id") != "qwen3.7-plus"
        or row["canonical_request_body"].get("temperature") != 0
        or row["canonical_request_body"].get("response_format") != {"type": "json_object"}
        or row["canonical_request_body"].get("enable_thinking") is not False
        for index, row in enumerate(rows, 1)
    ):
        raise HardStop("v20 request route/prefix drift")
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise HardStop("DASHSCOPE_API_KEY missing")
    result = {
        "schema_version": VERSION, "status": "zero-network-preflight-passed",
        "authorized_calls": CALLS, "max_provider_attempts": CALLS,
        "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": COST_CEILING,
        "v19_aggregate_fingerprint": gate["aggregate_fingerprint"],
        "bindings": {
            "authorization_receipt_sha256": sha256_file(RECEIPT), "authorization_request_sha256": sha256_file(REQUEST),
            "v19_config_sha256": sha256_file(V19_CONFIG), "v19_manifest_sha256": sha256_file(V19_MANIFEST),
            "schedule_sha256": sha256_file(SCHEDULE), "prior_bundles_sha256": sha256_file(PRIOR_BUNDLES),
            "recovery_gold_sha256": sha256_file(RECOVERY_GOLD), "v18_ledger_sha256": sha256_file(V18_LEDGER),
            "v17_schedule_sha256": sha256_file(V17_SCHEDULE), "candidate_sha256": sha256_file(CANDIDATE),
            "provider_adapter_sha256": sha256_file(PROVIDER_ADAPTER), "analyzer_sha256": sha256_file(ANALYZER),
            "live_runner_sha256": sha256_file(Path(__file__).resolve()), "live_test_sha256": sha256_file(TEST),
        },
        "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0,
        "authorization_opened": False, "held_out_authorized": False, "later_stages_authorized": False,
        "formal_scaling_authorized": False,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def authorization_template(key: str) -> dict[str, Any]:
    gate = preflight()
    return {
        "schema_version": VERSION, "experiment": "acl2027_phase2_probe_recovery_live_v20",
        "authorization_id": AUTH_ID, "status": "open",
        "bindings": {**gate["bindings"], "zero_network_preflight_aggregate_fingerprint": gate["aggregate_fingerprint"]},
        "credential_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "user_authorization": {
            "scope": "phase2_probe_recovery_only", "authorized_calls": CALLS,
            "authorization_receipt_sha256": sha256_file(RECEIPT), "held_out_authorized": False,
            "later_stages_authorized": False, "formal_scaling_authorized": False,
        },
        "authorized_stage": "probe", "authorized_calls": CALLS, "stage_call_ceiling": CALLS,
        "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": COST_CEILING,
        "cumulative_cost_ceiling_cny": COST_CEILING, "model_id": "qwen3.7-plus",
        "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False,
        "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True,
        "formal_scaling_allowed": False, "forbidden_stages": ["held_out", "later_phase2_stages", "formal_scaling"],
    }


engine.preflight = preflight
engine.authorization_template = authorization_template


def audit() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING) if PACING.exists() else []
    terminal = bool(records and records[-1].get("terminal"))
    auth_sha = sha256_file(AUTH) if AUTH.exists() else None
    if records and not auth_sha:
        raise HardStop("v20 ledger exists without authorization")
    if auth_sha:
        engine.validate_audit_chain(records, starts, rows, auth_sha)
    known = [record for record in records if isinstance(record.get("usage"), dict)]
    exact_usage_complete = len(known) == len(records)
    probe = None
    if len(records) == CALLS and not terminal:
        probe = build_probe_audit(
            records, rows, load(CANDIDATE), sha256_file(CANDIDATE), RECOVERY_GOLD,
            preserved_records=load(V18_LEDGER), preserved_schedule=load(V17_SCHEDULE)["schedule"],
        )
        write(PROBE_AUDIT, probe)
    request_ids = [record.get("request_id") for record in records if record.get("request_id")]
    completed_statuses = {"completed", "completed_cost_ceiling_stop"}
    completed = [record for record in records if record.get("status") in completed_statuses]
    if len(request_ids) != len(completed) or len(set(request_ids)) != len(request_ids):
        raise HardStop("v20 completed provider request IDs are missing or duplicated")
    result = {
        "schema_version": VERSION, "status": "completed" if probe else "terminal_hard_stop" if terminal else "incomplete",
        "planned_calls": CALLS, "provider_attempts": len(starts),
        "unique_logical_requests": len({record.get("logical_call_id") for record in records}),
        "unique_request_hashes": len({record.get("request_hash") for record in records}),
        "unique_provider_request_ids": len(set(request_ids)), "completed_calls": len(completed),
        "terminal_rows": sum(bool(record.get("terminal")) for record in records), "skipped_requests": 0,
        "out_of_bounds_requests": 0, "input_tokens": sum(usage(record)["input_tokens"] for record in known),
        "output_tokens": sum(usage(record)["output_tokens"] for record in known),
        "total_tokens": sum(usage(record)["total_tokens"] for record in known),
        "usage_status": "exact" if exact_usage_complete else "known_lower_bound",
        "exact_local_cost_cny": known_cost(records) if exact_usage_complete else None,
        "known_local_cost_lower_bound_cny": known_cost(records),
        "retries": sum(record.get("retries", 0) for record in records),
        "duplicates": len(records) - len({record.get("logical_call_id") for record in records}),
        "max_tokens_present": any(record.get("max_tokens_present") for record in records),
        "model_id": "qwen3.7-plus", "temperature": 0,
        "request_start_pacing_valid": all(b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= engine.INTERVAL_NS for a, b in zip(starts, starts[1:])),
        "ledger_hash_chain_valid": True, "request_start_hash_chain_valid": True, "exact_prefix_resume_valid": True,
        "v19_aggregate_fingerprint": load(V19_MANIFEST)["aggregate_fingerprint"],
        "v18_preserved_analysis_rows": 48, "combined_probe_rows": 48 + len(completed),
        "probe_gate_passed": probe.get("passed") if probe else False,
        "condition_accuracy": probe.get("condition_accuracy", {}) if probe else {},
        "condition_successes": probe.get("condition_successes", {}) if probe else {},
        "primary_paired_comparison": probe.get("primary_paired_comparison", {}) if probe else {},
        "network_calls": len(starts), "provider_calls": len(starts), "model_calls": len(starts), "paid_api_calls": len(starts),
        "held_out_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0,
        "authorization_closed": CLOSURE.exists() and AUTH_CLOSED.exists(),
    }
    write(RUN_AUDIT, result)
    return result


def close(reason: str) -> dict[str, Any]:
    result = audit()
    closure = {
        "schema_version": VERSION, "authorization_id": AUTH_ID, "status": "closed", "reason": reason,
        "authorization_sha256": sha256_file(AUTH) if AUTH.exists() else None,
        "authorization_receipt_sha256": sha256_file(RECEIPT), "authorization_request_sha256": sha256_file(REQUEST),
        "provider_attempts": result["provider_attempts"], "completed_calls": result["completed_calls"],
        "usage_status": result["usage_status"], "exact_local_cost_cny": result["exact_local_cost_cny"],
        "known_local_cost_lower_bound_cny": result["known_local_cost_lower_bound_cny"],
        "held_out_calls": 0, "later_stage_calls": 0, "formal_scaling_calls": 0,
        "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False,
        "formal_scaling_allowed": False,
    }
    write(CLOSURE, closure)
    write(AUTH_CLOSED, closure)
    result["authorization_closed"] = True
    write(RUN_AUDIT, result)
    return closure


engine.audit = audit
engine.close = close


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "authorize", "execute", "audit", "close"))
    args = parser.parse_args()
    if args.command == "preflight":
        result = preflight()
        write(PREFLIGHT_AUDIT, result)
    elif args.command == "authorize":
        result = engine.open_authorization()
    elif args.command == "audit":
        result = audit()
    elif args.command == "close":
        result = close("operator_close")
    else:
        try:
            records = engine.execute(QwenTokenPlanProviderAdapter(engine.validate_authorization()[0]))
            result = {"rows": len(records), "closure": close("completed_exact_112")}
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists():
                close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
