#!/usr/bin/env python3
"""Freeze a zero-network recovery plan for the terminal Phase 4B-R3 run."""
from __future__ import annotations

import argparse
import copy
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
from scripts import audit_acl2027_phase4b_contract_repair_live_v3_1 as terminal
from scripts import run_acl2027_phase4b_contract_repair_preflight_v1 as repair

VERSION = 4
CALLS = 28
COMPLETED = 72
SPENT = 73
TOTAL = 100
TASKS = 20
R1_FINGERPRINT = "a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c"
R2_FINGERPRINT = "94a2e284a4049db12f5e1f1294fa92d4433547ee9be0dd151e6ba848bbc7da28"
R3_FINGERPRINT = "f32e141b1ba15637cdb9b99fa360a59996adf613b90d610b7ef206bce14773e1"

CONFIG = ROOT / "configs/acl2027/phase4b_contract_repair_recovery_preflight_v4.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4b_contract_repair_recovery_preflight_v4.py"
R1 = ROOT / "artifacts/acl2027_phase4b_contract_repair_preflight_v1"
R1_MANIFEST = R1 / "run_manifest.json"
R1_SCHEDULE = R1 / "repaired_schedule.json"
R1_GOLD = R1 / "private_gold.json"
R2 = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_preflight_v2"
R2_MANIFEST = R2 / "run_manifest.json"
R3 = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3"
R3_STARTS = R3 / "request_start_ledger.json"
R3_LEDGER = R3 / "ledger.json"
R3_CLOSURE = R3 / "authorization_closure.json"
R3_TERMINAL = R3 / "terminal_audit_v3_1.json"
R3_COMPLETION = R3 / "completion_manifest.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_preflight_v4"
REPORT = ROOT / "paper/acl2027/results/phase4b_contract_repair_recovery_preflight_v4.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def source_rows() -> list[dict[str, Any]]:
    rows = load(R1_SCHEDULE).get("rows")
    if not isinstance(rows, list) or len(rows) != TOTAL:
        raise RuntimeError("Phase 4B-R1 schedule drift")
    return rows


def recovery_row(source: dict[str, Any], sequence: int) -> dict[str, Any]:
    original_sequence = int(source["sequence"])
    body = copy.deepcopy(source["canonical_request_body"])
    body["phase"] = "4B-contract-recovery-v4"
    body["recovery_identity"] = {
        "source_phase": "4B-contract-repair-v1",
        "source_sequence": original_sequence,
        "kind": "orphan_transport_replacement" if original_sequence == SPENT else "unattempted_suffix",
    }
    projection = repair.transport_projection(body)
    if projection != source["transport_projection"]:
        raise RuntimeError(f"model-visible transport changed at source sequence {original_sequence}")
    family = str(source["skill_family"])
    task_id = str(source["task_id"])
    condition = str(source["condition"])
    return {
        **{key: copy.deepcopy(value) for key, value in source.items() if key not in {
            "schema_version", "sequence", "logical_call_id", "request_hash", "canonical_request_body",
            "transport_projection", "transport_payload_hash", "provider_response_id",
        }},
        "schema_version": VERSION,
        "sequence": sequence,
        "recovery_sequence": sequence,
        "source_sequence": original_sequence,
        "logical_call_id": f"phase4b-contract-recovery-v4:{family}:{task_id}:{condition}",
        "request_hash": stable(body),
        "canonical_request_body": body,
        "transport_projection": projection,
        "transport_payload_hash": stable(projection),
        "provider_response_id": None,
        "recovery_kind": body["recovery_identity"]["kind"],
    }


