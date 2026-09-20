#!/usr/bin/env python3
"""Freeze the zero-network Phase 3F response-contract and control redesign."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import (
    V17_PRIORS,
    contains_forbidden_gold_key,
    occupied_task_ids,
    public_task,
    source_candidates,
)

VERSION = 1
TARGET_FAMILIES = ("attribute_comparison", "bridge_attribute_comparison")
TASKS_PER_FAMILY = 20
CONDITIONS = (
    "cold", "global_only", "contextual_single", "irrelevant_single",
    "dual_contextual_first", "dual_irrelevant_first",
)
RESPONSE_KEYS = ("skill_assessments", "selected_skill_id", "intermediate_operation", "final_answer")
IRRELEVANT_FAMILY = {
    "attribute_comparison": "bridge_attribute_comparison",
    "bridge_attribute_comparison": "fact_retrieval",
}
SYSTEM = (
    "Answer the question from the supplied context and optional historical skill candidates. "
    "Assess every presented candidate independently. Select a candidate only when its operation "
    "is applicable to this exact question; seeing a candidate is not evidence that it applies. "
    "Select none when no candidate applies. Return exactly one JSON object and no other text or "
    "markdown. The object must contain exactly these four keys: skill_assessments (an object mapping "
    "every presented candidate ID to an object with exactly applicable: true or false), selected_skill_id "
    "(one presented ID or none), intermediate_operation (a short non-empty operation label, not hidden "
    "reasoning or chain-of-thought), and final_answer (a non-empty short string)."
)

CONFIG = ROOT / "configs/acl2027/phase3f_contract_control_redesign_v1.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3f_contract_control_redesign_v1.py"
TEST = ROOT / "tests/test_acl2027_phase3f_contract_control_redesign_v1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3f_contract_control_redesign_v1"
REPORT = ROOT / "paper/acl2027/results/phase3f_contract_control_redesign_v1.md"
PHASE3D_STRICT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_v3/specificity_analysis.json"
PHASE3D_DIAGNOSTIC = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_v3/contract_shape_diagnostic_v3_1.json"
PHASE3E_AUDIT = ROOT / "artifacts/acl2027_phase3e_control_validity_audit_v1/control_validity_audit.json"
CANDIDATE_SOURCE = ROOT / "scripts/run_acl2027_phase2_post_v23_replication_design_preflight_v24.py"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def walk_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_records(child)


def prior_identity_universe() -> dict[str, set[str]]:
    result = {"task_ids": {str(value) for value in occupied_task_ids()}, "logical_call_ids": set(), "request_hashes": set()}
    for directory in sorted(ROOT.glob("artifacts/acl2027_phase*")):
        if not directory.is_dir() or directory.name.startswith("acl2027_phase3f_"):
            continue
        for path in sorted(directory.rglob("*.json")):
            try:
                values = [load(path)]
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            for value in values:
                for row in walk_records(value):
                    for source, target in (("task_id", "task_ids"), ("logical_call_id", "logical_call_ids"), ("request_hash", "request_hashes")):
                        if row.get(source) not in (None, ""):
                            result[target].add(str(row[source]))
    return result


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase3f-v1:contract-control:{family}:{task_id}".encode()).hexdigest()


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior, pools = prior_identity_universe(), source_candidates()
    selected: list[dict[str, Any]] = []
    families: dict[str, Any] = {}
    for family in TARGET_FAMILIES:
        available = [row for row in pools[family] if str(row["task_id"]) not in prior["task_ids"]]
        ordered = sorted(available, key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])))
        if len(ordered) < TASKS_PER_FAMILY:
            raise RuntimeError(f"insufficient unused Phase 3F tasks for {family}: {len(ordered)}")
        chosen = ordered[:TASKS_PER_FAMILY]
        selected.extend(chosen)
        families[family] = {"available_after_all_prior_exclusions": len(ordered), "selected": len(chosen), "task_ids": [row["task_id"] for row in chosen]}
    task_ids = {str(row["task_id"]) for row in selected}
    return selected, {
        "schema_version": VERSION, "selector": "20 lowest SHA256(phase3f-v1:contract-control:<family>:<task_id>) unused task IDs per family",
        "selection_uses_gold": False, "families": families, "selected_tasks": len(selected), "unique_selected_task_ids": len(task_ids),
        "prior_task_universe_size": len(prior["task_ids"]), "prior_task_universe_sha256": stable(sorted(prior["task_ids"])),
        "prior_task_overlap": len(task_ids & prior["task_ids"]), "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0,
    }


def candidate_payloads(family: str, bundles: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    correct_bundle, irrelevant_family = bundles["typed"][family], IRRELEVANT_FAMILY[family]
    irrelevant_bundle = bundles["typed"][irrelevant_family]
    correct = {"candidate_id": str(correct_bundle["candidate_id"]), "role": "contextual_candidate", "target_skill_family": family, "source_skill_family": family, "source_scope": correct_bundle["source_scope"], "examples": correct_bundle["examples"]}
    irrelevant = {"candidate_id": f"candidate:phase3f-incompatible:{irrelevant_family}-to-{family}:v1", "base_candidate_id": str(irrelevant_bundle["candidate_id"]), "role": "operation_incompatible_control", "target_skill_family": family, "source_skill_family": irrelevant_family, "source_scope": "phase3f_operation_incompatible_control", "examples": irrelevant_bundle["examples"], "control_validity": "cannot_supply_required_entity_bridge" if family == "bridge_attribute_comparison" else "cross_family_comparison_control"}
    return correct, irrelevant


def candidates_for_condition(condition: str, family: str, bundles: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str]:
    correct, irrelevant = candidate_payloads(family, bundles)
    if condition == "cold": return [], "none", "none"
    if condition == "global_only":
        global_bundle = bundles["global"]
        return [{"candidate_id": str(global_bundle["candidate_id"]), "role": "global_candidate", "target_skill_family": family, "source_skill_family": "mixed", "source_scope": global_bundle["source_scope"], "examples": global_bundle["examples"]}], "none", "mixed"
    if condition == "contextual_single": return [correct], correct["candidate_id"], family
    if condition == "irrelevant_single": return [irrelevant], "none", irrelevant["source_skill_family"]
    if condition == "dual_contextual_first": return [correct, irrelevant], correct["candidate_id"], irrelevant["source_skill_family"]
    return [irrelevant, correct], correct["candidate_id"], irrelevant["source_skill_family"]


def build_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles, schedule = load(V17_PRIORS), []
    for task in tasks:
        family, public = str(task["skill_family"]), public_task(task)
        for condition in CONDITIONS:
            candidates, expected, control = candidates_for_condition(condition, family, bundles)
            candidate_ids, allowed = [str(row["candidate_id"]) for row in candidates], ["none", *[str(row["candidate_id"]) for row in candidates]]
            body = {"model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "phase": "3F", "stage": "contract_control_redesign", "partition": "contract_control_held_out", "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family, "task_id": task["task_id"], "condition": condition, "candidate_version": "phase3f-v1-design-only", "target_skill_family": family, "control_skill_family": control, "available_skill_ids": allowed, "expected_specificity_selection": expected, "candidate_order": candidate_ids, "public_payload_sha256": stable(public), "candidate_payload_sha256": stable(candidates), "prompt_template_version": "phase3f-native-mapping-json-v1", "response_contract": {"exact_keys": list(RESPONSE_KEYS), "skill_assessments": {"type": "object", "exact_candidate_id_keys": candidate_ids, "value_exact_keys": ["applicable"], "applicable_type": "boolean"}, "selected_skill_id": {"type": "string", "allowed": allowed}, "intermediate_operation": {"type": "string", "non_empty": True, "chain_of_thought": False}, "final_answer": {"type": "string", "non_empty": True}}, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Available skill IDs: " + json.dumps(allowed, ensure_ascii=True) + "\nHistorical skill candidates in assessment order:\n" + json.dumps(candidates, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n\nQuestion:\n" + str(task["question"]) + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)}]}
            sequence = len(schedule) + 1
            schedule.append({"schema_version": VERSION, "sequence": sequence, "staged_execution_index": sequence, "logical_call_id": f"phase3f-v1:contract-control:{family}:{task['task_id']}:{condition}", "request_hash": stable(body), "provider_response_id": None, "task_id": task["task_id"], "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family, "condition": condition, "candidate_order": candidate_ids, "expected_specificity_selection": expected, "target_skill_family": family, "control_skill_family": control, "candidate_payload_sha256": body["candidate_payload_sha256"], "public_payload_sha256": body["public_payload_sha256"], "canonical_request_body": body, "provenance": {"source_dataset": task["task_family"], "source_record_id": task["task_id"], "source_split": task["source_split"], "gold_is_not_request": True, "selection_used_gold": False, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0}, "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True}})
    return schedule, tasks


def identity_audit(tasks: list[dict[str, Any]], schedule: list[dict[str, Any]], selection: dict[str, Any]) -> dict[str, Any]:
    prior = prior_identity_universe()
    task_ids, logical, hashes = {str(row["task_id"]) for row in tasks}, {str(row["logical_call_id"]) for row in schedule}, {str(row["request_hash"]) for row in schedule}
    return {"schema_version": VERSION, "prior_task_ids": len(prior["task_ids"]), "prior_logical_call_ids": len(prior["logical_call_ids"]), "prior_request_hashes": len(prior["request_hashes"]), "proposed_task_ids": len(task_ids), "proposed_logical_call_ids": len(logical), "proposed_request_hashes": len(hashes), "task_id_overlap": len(task_ids & prior["task_ids"]), "logical_call_id_overlap": len(logical & prior["logical_call_ids"]), "request_hash_overlap": len(hashes & prior["request_hashes"]), "prior_task_set_sha256": selection["prior_task_universe_sha256"], "prior_logical_call_set_sha256": stable(sorted(prior["logical_call_ids"])), "prior_request_hash_set_sha256": stable(sorted(prior["request_hashes"]))}


def source_paths() -> dict[str, Path]:
    return {"candidate_source_module_sha256": CANDIDATE_SOURCE, "phase3d_strict_sha256": PHASE3D_STRICT, "phase3d_diagnostic_sha256": PHASE3D_DIAGNOSTIC, "phase3e_audit_sha256": PHASE3E_AUDIT, "preflight_source_sha256": SCRIPT, "preflight_test_sha256": TEST, "v17_prior_bundles_sha256": V17_PRIORS}


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()) or cfg["future_execution_proposal"]["status"] != "not_authorized": raise RuntimeError("Phase 3F must remain closed")
    if cfg["bindings"]["source_files"] != source_bindings(): raise RuntimeError("Phase 3F source binding drift")
    if load(PHASE3D_STRICT)["aggregate_fingerprint"] != cfg["bindings"]["phase3d_strict_fingerprint"]: raise RuntimeError("Phase 3D strict binding drift")
    if load(PHASE3D_DIAGNOSTIC)["aggregate_fingerprint"] != cfg["bindings"]["phase3d_diagnostic_fingerprint"]: raise RuntimeError("Phase 3D diagnostic binding drift")
    audit = load(PHASE3E_AUDIT)
    if audit["aggregate_fingerprint"] != cfg["bindings"]["phase3e_control_audit_fingerprint"] or audit["control_validity"]["bridge_attribute_comparison_control_valid"] is not False: raise RuntimeError("Phase 3E binding drift")
    tasks, selection = select_tasks(); schedule, private_gold = build_schedule(tasks); identities = identity_audit(tasks, schedule, selection)
    if len(tasks) != 40 or Counter(str(row["skill_family"]) for row in tasks) != Counter({family: 20 for family in TARGET_FAMILIES}): raise RuntimeError("Phase 3F task balance drift")
    if len(schedule) != 240 or len({row["logical_call_id"] for row in schedule}) != 240 or len({row["request_hash"] for row in schedule}) != 240: raise RuntimeError("Phase 3F schedule identity drift")
    if Counter(str(row["condition"]) for row in schedule) != Counter({condition: 40 for condition in CONDITIONS}): raise RuntimeError("Phase 3F condition balance drift")
    if any(identities[key] != 0 for key in ("task_id_overlap", "logical_call_id_overlap", "request_hash_overlap")): raise RuntimeError("Phase 3F prior identity overlap")
    if any(contains_forbidden_gold_key(row["canonical_request_body"]) for row in schedule): raise RuntimeError("Phase 3F private gold leaked")
    for task in tasks:
        grid = {row["condition"]: row for row in schedule if row["task_id"] == task["task_id"]}
        if set(grid) != set(CONDITIONS) or grid["dual_contextual_first"]["candidate_order"] != list(reversed(grid["dual_irrelevant_first"]["candidate_order"])): raise RuntimeError("Phase 3F dual-order drift")
        if grid["irrelevant_single"]["expected_specificity_selection"] != "none": raise RuntimeError("Phase 3F irrelevant selection drift")
        contract = grid["contextual_single"]["canonical_request_body"]["response_contract"]["skill_assessments"]
        if contract["type"] != "object" or contract["exact_candidate_id_keys"] != grid["contextual_single"]["candidate_order"]: raise RuntimeError("Phase 3F native mapping contract drift")
    result = {"schema_version": VERSION, "experiment": cfg["experiment"], "status": "design-preflight-passed-closed", "authorization_status": "not-authorized", "authorization_artifact_created": False, "config_sha256": sha256_file(CONFIG), "source_bindings": source_bindings(), "phase3d_strict_fingerprint": cfg["bindings"]["phase3d_strict_fingerprint"], "phase3d_diagnostic_fingerprint": cfg["bindings"]["phase3d_diagnostic_fingerprint"], "phase3e_control_audit_fingerprint": cfg["bindings"]["phase3e_control_audit_fingerprint"], "task_count": len(tasks), "logical_calls_proposed": len(schedule), "family_counts": dict(Counter(str(row["skill_family"]) for row in tasks)), "condition_counts": dict(Counter(str(row["condition"]) for row in schedule)), "control_families": IRRELEVANT_FAMILY, "response_schema": "candidate_id_keyed_object_mapping", "identity_overlap_audit": identities, "analysis_plan": cfg["analysis_plan"], "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "formal_scaling_calls": 0}
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any]) -> str:
    return f"""# Phase 3F contract and control redesign

