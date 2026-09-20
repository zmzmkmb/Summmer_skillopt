#!/usr/bin/env python3
"""Freeze a repaired zero-network Phase 4C held-out design; never execute it here."""
from __future__ import annotations

import argparse
import copy
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
EXPERIMENT = "acl2027_phase4c_repaired_zero_network_design_preflight_v1"
CONDITIONS = ("cold", "global_only", "contextual_typed", "shuffled_typed", "incompatible_control")
EXACT_KEYS = ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")
PHASE4A_FINGERPRINT = "2a7a6814b261ad336902fa8c4c6048a6114f62ffa242aae267a3700d0e97a2db"
DIAGNOSTIC_FINGERPRINT = "57e2588f8183e4d8682f20dcf9d587fb37fe303142be1c340b616fbef68405c7"
R6_FINGERPRINT = "80cc655e1dc70795b783ae671f55e9df064c552467db3a42295e795f46016048"
CONFIG = ROOT / "configs/acl2027/phase4c_repaired_zero_network_design_preflight_v1.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4c_repaired_zero_network_design_preflight_v1.py"
SOURCE = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1"
SOURCE_MANIFEST = SOURCE / "run_manifest.json"
SOURCE_SCHEDULE = SOURCE / "design_schedule.json"
R3_SCHEDULE = ROOT / "artifacts/acl2027_phase4b_contract_repair_preflight_v1/repaired_schedule.json"
R6_SCHEDULE = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_preflight_v4/recovery_schedule.json"
R6_ANALYSIS = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_live_v6/combined_analysis.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4c_repaired_zero_network_design_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase4c_repaired_zero_network_design_preflight_v1.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def response_contract() -> dict[str, Any]:
    return {
        "exact_keys": list(EXACT_KEYS),
        "skill_assessments": "object keyed by every presented candidate_id; each value has applicable:boolean and rationale:string",
        "selected_skill_id": "one presented candidate_id or the literal string none",
        "evidence_sentence_ids": "non-empty array of IDs copied verbatim from context[].sentences[].id",
        "extracted_operands": "object containing the evidence-grounded values used by the comparison",
        "intermediate_result": "short non-empty comparison result; do not provide hidden chain of thought",
        "final_answer": "short non-empty answer to the question",
        "forbidden": ["markdown", "code_fence", "additional_top_level_keys"],
    }


def system_message(contract: dict[str, Any]) -> str:
    return "Return exactly one JSON object and no markdown. The object MUST have exactly these six top-level keys: " + ", ".join(EXACT_KEYS) + ". Contract: " + json.dumps(contract, ensure_ascii=True, sort_keys=True) + ". Assess every presented candidate and copy evidence IDs verbatim from the annotated context."


def annotate(context: list[Any]) -> list[dict[str, Any]]:
    output = []
    for title, sentences in context:
        output.append({"title": title, "sentences": [{"id": f"{title}#{index}", "text": sentence} for index, sentence in enumerate(sentences)]})
    return output


def projected(body: dict[str, Any]) -> dict[str, Any]:
    return {"model": body["model_id"], "messages": body["messages"], "temperature": body["temperature"], "enable_thinking": False, "response_format": {"type": "json_object"}}


def transformed(candidate: dict[str, Any], scope: str) -> dict[str, Any]:
    value = copy.deepcopy(candidate)
    value["prior_scope"] = scope
    value["procedure_contract"] = "Apply the comparison direction stated in the question and return the supported entity that satisfies it."
    value["scope_note"] = "Broad family-level prior." if scope == "global" else "Task-family-typed prior with scoped procedure examples."
    return value