def build_recovery_schedule(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Sequence 73 is spent but response-incomplete; 74-100 were never attempted.
    return [recovery_row(row, index) for index, row in enumerate(rows[SPENT - 1 :], start=1)]


def validate_r3(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    starts = load(R3_STARTS)
    records = load(R3_LEDGER)
    audit = load(R3_TERMINAL)
    completion = load(R3_COMPLETION)
    closure = load(R3_CLOSURE)
    if len(starts) != SPENT or len(records) != COMPLETED:
        raise RuntimeError("Phase 4B-R3 terminal count drift")
    if audit.get("aggregate_fingerprint") != R3_FINGERPRINT or completion.get("aggregate_fingerprint") != R3_FINGERPRINT:
        raise RuntimeError("Phase 4B-R3 terminal fingerprint drift")
    if audit.get("authorization_closed") is not True or audit.get("retry_or_resume_authorized") is not False:
        raise RuntimeError("Phase 4B-R3 closure drift")
    if closure.get("status") != "closed":
        raise RuntimeError("Phase 4B-R3 original closure is not closed")
    terminal.live.validate_prefix(rows, starts[:COMPLETED], records, sha256_file(terminal.live.AUTH))
    orphan = terminal.validate_orphan(rows, starts, sha256_file(terminal.live.AUTH))
    valid = 0
    evidence = 0
    for row, record in zip(rows, records):
        try:
            value = json.loads(record["raw_response"])
        except (TypeError, json.JSONDecodeError):
            value = None
        contract_valid, evidence_resolves = terminal.contract_valid(row, value)
        valid += int(contract_valid)
        evidence += int(evidence_resolves)
    if valid != COMPLETED or evidence != COMPLETED:
        raise RuntimeError("Phase 4B-R3 reusable response contract drift")
    return starts, records, {
        "request_starts": len(starts),
        "completed_responses": len(records),
        "orphan_request_starts": 1,
        "unattempted_original_rows": TOTAL - len(starts),
        "reusable_contract_valid_rows": valid,
        "reusable_evidence_resolving_rows": evidence,
        "orphan": orphan,
        "authorization_closed": True,
        "retry_or_resume_authorized": False,
    }


def analysis_row(source: dict[str, Any], disposition: str, recovery: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {
        "analysis_sequence": int(source["sequence"]),
        "source_sequence": int(source["sequence"]),
        "task_id": source["task_id"],
        "skill_family": source["skill_family"],
        "condition": source["condition"],
        "transport_payload_hash": source["transport_payload_hash"],
        "disposition": disposition,
    }
    if recovery is None:
        row.update({"logical_call_id": source["logical_call_id"], "request_hash": source["request_hash"]})
    else:
        row.update({
            "logical_call_id": recovery["logical_call_id"],
            "request_hash": recovery["request_hash"],
            "recovery_sequence": recovery["sequence"],
            "recovery_kind": recovery["recovery_kind"],
        })
    return row


def validate() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("Phase 4B-R4 execution switches must remain closed")
    auth = cfg["authorization_request"]
    if auth["status"] != "closed_fresh_live_preflight_and_explicit_authorization_required":
        raise RuntimeError("Phase 4B-R4 authorization request drift")
    if any(auth[key] is not False for key in (
        "receipt_created", "authorization_open", "data_egress_authorized",
        "provider_calls_authorized", "paid_api_authorized",
    )):
        raise RuntimeError("Phase 4B-R4 authorization must remain closed")
    if auth["stage_cost_ceiling_cny"] is not None or auth["cumulative_cost_ceiling_cny"] is not None:
        raise RuntimeError("Phase 4B-R4 cannot freeze cost ceilings with unknown orphan usage")

    r1 = load(R1_MANIFEST)
    r2 = load(R2_MANIFEST)
    if r1.get("aggregate_fingerprint") != R1_FINGERPRINT or r2.get("aggregate_fingerprint") != R2_FINGERPRINT:
        raise RuntimeError("Phase 4B-R1/R2 source fingerprint drift")
    rows = source_rows()
    starts, records, provenance = validate_r3(rows)
    recovery = build_recovery_schedule(rows)
    if len(recovery) != CALLS:
        raise RuntimeError("Phase 4B-R4 recovery row count drift")

    spent_logical = {str(row["logical_call_id"]) for row in starts}
    spent_hashes = {str(row["request_hash"]) for row in starts}
    recovery_logical = {str(row["logical_call_id"]) for row in recovery}
    recovery_hashes = {str(row["request_hash"]) for row in recovery}
    if len(recovery_logical) != CALLS or len(recovery_hashes) != CALLS:
        raise RuntimeError("Phase 4B-R4 recovery canonical identity collision")
    if spent_logical & recovery_logical or spent_hashes & recovery_hashes:
        raise RuntimeError("Phase 4B-R4 reuses a spent canonical identity")

    original_by_sequence = {int(row["sequence"]): row for row in rows}
    recovery_by_source = {int(row["source_sequence"]): row for row in recovery}
    if set(recovery_by_source) != set(range(SPENT, TOTAL + 1)):
        raise RuntimeError("Phase 4B-R4 source coverage drift")
    transport_matches = sum(
        recovery_by_source[sequence]["transport_payload_hash"] == original_by_sequence[sequence]["transport_payload_hash"]
        for sequence in range(SPENT, TOTAL + 1)
    )
    if transport_matches != CALLS:
        raise RuntimeError("Phase 4B-R4 transport preservation drift")
    orphan_transport = original_by_sequence[SPENT]["transport_payload_hash"]
    spent_transport = Counter(str(row["transport_payload_hash"]) for row in rows[:SPENT])
    recovery_transport = Counter(str(row["transport_payload_hash"]) for row in recovery)
    repeated_from_spent = sum(min(count, recovery_transport[value]) for value, count in spent_transport.items())
    if repeated_from_spent != 1 or recovery_transport[orphan_transport] != 1:
        raise RuntimeError("Phase 4B-R4 orphan transport-repeat disclosure drift")

    combined = [analysis_row(row, "r3_completed_response") for row in rows[:COMPLETED]]
    combined.extend(
        analysis_row(original_by_sequence[sequence], "r4_recovery_required", recovery_by_source[sequence])
        for sequence in range(SPENT, TOTAL + 1)
    )
    condition_counts = Counter(str(row["condition"]) for row in combined)
    if len(combined) != TOTAL or len({(row["task_id"], row["condition"]) for row in combined}) != TOTAL:
        raise RuntimeError("Phase 4B-R4 combined analysis grid drift")
    if len({str(row["task_id"]) for row in combined}) != TASKS:
        raise RuntimeError("Phase 4B-R4 combined task count drift")
    if condition_counts != Counter({condition: 20 for condition in repair.CONDITIONS}):
        raise RuntimeError("Phase 4B-R4 combined condition balance drift")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in combined:
        groups[str(row["transport_payload_hash"])].append(row)
    duplicate_groups = [group for group in groups.values() if len(group) == 2]
    if len(groups) != 80 or len(duplicate_groups) != 20:
        raise RuntimeError("Phase 4B-R4 combined transport-equivalence drift")
    if any({str(row["condition"]) for row in group} != {"global_only", "contextual_typed"} for group in duplicate_groups):
        raise RuntimeError("Phase 4B-R4 unexpected duplicate transport group")

    audit = {
        "schema_version": VERSION,
        "status": "terminal_provenance_valid",
        **provenance,
        "spent_logical_ids": len(spent_logical),
        "spent_request_hashes": len(spent_hashes),
        "response_records_reused_as_provenance": len(records),
        "r3_terminal_fingerprint": R3_FINGERPRINT,
    }
    request = {
        "schema_version": VERSION,
        "status": auth["status"],
        "requested_calls": CALLS,
        "max_provider_attempts": CALLS,
        "cost_treatment_status": auth["cost_treatment_status"],
        "stage_cost_ceiling_cny": None,
        "cumulative_cost_ceiling_cny": None,
        "fresh_live_execution_preflight_required": True,
        "fresh_exact_explicit_user_authorization_required": True,
        "orphan_transport_repeat_disclosure": {
            "source_sequence": SPENT,
            "transport_payload_hash": orphan_transport,
            "same_provider_visible_content_as_spent_orphan": True,
            "same_logical_or_request_identity": False,
            "interpretation": "A missing response is recovered under a new canonical identity, but provider-visible content is deliberately repeated once.",
        },
        "known_transport_equivalence": {
            "unique_transport_payloads_in_combined_grid": 80,
            "duplicate_pair_count": 20,
            "paired_conditions": ["global_only", "contextual_typed"],
            "causal_comparison_identifiable": False,
        },
        "forbidden_scope": cfg["forbidden_scope"],
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "zero-network-recovery-preflight-passed-closed",
        "authorization_status": request["status"],
        "source_fingerprints": cfg["source_fingerprints"],
        "r3_provenance": audit,
        "recovery_rows": len(recovery),
        "orphan_replacement_rows": 1,
        "unattempted_suffix_rows": 27,
        "new_logical_call_ids": len(recovery_logical),
        "new_request_hashes": len(recovery_hashes),
        "spent_identity_overlap": {"logical_call_ids": 0, "request_hashes": 0},
        "transport_payloads_preserved": transport_matches,
        "deliberate_spent_transport_repeats": repeated_from_spent,
        "combined_analysis_rows": len(combined),
        "combined_task_count": TASKS,
        "combined_condition_counts": dict(sorted(condition_counts.items())),
        "combined_unique_transport_payloads": len(groups),
        "combined_duplicate_transport_pairs": len(duplicate_groups),
        "global_only_contextual_typed_causal_comparison_identifiable": False,
        "analysis_gate_reached": False,
        "authorization_request": request,
        "execution": cfg["execution"],
        "bindings": {
            "config_sha256": sha256_file(CONFIG),
            "script_sha256": sha256_file(SCRIPT),
            "test_sha256": sha256_file(TEST),
            "r1_manifest_sha256": sha256_file(R1_MANIFEST),
            "r1_schedule_sha256": sha256_file(R1_SCHEDULE),
            "r1_private_gold_sha256": sha256_file(R1_GOLD),
            "r2_manifest_sha256": sha256_file(R2_MANIFEST),
            "r3_request_start_ledger_sha256": sha256_file(R3_STARTS),
            "r3_response_ledger_sha256": sha256_file(R3_LEDGER),
            "r3_closure_sha256": sha256_file(R3_CLOSURE),
            "r3_terminal_audit_sha256": sha256_file(R3_TERMINAL),
            "recovery_schedule_canonical_sha256": stable(recovery),
            "combined_analysis_plan_canonical_sha256": stable(combined),
        },
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
    return result, request, recovery, combined


def report_text(result: dict[str, Any]) -> str:
    return f"""# ACL 2027 Phase 4B-R4 recovery preflight

This zero-network recovery preflight preserves the 72 complete Phase 4B-R3 responses as provenance, excludes all 73 spent logical/request identities, and freezes 28 new canonical identities: one replacement for the orphan source row 73 and 27 rows for the unattempted source suffix 74-100.

All 28 provider-visible payloads remain byte-for-byte equivalent to their source transport projections. The orphan replacement therefore deliberately repeats one already-spent provider-visible payload under a new logical ID and request hash. This is disclosed recovery of missing response coverage, not a retry or resume of the spent canonical request identity.

The combined plan restores the frozen 100-row, 20-task, five-condition grid. It still has 80 unique transport payloads and 20 identical `global_only`/`contextual_typed` pairs, so those labels remain causally non-identifiable.

No network, provider, model, paid, Phase 4C, replication, cross-domain, or formal-scaling call was made. Because orphan usage is unknown, no stage or cumulative cost ceiling is frozen here. A separately versioned live-execution preflight and fresh exact explicit authorization are required before any provider call.

Aggregate fingerprint: `{result['aggregate_fingerprint']}`.
"""


def write_artifact(result: dict[str, Any], request: dict[str, Any], recovery: list[dict[str, Any]], combined: list[dict[str, Any]]) -> None:
    if ARTIFACT.exists():
        raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
    ARTIFACT.mkdir(parents=True)
    write(ARTIFACT / "r3_provenance_audit.json", result["r3_provenance"])
    write(ARTIFACT / "recovery_schedule.json", {"schema_version": VERSION, "rows": recovery})
    write(ARTIFACT / "combined_analysis_plan.json", {"schema_version": VERSION, "rows": combined})
    write(ARTIFACT / "authorization_request.json", request)
    write(ARTIFACT / "run_manifest.json", result)
    write(ARTIFACT / "completion_manifest.json", {
        "schema_version": VERSION,
        "experiment": result["experiment"],
        "status": "complete",
        "completion_kind": "zero_network_recovery_preflight",
        "proposed_calls": CALLS,
        "completed_calls": CALLS,
        "rows": CALLS,
        "combined_analysis_rows": TOTAL,
        "provider_calls_executed": 0,
        "authorization_status": result["authorization_status"],
        "aggregate_fingerprint": result["aggregate_fingerprint"],
        "authorization_request_sha256": sha256_file(ARTIFACT / "authorization_request.json"),
    })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result, request, recovery, combined = validate()
    if args.write_artifact:
        write_artifact(result, request, recovery, combined)
    print(render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
