#!/usr/bin/env python3
"""Freeze the zero-network Phase 4B-R2 live-execution preflight."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts import run_acl2027_phase4b_contract_repair_preflight_v1 as repair

VERSION = 2
CALLS = 100
TASKS = 20
REPAIR_FINGERPRINT = "a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"
CONDITIONS = repair.CONDITIONS

CONFIG = ROOT / "configs/acl2027/phase4b_contract_repair_live_preflight_v2.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4b_contract_repair_live_preflight_v2.py"
SOURCE = ROOT / "artifacts/acl2027_phase4b_contract_repair_preflight_v1"
SOURCE_MANIFEST = SOURCE / "run_manifest.json"
SOURCE_SCHEDULE = SOURCE / "repaired_schedule.json"
SOURCE_GOLD = SOURCE / "private_gold.json"
SOURCE_TRANSPORT_AUDIT = SOURCE / "transport_projection_audit.json"
SOURCE_COMPLETION = SOURCE / "completion_manifest.json"
RECEIPT = ROOT / "configs/acl2027/phase4b_contract_repair_user_authorization_receipt_v3.json"
LIVE_ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3"
AUTH_OPEN = LIVE_ARTIFACT / "authorization_open.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_preflight_v2"
REPORT = ROOT / "paper/acl2027/results/phase4b_contract_repair_live_preflight_v2.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def schedule_rows() -> list[dict[str, Any]]:
    rows = load(SOURCE_SCHEDULE).get("rows")
    if not isinstance(rows, list):
        raise RuntimeError("Phase 4B-R1 repaired schedule is not a list")
    return rows


def validate_schedule(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != CALLS:
        raise RuntimeError("Phase 4B-R1 schedule row-count drift")
    if [row.get("sequence") for row in rows] != list(range(1, CALLS + 1)):
        raise RuntimeError("Phase 4B-R1 schedule sequence drift")

    logical_ids = [str(row.get("logical_call_id")) for row in rows]
    request_hashes = [str(row.get("request_hash")) for row in rows]
    transport_hashes = [str(row.get("transport_payload_hash")) for row in rows]
    if len(set(logical_ids)) != CALLS or len(set(request_hashes)) != CALLS:
        raise RuntimeError("Phase 4B-R1 canonical request identities are not unique")

    repair.base.ARTIFACT = SOURCE
    prior = repair.base.prior_identity_universe()
    task_ids = {str(row.get("task_id")) for row in rows}
    overlap = {
        "task_id_overlap": len(task_ids & prior["task_ids"]),
        "logical_call_id_overlap": len(set(logical_ids) & prior["logical_call_ids"]),
        "request_hash_overlap": len(set(request_hashes) & prior["request_hashes"]),
    }
    if any(overlap.values()):
        raise RuntimeError(f"Phase 4B-R1 prior identity overlap drift: {overlap}")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        body = row.get("canonical_request_body")
        projection = row.get("transport_projection")
        if not isinstance(body, dict) or stable(body) != row.get("request_hash"):
            raise RuntimeError(f"canonical request hash drift at sequence {row.get('sequence')}")
        recomputed = repair.transport_projection(body)
        if projection != recomputed or stable(recomputed) != row.get("transport_payload_hash"):
            raise RuntimeError(f"transport projection hash drift at sequence {row.get('sequence')}")
        expected = {
            "model": MODEL,
            "temperature": 0,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
        }
        if any(projection.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"transport route contract drift at sequence {row.get('sequence')}")
        if set(projection) != {"model", "messages", "temperature", "enable_thinking", "response_format"}:
            raise RuntimeError(f"transport field drift at sequence {row.get('sequence')}")
        if "max_tokens" in body or "max_tokens" in projection:
            raise RuntimeError(f"max_tokens unexpectedly present at sequence {row.get('sequence')}")
        system = projection["messages"][0]["content"]
        user = json.loads(projection["messages"][1]["content"])
        if not all(key in system for key in repair.EXACT_KEYS):
            raise RuntimeError(f"six-field system contract invisible at sequence {row.get('sequence')}")
        if user.get("response_contract", {}).get("exact_keys") != list(repair.EXACT_KEYS):
            raise RuntimeError(f"six-field user contract invisible at sequence {row.get('sequence')}")
        evidence_ids = [
            sentence.get("id")
            for block in user.get("context", [])
            for sentence in block.get("sentences", [])
        ]
        if not evidence_ids or any(not value for value in evidence_ids):
            raise RuntimeError(f"evidence ID visibility drift at sequence {row.get('sequence')}")
        groups[str(row["transport_payload_hash"])].append(row)

    condition_counts = Counter(str(row.get("condition")) for row in rows)
    if len(task_ids) != TASKS or condition_counts != Counter({condition: 20 for condition in CONDITIONS}):
        raise RuntimeError("Phase 4B-R1 task-grid balance drift")

    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    expected_pairs = {frozenset(("global_only", "contextual_typed"))}
    if len(groups) != 80 or len(duplicate_groups) != 20:
        raise RuntimeError("Phase 4B-R1 transport equivalence count drift")
    for group in duplicate_groups:
        if len(group) != 2 or {frozenset(str(row["condition"]) for row in group)} != expected_pairs:
            raise RuntimeError("unexpected Phase 4B-R1 transport equivalence shape")
        if len({str(row["task_id"]) for row in group}) != 1:
            raise RuntimeError("transport equivalence crosses task identities")

    return {
        "rows": len(rows),
        "tasks": len(task_ids),
        "unique_logical_call_ids": len(set(logical_ids)),
        "unique_request_hashes": len(set(request_hashes)),
        "unique_transport_payload_hashes": len(set(transport_hashes)),
        "duplicate_transport_pair_count": len(duplicate_groups),
        "duplicate_transport_pair_conditions": ["global_only", "contextual_typed"],
        "condition_counts": dict(sorted(condition_counts.items())),
        "identity_overlap_audit": overlap,
        "canonical_schedule_sha256": stable(rows),
        "transport_payload_hash_chain_seed": stable(transport_hashes),
        "contract_visible_in_all_transmitted_messages": True,
        "evidence_ids_visible_in_all_transmitted_messages": True,
    }


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load(CONFIG)
    source_manifest = load(SOURCE_MANIFEST)
    source_completion = load(SOURCE_COMPLETION)
    if source_manifest.get("aggregate_fingerprint") != REPAIR_FINGERPRINT:
        raise RuntimeError("Phase 4B-R1 repair fingerprint drift")
    if source_completion.get("aggregate_fingerprint") != REPAIR_FINGERPRINT:
        raise RuntimeError("Phase 4B-R1 completion fingerprint drift")
    if source_manifest.get("status") != "zero-network-contract-repair-preflight-passed-closed":
        raise RuntimeError("Phase 4B-R1 source is not closed and complete")
    if source_completion.get("rows") != CALLS or source_completion.get("provider_calls_executed") != 0:
        raise RuntimeError("Phase 4B-R1 completion counters drift")
    if cfg.get("status") != "zero_network_live_execution_preflight_closed":
        raise RuntimeError("Phase 4B-R2 preflight status drift")
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("Phase 4B-R2 execution switches must remain closed")
    authorization = cfg["authorization"]
    if any(authorization.get(key) is not False for key in (
        "receipt_created", "authorization_open", "data_egress_authorized",
        "provider_calls_authorized", "paid_api_authorized",
    )):
        raise RuntimeError("Phase 4B-R2 authorization must remain closed")
    if RECEIPT.exists() or AUTH_OPEN.exists():
        raise RuntimeError("Phase 4B-R3 authorization receipt or open authorization already exists")

    contract = cfg["execution_contract"]
    expected_contract = {
        "scope": "phase4b_repaired_development_calibration_only",
        "endpoint": ENDPOINT,
        "model_id": MODEL,
        "authorized_calls": CALLS,
        "max_provider_attempts": CALLS,
        "temperature": 0,
        "enable_thinking": False,
        "retries": 0,
        "max_tokens_present": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "stage_cost_ceiling_cny": 2.0,
        "cumulative_cost_ceiling_cny": 15.0,
        "known_cumulative_cost_lower_bound_cny": 11.816126,
    }
    if any(contract.get(key) != value for key, value in expected_contract.items()):
        raise RuntimeError("Phase 4B-R2 exact execution contract drift")
    if contract.get("payload_classes") != [
        "frozen_task_prompts",
        "frozen_annotated_contexts",
        "frozen_procedure_candidate_bundles",
        "frozen_six_field_response_contract",
    ]:
        raise RuntimeError("Phase 4B-R2 payload egress classes drift")
    if any(contract.get(key) is not True for key in (
        "terminal_stop_on_first_failed_attempt",
        "authorization_closes_on_completion_or_terminal_stop",
        "usage_accounting_required",
        "request_start_ledger_required",
        "response_ledger_required",
        "hash_chain_required",
        "exact_prefix_resume_only",
    )):
        raise RuntimeError("Phase 4B-R2 safety or accounting contract drift")

    audit = validate_schedule(schedule_rows())
    equivalence = cfg["known_transport_equivalence"]
    if equivalence.get("unique_transport_payloads") != audit["unique_transport_payload_hashes"]:
        raise RuntimeError("Phase 4B-R2 transport equivalence declaration drift")
    if equivalence.get("duplicate_pair_count") != audit["duplicate_transport_pair_count"]:
        raise RuntimeError("Phase 4B-R2 duplicate pair declaration drift")

    bindings = {
        "config_sha256": sha256_file(CONFIG),
        "script_sha256": sha256_file(SCRIPT),
        "test_sha256": sha256_file(TEST),
        "source_manifest_sha256": sha256_file(SOURCE_MANIFEST),
        "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE),
        "source_private_gold_sha256": sha256_file(SOURCE_GOLD),
        "source_transport_audit_sha256": sha256_file(SOURCE_TRANSPORT_AUDIT),
        "source_completion_manifest_sha256": sha256_file(SOURCE_COMPLETION),
        "source_schedule_canonical_sha256": audit["canonical_schedule_sha256"],
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "live-execution-preflight-passed-closed",
        "authorization_status": "fresh-exact-explicit-user-authorization-required",
        "phase4b_repair_fingerprint": REPAIR_FINGERPRINT,
        "schedule_audit": audit,
        "known_transport_equivalence": equivalence,
        "execution_contract": contract,
        "forbidden_scope": cfg["forbidden_scope"],
        "bindings": bindings,
        "authorization_receipt_exists": False,
        "authorization_open_exists": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "phase4c_calls": 0,
        "replication_calls": 0,
        "cross_domain_scaling_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    statement = authorization["authorization_statement_template"].format(
        preflight_aggregate_fingerprint=result["aggregate_fingerprint"]
    )
    request = {
        "schema_version": VERSION,
        "status": "awaiting_exact_explicit_user_authorization",
        "phase4b_repair_fingerprint": REPAIR_FINGERPRINT,
        "preflight_aggregate_fingerprint": result["aggregate_fingerprint"],
        "authorization_statement_verbatim": statement,
        "execution_contract": contract,
        "known_transport_equivalence": equivalence,
        "forbidden_scope": cfg["forbidden_scope"],
        "receipt_path_if_authorized": str(RECEIPT.relative_to(ROOT)).replace("\\", "/"),
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }
    return result, request


def report_text(result: dict[str, Any], request: dict[str, Any]) -> str:
    return f"""# ACL 2027 Phase 4B-R2 live-execution preflight