def build_rows() -> list[dict[str, Any]]:
    source = [row for row in load(SOURCE_SCHEDULE)["rows"] if row["split"] == "heldout"]
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in source:
        groups[str(row["task_id"])][str(row["condition"])] = row
    rows = []
    contract = response_contract()
    system = system_message(contract)
    for task_id in sorted(groups):
        group = groups[task_id]
        base_body = group["cold"]["canonical_request_body"]
        base_user = json.loads(group["cold"]["canonical_request_body"]["messages"][1]["content"])
        target_source = json.loads(group["contextual_typed"]["canonical_request_body"]["messages"][1]["content"]).get("candidates", [])
        control_source = json.loads(group["incompatible_control"]["canonical_request_body"]["messages"][1]["content"]).get("candidates", [])
        family = str(base_body["skill_family"])
        bundles = {
            "cold": [],
            "global_only": [transformed(candidate, "global") for candidate in target_source],
            "contextual_typed": [transformed(candidate, "contextual_typed") for candidate in target_source],
            "shuffled_typed": [transformed(candidate, "shuffled_control") for candidate in control_source] + [transformed(candidate, "contextual_typed") for candidate in target_source],
            "incompatible_control": [transformed(candidate, "incompatible_control") for candidate in control_source],
        }
        for condition in CONDITIONS:
            candidates = bundles[condition]
            ids = [str(candidate["candidate_id"]) for candidate in candidates]
            expected = "none" if condition == "cold" else (ids[-1] if condition == "shuffled_typed" else ids[0])
            body = {
                "model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False,
                "response_format": {"type": "json_object"}, "phase": "4C-repaired-design-v1",
                "stage": "heldout_causal_test", "split": "heldout", "task_id": task_id,
                "task_family": base_body["task_family"], "skill_family": family, "condition": condition,
                "expected_selected_skill_id": expected, "prior_scope": "none" if condition == "cold" else bundles[condition][0].get("prior_scope"),
                "response_contract": contract, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps({"available_skill_ids": ["none", *ids], "candidates": candidates, "context": annotate(base_user["context"]), "question": base_user["question"], "response_contract": contract}, ensure_ascii=True, sort_keys=True)},
                ],
            }
            payload = projected(body)
            rows.append({"schema_version": VERSION, "sequence": len(rows) + 1, "split": "heldout", "task_id": task_id, "task_family": body["task_family"], "skill_family": family, "condition": condition, "logical_call_id": f"phase4c-repaired-design-v1:{family}:{task_id}:{condition}", "request_hash": stable(body), "transport_payload_hash": stable(payload), "canonical_request_body": body, "transport_projection": payload, "provider_response_id": None, "provenance": {"source_phase4a": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}})
    return rows


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("repaired Phase 4C design must remain closed")
    if load(SOURCE_MANIFEST).get("aggregate_fingerprint") != PHASE4A_FINGERPRINT or load(R6_ANALYSIS).get("aggregate_fingerprint") != R6_FINGERPRINT:
        raise RuntimeError("source fingerprint drift")
    rows = build_rows()
    if len(rows) != 400 or len({row["logical_call_id"] for row in rows}) != 400 or len({row["request_hash"] for row in rows}) != 400:
        raise RuntimeError("repaired design identity drift")
    spent = load(R3_SCHEDULE)["rows"] + load(R6_SCHEDULE)["rows"]
    if {row["request_hash"] for row in rows} & {row["request_hash"] for row in spent} or {row["logical_call_id"] for row in rows} & {row["logical_call_id"] for row in spent}:
        raise RuntimeError("repaired design overlaps spent identities")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        body = row["canonical_request_body"]
        if stable(projected(body)) != row["transport_payload_hash"] or stable(body) != row["request_hash"]:
            raise RuntimeError("canonical or transport hash drift")
        user = json.loads(body["messages"][1]["content"])
        if not all(key in body["messages"][0]["content"] for key in EXACT_KEYS) or user["response_contract"]["exact_keys"] != list(EXACT_KEYS):
            raise RuntimeError("contract visibility drift")
        if not all(sentence.get("id") for block in user["context"] for sentence in block["sentences"]):
            raise RuntimeError("evidence ID visibility drift")
        groups[row["transport_payload_hash"]].append(row)
    duplicate = [group for group in groups.values() if len(group) == 2]
    if len(groups) != 400 or duplicate:
        raise RuntimeError("repaired design must have 400 unique transport payloads")
    counts = Counter(row["condition"] for row in rows)
    result = {"schema_version": VERSION, "experiment": EXPERIMENT, "status": "zero_network_repaired_design_passed_closed_not_authorized", "source_diagnostic_fingerprint": DIAGNOSTIC_FINGERPRINT, "source_phase4a_fingerprint": PHASE4A_FINGERPRINT, "source_phase4b_r6_analysis_fingerprint": R6_FINGERPRINT, "rows": len(rows), "heldout_tasks": len({row["task_id"] for row in rows}), "condition_counts": dict(sorted(counts.items())), "unique_transport_payloads": len(groups), "duplicate_transport_pairs": 0, "contract_visible_rows": 400, "evidence_ids_visible_rows": 400, "identity_overlap": {"logical_call_ids": 0, "request_hashes": 0}, "phase4c_live_authorized": False, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "replication_calls": 0, "cross_domain_scaling_calls": 0, "formal_scaling_calls": 0, "bindings": {"config_sha256": sha256_file(CONFIG), "script_sha256": sha256_file(SCRIPT), "test_sha256": sha256_file(TEST), "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE), "r6_analysis_sha256": sha256_file(R6_ANALYSIS), "repaired_schedule_canonical_sha256": stable(rows)}}
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    if ARTIFACT.exists():
        raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
    ARTIFACT.mkdir(parents=True)
    rows = build_rows()
    for path, value in [(ARTIFACT / "repaired_heldout_schedule.json", {"schema_version": VERSION, "rows": rows}), (ARTIFACT / "run_manifest.json", result), (ARTIFACT / "completion_manifest.json", {"schema_version": VERSION, "experiment": EXPERIMENT, "status": "complete", "completion_kind": "zero_network_repaired_design", "proposed_calls": 400, "completed_calls": 400, "rows": 400, "provider_calls_executed": 0, "phase4c_live_authorized": False, "aggregate_fingerprint": result["aggregate_fingerprint"]})]:
        path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(f"# Phase 4C repaired zero-network design preflight\n\nFrozen 80 held-out tasks and 400 new canonical requests. The repaired design embeds the exact six-field contract, annotates evidence IDs, and makes global_only/contextual_typed payloads substantively distinct by prior scope. It is not authorized and made zero external calls.\n\nFingerprint: `{result['aggregate_fingerprint']}`.\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--write-artifact", action="store_true"); args = parser.parse_args(); result = validate();
    if args.write_artifact: write_artifact(result)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
