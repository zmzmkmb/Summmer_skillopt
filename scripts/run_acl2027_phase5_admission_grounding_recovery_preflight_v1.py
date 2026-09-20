#!/usr/bin/env python3
"""Freeze a zero-network recovery after the Phase 5 ledger write failure."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

SOURCE = ROOT / "artifacts/acl2027_phase5_admission_grounding_preflight_v1/schedule.json"
LIVE = ROOT / "artifacts/acl2027_phase5_admission_grounding_live_v1"
ARTIFACT = ROOT / "artifacts/acl2027_phase5_admission_grounding_recovery_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase5_admission_grounding_recovery_preflight_v1.md"
SOURCE_DESIGN = "c61009e80f5f662c5b62c87239aff4a9fce86c759a98c6250f1a4e941b11a7de"
SOURCE_PREFLIGHT = "602b27d182b8fc8dfd7f64897a44a2a89ed8ecc3f037f568108407c25b52fd1c"
KNOWN_COST = 0.730116
ORPHAN_RESERVE = 0.05


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    if ARTIFACT.exists():
        raise RuntimeError("immutable recovery artifact already exists")
    starts = load(LIVE / "request_start_ledger.json")
    ledger = load(LIVE / "ledger.json")
    if len(starts) != 94 or len(ledger) != 93:
        raise RuntimeError(f"unexpected terminal prefix: starts={len(starts)} ledger={len(ledger)}")
    if any(r.get("terminal") for r in ledger):
        raise RuntimeError("completed prefix contains terminal row")
    spent_logical = {r["logical_call_id"] for r in starts}
    spent_hashes = {r["request_hash"] for r in starts}
    source = load(SOURCE)["rows"]
    candidates = [r for r in source if r["sequence"] >= 94]
    if len(candidates) != 147:
        raise RuntimeError("source recovery coverage drift")
    rows = []
    for i, original in enumerate(candidates, start=1):
        body = dict(original["canonical_request_body"])
        body["recovery_plan_id"] = "phase5-admission-grounding-recovery-preflight-v1"
        body["recovery_source_sequence"] = original["sequence"]
        row = dict(original)
        row["sequence"] = i
        row["logical_call_id"] = original["logical_call_id"] + ":recovery_v1"
        row["canonical_request_body"] = body
        row["request_hash"] = stable(body)
        row["transport_payload_hash"] = stable({"model": body["model_id"], "messages": body["messages"], "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}})
        row["provenance"] = {"network_calls": 0, "provider_calls": 0, "paid_api_calls": 0, "recovery_source_sequence": original["sequence"], "spent_source_prefix_excluded": True}
        rows.append(row)
    if any(r["logical_call_id"] in spent_logical for r in rows):
        raise RuntimeError("logical identity overlap")
    if any(r["request_hash"] in spent_hashes for r in rows):
        raise RuntimeError("request hash overlap")
    counts = Counter(r["condition"] for r in rows)
    result = {"schema_version": 1, "experiment": "acl2027_phase5_admission_grounding_recovery_preflight_v1", "status": "zero_network_recovery_preflight_passed_closed", "source_design_fingerprint": SOURCE_DESIGN, "source_live_preflight_fingerprint": SOURCE_PREFLIGHT, "terminal_source_attempts": 94, "preserved_completed_rows": 93, "orphan_source_sequence": 94, "new_rows": len(rows), "condition_counts": dict(sorted(counts.items())), "unique_logical_call_ids": len({r["logical_call_id"] for r in rows}), "unique_request_hashes": len({r["request_hash"] for r in rows}), "unique_transport_payloads": len({r["transport_payload_hash"] for r in rows}), "identity_overlap": {"spent_logical_call_ids": 0, "spent_request_hashes": 0}, "cost_accounting": {"prior_known_lower_bound_cny": KNOWN_COST, "orphan_usage_reserve_cny": ORPHAN_RESERVE, "known_plus_reserve_cny": round(KNOWN_COST + ORPHAN_RESERVE, 6), "stage_cost_ceiling_cny": 3.0, "cumulative_cost_ceiling_cny": 15.0}, "execution_contract": {"scope": "phase5_admission_grounding_recovery_only", "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "model_id": "qwen3.7-plus", "authorized_calls": len(rows), "temperature": 0, "enable_thinking": False, "retries": 0, "max_tokens_present": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "stage_cost_ceiling_cny": 3.0, "cumulative_cost_ceiling_cny": 15.0, "terminal_stop_on_first_failed_attempt": True, "exact_prefix_resume_only": True, "hash_chain_required": True}, "forbidden_scope": ["replication", "other_models", "cross_domain_scaling", "formal_scaling"], "bindings": {"source_schedule_sha256": sha256_file(SOURCE), "terminal_starts_sha256": sha256_file(LIVE / "request_start_ledger.json"), "terminal_ledger_sha256": sha256_file(LIVE / "ledger.json")}, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    result["aggregate_fingerprint"] = stable(result)
    request = {"schema_version": 1, "status": "awaiting_fresh_exact_explicit_user_authorization", "source_design_fingerprint": SOURCE_DESIGN, "source_live_preflight_fingerprint": SOURCE_PREFLIGHT, "recovery_preflight_aggregate_fingerprint": result["aggregate_fingerprint"], "authorization_statement_verbatim": "I explicitly authorize Phase 5 admission/grounding recovery execution, binding recovery preflight fingerprint " + result["aggregate_fingerprint"] + ", preserving 93 completed rows as provenance, excluding all 94 spent source attempts including orphan source sequence 94, and using 147 new frozen requests to https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1 with qwen3.7-plus, temperature 0, thinking disabled, zero retries, no max_tokens, JSON-object responses, one-second pacing, CNY 3.00 recovery-stage and CNY 15.00 cumulative ceilings including the CNY 0.05 orphan-usage reserve, first-failure stop, exact-prefix resume, durable hash-chain ledgers, and automatic closure. I authorize no replication, other models, cross-domain scaling, or formal scaling.", "execution_contract": result["execution_contract"], "forbidden_scope": result["forbidden_scope"], "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    ARTIFACT.mkdir(parents=True)
    for name, value in (("run_manifest.json", result), ("schedule.json", {"schema_version": 1, "rows": rows}), ("authorization_request.json", request), ("source_provenance.json", {"terminal_source_attempts": 94, "preserved_completed_rows": 93, "orphan_source_sequence": 94, "terminal_starts_sha256": result["bindings"]["terminal_starts_sha256"], "terminal_ledger_sha256": result["bindings"]["terminal_ledger_sha256"]}), ("completion_manifest.json", {"schema_version": 1, "experiment": result["experiment"], "status": "complete", "completion_kind": "zero_network_recovery_preflight", "proposed_calls": len(rows), "completed_calls": len(rows), "rows": len(rows), "provider_calls_executed": 0, "aggregate_fingerprint": result["aggregate_fingerprint"]})):
        (ARTIFACT / name).write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Phase 5 admission/grounding recovery preflight\n\nPreserves 93 completed responses, excludes 94 spent attempts, and freezes 147 new identities. No network or provider call occurred.\n\nFingerprint: `" + result["aggregate_fingerprint"] + "`.\n\nExact fresh authorization is required.\n", encoding="utf-8")
    print(json.dumps({"aggregate_fingerprint": result["aggregate_fingerprint"], "rows": len(rows), "condition_counts": dict(sorted(counts.items())), "network_calls": 0, "authorization_request": request}, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