This zero-network preflight binds the unchanged 100-row Phase 4B-R1 repaired schedule and its aggregate fingerprint `{REPAIR_FINGERPRINT}`. It revalidates every canonical request hash and final adapter transport hash, the 20-by-5 task grid, visible six-field response schema, explicit evidence IDs, and zero prior task, logical-call, or request-hash overlap.

The audit records 80 unique transmitted payloads. For each of the 20 tasks, `global_only` and `contextual_typed` are an identical transport pair, so a future execution cannot identify a contrast between those two labels. The schedule remains unchanged; this limitation is included in the exact authorization statement.

The preflight freezes the Token Plan Beijing endpoint, `qwen3.7-plus`, temperature 0, thinking disabled, zero retries, absent `max_tokens`, JSON-object responses, one-second pacing, CNY 2.00 stage ceiling, CNY 15.00 cumulative ceiling, first-failure termination, exact-prefix resume, hash-chain ledgers, and automatic closure. No authorization receipt or open authorization exists, and all call counters remain zero.

Preflight aggregate fingerprint: `{result['aggregate_fingerprint']}`.

## Exact authorization required

{request['authorization_statement_verbatim']}
"""


def write_artifact(result: dict[str, Any], request: dict[str, Any], *, repair_incomplete: bool = False) -> None:
    if ARTIFACT.exists():
        if not repair_incomplete:
            raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
        prior_completion = load(ARTIFACT / "completion_manifest.json")
        if any(key in prior_completion for key in ("proposed_calls", "completed_calls", "rows")):
            raise RuntimeError("refusing to rewrite a non-schema-incomplete artifact")
        if prior_completion.get("schedule_rows_bound") != CALLS or prior_completion.get("provider_calls_executed") != 0:
            raise RuntimeError("refusing to rewrite an unexpected artifact")
    else:
        ARTIFACT.mkdir(parents=True)
    write(ARTIFACT / "schedule_binding_audit.json", result["schedule_audit"])
    write(ARTIFACT / "authorization_request.json", request)
    write(ARTIFACT / "run_manifest.json", result)
    write(ARTIFACT / "completion_manifest.json", {
        "schema_version": VERSION,
        "experiment": result["experiment"],
        "status": "complete",
        "completion_kind": "zero_network_live_execution_preflight",
        "proposed_calls": CALLS,
        "completed_calls": CALLS,
        "rows": CALLS,
        "schedule_rows_bound": CALLS,
        "provider_calls_executed": 0,
        "authorization_status": result["authorization_status"],
        "aggregate_fingerprint": result["aggregate_fingerprint"],
        "authorization_request_sha256": sha256_file(ARTIFACT / "authorization_request.json"),
    })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(result, request), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    parser.add_argument("--repair-incomplete-artifact", action="store_true")
    args = parser.parse_args()
    if args.repair_incomplete_artifact and not args.write_artifact:
        parser.error("--repair-incomplete-artifact requires --write-artifact")
    result, request = validate()
    if args.write_artifact:
        write_artifact(result, request, repair_incomplete=args.repair_incomplete_artifact)
    print(render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
