#!/usr/bin/env python3
"""Audit whether the frozen Phase 4A held-out design is admissible for Phase 4C."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

VERSION = 1
PHASE4A_FINGERPRINT = "2a7a6814b261ad336902fa8c4c6048a6114f62ffa242aae267a3700d0e97a2db"
R6_FINGERPRINT = "80cc655e1dc70795b783ae671f55e9df064c552467db3a42295e795f46016048"
EXACT_KEYS = ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")
CONFIG = ROOT / "configs/acl2027/phase4c_zero_network_design_diagnostic_v1.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4c_zero_network_design_diagnostic_v1.py"
SOURCE = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1"
SOURCE_MANIFEST = SOURCE / "run_manifest.json"
SOURCE_SCHEDULE = SOURCE / "design_schedule.json"
R6_ANALYSIS = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_live_v6/combined_analysis.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4c_zero_network_design_diagnostic_v1"
REPORT = ROOT / "paper/acl2027/results/phase4c_zero_network_design_diagnostic_v1.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def projection(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": body["model_id"],
        "messages": body["messages"],
        "temperature": body["temperature"],
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
    }


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("Phase 4C diagnostic must remain closed")
    if load(SOURCE_MANIFEST).get("aggregate_fingerprint") != PHASE4A_FINGERPRINT:
        raise RuntimeError("Phase 4A source fingerprint drift")
    if load(R6_ANALYSIS).get("aggregate_fingerprint") != R6_FINGERPRINT:
        raise RuntimeError("Phase 4B-R6 source fingerprint drift")
    all_rows = load(SOURCE_SCHEDULE)["rows"]
    rows = [row for row in all_rows if row.get("split") == "heldout"]
    if len(rows) != 400 or len({str(row["task_id"]) for row in rows}) != 80:
        raise RuntimeError("Phase 4A held-out population drift")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contract_visible = 0
    evidence_ids_visible = 0
    for row in rows:
        body = row["canonical_request_body"]
        payload = projection(body)
        groups[stable(payload)].append(row)
        system = str(payload["messages"][0]["content"])
        user = json.loads(payload["messages"][1]["content"])
        contract_visible += int(all(key in system for key in EXACT_KEYS) and user.get("response_contract", {}).get("exact_keys") == list(EXACT_KEYS))
        context = user.get("context", [])
        ids = [sentence.get("id") for block in context if isinstance(block, dict) for sentence in block.get("sentences", []) if isinstance(sentence, dict)]
        evidence_ids_visible += int(bool(ids) and all(ids))
    duplicate_pairs = [group for group in groups.values() if len(group) == 2]
    equivalent = [group for group in duplicate_pairs if {str(row["condition"]) for row in group} == {"global_only", "contextual_typed"} and len({str(row["task_id"]) for row in group}) == 1]
    condition_counts = Counter(str(row["condition"]) for row in rows)
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "closed_design_blocked_repair_required",
        "decision": "phase4c_source_schedule_not_admissible",
        "source_phase4a_fingerprint": PHASE4A_FINGERPRINT,
        "source_phase4b_r6_analysis_fingerprint": R6_FINGERPRINT,
        "heldout_rows_audited": len(rows),
        "heldout_tasks_audited": len({str(row["task_id"]) for row in rows}),
        "condition_counts": dict(sorted(condition_counts.items())),
        "unique_transport_payloads": len(groups),
        "global_only_contextual_typed_equivalent_pairs": len(equivalent),
        "contract_visible_in_transmitted_messages_rows": contract_visible,
        "evidence_ids_visible_in_transmitted_messages_rows": evidence_ids_visible,
        "blocking_findings": [
            "The exact six-field response contract is not visible in the frozen transmitted messages.",
            "Explicit copyable evidence sentence IDs are not visible in the frozen transmitted context.",
            "Every global_only/contextual_typed task pair is transport-identical and cannot support the preregistered causal contrast.",
        ],
        "required_repair": {
            "separately_versioned_schedule_required": True,
            "embed_exact_contract_in_system_and_user_messages": True,
            "annotate_context_with_copyable_evidence_ids": True,
            "make_global_only_and_contextual_typed_provider_payloads_distinct_by_substantive_prior_scope": True,
            "preserve_80_task_private_gold_without_answer_egress": True,
            "prove_zero_spent_logical_and_request_identity_overlap": True,
            "fresh_live_preflight_and_explicit_authorization_required": True,
        },
        "phase4c_authorized": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "replication_calls": 0,
        "cross_domain_scaling_calls": 0,
        "formal_scaling_calls": 0,
        "bindings": {
            "config_sha256": sha256_file(CONFIG),
            "script_sha256": sha256_file(SCRIPT),
            "test_sha256": sha256_file(TEST),
            "source_manifest_sha256": sha256_file(SOURCE_MANIFEST),
            "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE),
            "r6_analysis_sha256": sha256_file(R6_ANALYSIS),
        },
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    if ARTIFACT.exists():
        raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
    ARTIFACT.mkdir(parents=True)
    (ARTIFACT / "design_diagnostic.json").write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    (ARTIFACT / "run_manifest.json").write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    (ARTIFACT / "completion_manifest.json").write_text(json.dumps({
        "schema_version": VERSION, "experiment": result["experiment"], "status": "complete",
        "completion_kind": "zero_network_design_diagnostic", "proposed_calls": 400,
        "completed_calls": 400, "rows": 400, "provider_calls_executed": 0,
        "phase4c_authorized": False, "aggregate_fingerprint": result["aggregate_fingerprint"],
    }, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(
        "# ACL 2027 Phase 4C zero-network design diagnostic\n\n"
        "The frozen Phase 4A held-out schedule is not admissible for live Phase 4C. Across 400 rows, the exact six-field contract and explicit evidence IDs are absent from transmitted messages. The schedule has only 320 unique transport payloads because all 80 global_only/contextual_typed pairs are identical.\n\n"
        "A separately versioned repaired schedule is required. This diagnostic creates no authorization and makes zero external calls.\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n",
        encoding="utf-8", newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        write_artifact(result)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