This zero-network preflight repairs two Phase 3D design failures without altering its immutable negative result. The response contract now treats `skill_assessments` as the provider's candidate-ID-keyed object mapping. For bridge-attribute-comparison, the irrelevant control is fact retrieval, which has no entity-bridge operation; entity_bridge is excluded because Phase 3E proved it contaminated the original control.

The schedule freezes {result['task_count']} entirely new tasks and {result['logical_calls_proposed']} calls across six conditions. All prior task, logical-call, and request-hash overlaps are zero. The positive gate requires both selective uptake and answer mediation; no authorization was created and no calls were made.

Fingerprint: `{result['aggregate_fingerprint']}`.
"""


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    tasks, selection = select_tasks(); schedule, private_gold = build_schedule(tasks)
    documents = {"specificity_schedule.json": {"schema_version": VERSION, "schedule": schedule}, "specificity_private_gold.json": private_gold, "task_selection_audit.json": selection, "identity_overlap_audit.json": result["identity_overlap_audit"], "analysis_plan.json": result["analysis_plan"], "run_manifest.json": result, "completion_manifest.json": {"schema_version": VERSION, "experiment": result["experiment"], "status": "complete", "completion_kind": "zero_network_design_preflight", "completed_calls": 240, "rows": 240, "provider_calls_executed": 0, "authorization_status": "not-authorized", "run_manifest": "run_manifest.json", "aggregate_fingerprint": result["aggregate_fingerprint"]}}
    for name, value in documents.items(): (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--print-bindings", action="store_true"); parser.add_argument("--write-artifact", action="store_true"); args = parser.parse_args()
    if args.print_bindings: print(json.dumps(source_bindings(), indent=2, sort_keys=True)); raise SystemExit(0)
    result = validate()
    if args.write_artifact: write_artifact(result)
    print(json.dumps(result, indent=2, sort_keys=True))
