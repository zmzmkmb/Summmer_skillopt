#!/usr/bin/env python3
"""Build the zero-network ACL 2027 Phase 3D specificity preflight v1."""
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
    "cold",
    "global_only",
    "contextual_single",
    "irrelevant_single",
    "dual_contextual_first",
    "dual_irrelevant_first",
)
RESPONSE_KEYS = (
    "skill_assessments",
    "selected_skill_id",
    "intermediate_operation",
    "final_answer",
)
IRRELEVANT_FAMILY = {
    "attribute_comparison": "bridge_attribute_comparison",
    "bridge_attribute_comparison": "entity_bridge",
}
SYSTEM = (
    "Answer the question from the supplied context and optional historical skill candidates. "
    "Assess every presented candidate independently. Select a candidate only when its operation "
    "is applicable to this exact question; seeing a candidate is not evidence that it applies. "
    "Select none when no candidate applies. Return exactly one JSON object and no other text or "
    "markdown. The object must contain exactly these four keys: skill_assessments (one object per "
    "presented candidate in presentation order, each with exactly skill_id and applicable), "
    "selected_skill_id (one presented ID or none), intermediate_operation (a short non-empty "
    "operation label, not hidden reasoning or chain-of-thought), and final_answer (a non-empty "
    "short string)."
)

CONFIG = ROOT / "configs/acl2027/phase3d_specificity_abstention_preflight_v1.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3d_specificity_abstention_preflight_v1.py"
TEST = ROOT / "tests/test_acl2027_phase3d_specificity_abstention_preflight_v1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase3d_specificity_abstention_preflight_v1.md"
PHASE3B_PREFLIGHT = ROOT / "artifacts/acl2027_phase3b_activation_preflight_v1/run_manifest.json"
PHASE3B_ANALYSIS = ROOT / "artifacts/acl2027_phase3b_activation_recovery_live_v5/activation_analysis.json"
PHASE3C_CONFIG = ROOT / "configs/acl2027/phase3c_uptake_outcome_mediation_audit_v1.json"
PHASE3C_AUDIT = ROOT / "artifacts/acl2027_phase3c_uptake_outcome_mediation_audit_v1/mediation_audit.json"
CANDIDATE_SOURCE = ROOT / "scripts/run_acl2027_phase2_post_v23_replication_design_preflight_v24.py"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def walk_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_records(child)


def prior_identity_universe() -> dict[str, set[str]]:
    result = {
        "task_ids": set(str(value) for value in occupied_task_ids()),
        "logical_call_ids": set(),
        "request_hashes": set(),
    }
    patterns = (
        "artifacts/acl2027_phase2*",
        "artifacts/acl2027_phase3a*",
        "artifacts/acl2027_phase3b*",
        "artifacts/acl2027_phase3c*",
    )
    for pattern in patterns:
        for directory in sorted(ROOT.glob(pattern)):
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
                    continue
                try:
                    if path.suffix.lower() == ".jsonl":
                        values = [
                            json.loads(line)
                            for line in path.read_text(encoding="utf-8-sig").splitlines()
                            if line.strip()
                        ]
                    else:
                        values = [load(path)]
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                for value in values:
                    for row in walk_records(value):
                        for source, target in (
                            ("task_id", "task_ids"),
                            ("logical_call_id", "logical_call_ids"),
                            ("request_hash", "request_hashes"),
                        ):
                            if row.get(source) not in (None, ""):
                                result[target].add(str(row[source]))
    return result


def selector_hash(family: str, task_id: str) -> str:
    text = f"phase3d-v1:specificity-abstention:{family}:{task_id}"
    return hashlib.sha256(text.encode()).hexdigest()


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pools = source_candidates()
    prior = prior_identity_universe()
    selected: list[dict[str, Any]] = []
    families: dict[str, Any] = {}
    for family in TARGET_FAMILIES:
        available = [row for row in pools[family] if str(row["task_id"]) not in prior["task_ids"]]
        ordered = sorted(
            available,
            key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])),
        )
        if len(ordered) < TASKS_PER_FAMILY:
            raise RuntimeError(f"insufficient unused Phase 3D tasks for {family}: {len(ordered)}")
        chosen = ordered[:TASKS_PER_FAMILY]
        selected.extend(chosen)
        families[family] = {
            "available_after_all_prior_exclusions": len(ordered),
            "selected": len(chosen),
            "task_ids": [row["task_id"] for row in chosen],
            "selector_hashes": [selector_hash(family, str(row["task_id"])) for row in chosen],
        }
    task_ids = {str(row["task_id"]) for row in selected}
    return selected, {
        "schema_version": VERSION,
        "selector": "20 lowest SHA256(phase3d-v1:specificity-abstention:<family>:<task_id>) per family",
        "selection_uses_gold": False,
        "families": families,
        "selected_tasks": len(selected),
        "unique_selected_task_ids": len(task_ids),
        "prior_task_universe_size": len(prior["task_ids"]),
        "prior_task_universe_sha256": stable(sorted(prior["task_ids"])),
        "prior_task_overlap": len(task_ids & prior["task_ids"]),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }


def candidate_payloads(family: str, bundles: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    correct_bundle = bundles["typed"][family]
    irrelevant_family = IRRELEVANT_FAMILY[family]
    irrelevant_bundle = bundles["typed"][irrelevant_family]
    correct = {
        "candidate_id": str(correct_bundle["candidate_id"]),
        "role": "contextual_candidate",
        "target_skill_family": family,
        "source_skill_family": family,
        "source_scope": correct_bundle["source_scope"],
        "examples": correct_bundle["examples"],
    }
    irrelevant = {
        "candidate_id": f"candidate:phase3d-irrelevant:{irrelevant_family}-to-{family}:v1",
        "base_candidate_id": str(irrelevant_bundle["candidate_id"]),
        "role": "irrelevant_candidate",
        "target_skill_family": family,
        "source_skill_family": irrelevant_family,
        "source_scope": "observed_phase3b_universal_uptake_control",
        "examples": irrelevant_bundle["examples"],
    }
    return correct, irrelevant


def candidates_for_condition(
    condition: str, family: str, bundles: dict[str, Any]
) -> tuple[list[dict[str, Any]], str, str]:
    correct, irrelevant = candidate_payloads(family, bundles)
    if condition == "cold":
        return [], "none", "none"
    if condition == "global_only":
        global_bundle = bundles["global"]
        return [{
            "candidate_id": str(global_bundle["candidate_id"]),
            "role": "global_candidate",
            "target_skill_family": family,
            "source_skill_family": "mixed",
            "source_scope": global_bundle["source_scope"],
            "examples": global_bundle["examples"],
        }], "none", "mixed"
    if condition == "contextual_single":
        return [correct], correct["candidate_id"], family
    if condition == "irrelevant_single":
        return [irrelevant], "none", irrelevant["source_skill_family"]
    if condition == "dual_contextual_first":
        return [correct, irrelevant], correct["candidate_id"], irrelevant["source_skill_family"]
    return [irrelevant, correct], correct["candidate_id"], irrelevant["source_skill_family"]


def build_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = load(V17_PRIORS)
    schedule: list[dict[str, Any]] = []
    for task in tasks:
        family = str(task["skill_family"])
        public = public_task(task)
        for condition in CONDITIONS:
            candidates, expected_selection, control_family = candidates_for_condition(condition, family, bundles)
            candidate_ids = [str(row["candidate_id"]) for row in candidates]
            allowed = ["none", *candidate_ids]
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "3D",
                "stage": "specificity_abstention_preflight",
                "partition": "specificity_repair_held_out",
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "task_id": task["task_id"],
                "condition": condition,
                "candidate_version": "phase3d-v1-design-only",
                "target_skill_family": family,
                "control_skill_family": control_family,
                "available_skill_ids": allowed,
                "expected_specificity_selection": expected_selection,
                "candidate_order": candidate_ids,
                "public_payload_sha256": stable(public),
                "candidate_payload_sha256": stable(candidates),
                "prompt_template_version": "phase3d-specificity-abstention-json-v1",
                "response_contract": {
                    "exact_keys": list(RESPONSE_KEYS),
                    "skill_assessments": {
                        "type": "array",
                        "length": len(candidates),
                        "item_exact_keys": ["skill_id", "applicable"],
                        "skill_id_order": candidate_ids,
                    },
                    "selected_skill_id": {"type": "string", "allowed": allowed},
                    "intermediate_operation": {"type": "string", "non_empty": True, "chain_of_thought": False},
                    "final_answer": {"type": "string", "non_empty": True},
                },
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            "Available skill IDs: " + json.dumps(allowed, ensure_ascii=True) +
                            "\nHistorical skill candidates in assessment order:\n" +
                            json.dumps(candidates, ensure_ascii=True, sort_keys=True, separators=(",", ":")) +
                            "\n\nQuestion:\n" + str(task["question"]) +
                            "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)
                        ),
                    },
                ],
            }
            sequence = len(schedule) + 1
            schedule.append({
                "schema_version": VERSION,
                "sequence": sequence,
                "staged_execution_index": sequence,
                "logical_call_id": f"phase3d-v1:specificity:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "provider_response_id": None,
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "condition": condition,
                "candidate_order": candidate_ids,
                "expected_specificity_selection": expected_selection,
                "target_skill_family": family,
                "control_skill_family": control_family,
                "candidate_payload_sha256": body["candidate_payload_sha256"],
                "public_payload_sha256": body["public_payload_sha256"],
                "canonical_request_body": body,
                "provenance": {
                    "source_dataset": task["task_family"],
                    "source_record_id": task["task_id"],
                    "source_split": task["source_split"],
                    "gold_is_not_request": True,
                    "selection_used_gold": False,
                    "network_calls": 0,
                    "provider_calls": 0,
                    "model_calls": 0,
                    "paid_api_calls": 0,
                },
                "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
            })
    return schedule, tasks


def identity_audit(
    tasks: list[dict[str, Any]], schedule: list[dict[str, Any]], selection: dict[str, Any]
) -> dict[str, Any]:
    prior = prior_identity_universe()
    task_ids = {str(row["task_id"]) for row in tasks}
    logical = {str(row["logical_call_id"]) for row in schedule}
    hashes = {str(row["request_hash"]) for row in schedule}
    return {
        "schema_version": VERSION,
        "prior_task_ids": len(prior["task_ids"]),
        "prior_logical_call_ids": len(prior["logical_call_ids"]),
        "prior_request_hashes": len(prior["request_hashes"]),
        "proposed_task_ids": len(task_ids),
        "proposed_logical_call_ids": len(logical),
        "proposed_request_hashes": len(hashes),
        "task_id_overlap": len(task_ids & prior["task_ids"]),
        "logical_call_id_overlap": len(logical & prior["logical_call_ids"]),
        "request_hash_overlap": len(hashes & prior["request_hashes"]),
        "prior_task_set_sha256": selection["prior_task_universe_sha256"],
        "prior_logical_call_set_sha256": stable(sorted(prior["logical_call_ids"])),
        "prior_request_hash_set_sha256": stable(sorted(prior["request_hashes"])),
    }


def source_paths() -> dict[str, Path]:
    return {
        "candidate_source_module_sha256": CANDIDATE_SOURCE,
        "phase3b_analysis_sha256": PHASE3B_ANALYSIS,
        "phase3b_preflight_manifest_sha256": PHASE3B_PREFLIGHT,
        "phase3c_audit_sha256": PHASE3C_AUDIT,
        "phase3c_config_sha256": PHASE3C_CONFIG,
        "preflight_source_sha256": SCRIPT,
        "preflight_test_sha256": TEST,
        "v17_prior_bundles_sha256": V17_PRIORS,
    }


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def analysis_plan() -> dict[str, Any]:
    return load(CONFIG)["analysis_plan"]


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("Phase 3D execution switches must remain closed")
    if cfg["future_execution_proposal"]["status"] != "not_authorized":
        raise RuntimeError("Phase 3D cannot imply provider authorization")
    actual_bindings = source_bindings()
    if actual_bindings != cfg["bindings"]["source_files"]:
        raise RuntimeError("Phase 3D source binding drift")

    phase3b = load(PHASE3B_ANALYSIS)
    phase3c = load(PHASE3C_AUDIT)
    if phase3b["aggregate_fingerprint"] != cfg["bindings"]["phase3b_aggregate_fingerprint"]:
        raise RuntimeError("Phase 3B aggregate fingerprint drift")
    if phase3c["aggregate_fingerprint"] != cfg["bindings"]["phase3c_aggregate_fingerprint"]:
        raise RuntimeError("Phase 3C aggregate fingerprint drift")
    if phase3c["decision_gate"] != "inconclusive" or not phase3c["specificity_warning_fired"]:
        raise RuntimeError("Phase 3D requires the frozen Phase 3C specificity diagnosis")

    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    family_counts = Counter(str(row["skill_family"]) for row in tasks)
    condition_counts = Counter(str(row["condition"]) for row in schedule)
    expected_families = Counter({family: TASKS_PER_FAMILY for family in TARGET_FAMILIES})
    if len(tasks) != 40 or len({row["task_id"] for row in tasks}) != 40:
        raise RuntimeError("Phase 3D task count drift")
    if family_counts != expected_families:
        raise RuntimeError("Phase 3D family balance drift")
    if len(schedule) != 240:
        raise RuntimeError("Phase 3D request count drift")
    if len({row["logical_call_id"] for row in schedule}) != 240:
        raise RuntimeError("Phase 3D logical identity drift")
    if len({row["request_hash"] for row in schedule}) != 240:
        raise RuntimeError("Phase 3D request hash drift")
    if condition_counts != Counter({condition: 40 for condition in CONDITIONS}):
        raise RuntimeError("Phase 3D condition balance drift")
    if [row["staged_execution_index"] for row in schedule] != list(range(1, 241)):
        raise RuntimeError("Phase 3D exact sequence drift")
    if any(contains_forbidden_gold_key(row["canonical_request_body"]) for row in schedule):
        raise RuntimeError("Phase 3D private gold leaked into a canonical request")
    if any(identities[key] != 0 for key in ("task_id_overlap", "logical_call_id_overlap", "request_hash_overlap")):
        raise RuntimeError("Phase 3D identity overlap audit failed")

    for task in tasks:
        grid = [row for row in schedule if row["task_id"] == task["task_id"]]
        if {row["condition"] for row in grid} != set(CONDITIONS):
            raise RuntimeError("Phase 3D task grid is incomplete")
        by_condition = {row["condition"]: row for row in grid}
        contextual = by_condition["contextual_single"]
        irrelevant = by_condition["irrelevant_single"]
        contextual_first = by_condition["dual_contextual_first"]
        irrelevant_first = by_condition["dual_irrelevant_first"]
        if len(contextual["candidate_order"]) != 1 or contextual["expected_specificity_selection"] == "none":
            raise RuntimeError("Phase 3D contextual candidate semantics drift")
        if len(irrelevant["candidate_order"]) != 1 or irrelevant["expected_specificity_selection"] != "none":
            raise RuntimeError("Phase 3D irrelevant rejection semantics drift")
        if contextual_first["candidate_order"] != list(reversed(irrelevant_first["candidate_order"])):
            raise RuntimeError("Phase 3D dual order control drift")
        if contextual_first["expected_specificity_selection"] != irrelevant_first["expected_specificity_selection"]:
            raise RuntimeError("Phase 3D dual expected selection drift")

    documents = {
        "specificity_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "specificity_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": identities,
        "analysis_plan.json": analysis_plan(),
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "design-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "authorization_artifact_created": False,
        "config_sha256": sha256_file(CONFIG),
        "source_bindings": actual_bindings,
        "phase3b_aggregate_fingerprint": phase3b["aggregate_fingerprint"],
        "phase3c_aggregate_fingerprint": phase3c["aggregate_fingerprint"],
        "phase3c_gate_preserved": phase3c["decision_gate"],
        "specificity_warning_bound": phase3c["specificity_warning_fired"],
        "task_count": len(tasks),
        "tasks_per_family": TASKS_PER_FAMILY,
        "family_counts": dict(family_counts),
        "condition_counts": dict(condition_counts),
        "logical_calls_proposed": len(schedule),
        "unique_task_ids": len({row["task_id"] for row in tasks}),
        "unique_logical_call_ids": len({row["logical_call_id"] for row in schedule}),
        "unique_request_hashes": len({row["request_hash"] for row in schedule}),
        "prior_task_overlap": 0,
        "prior_logical_call_overlap": 0,
        "prior_request_hash_overlap": 0,
        "response_contract_keys": list(RESPONSE_KEYS),
        "analysis_plan": analysis_plan(),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "formal_scaling_calls": 0,
        "documents": {name: rendered_sha256(value) for name, value in documents.items()},
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any], selection: dict[str, Any]) -> str:
    capacities = ", ".join(
        f"{family}={selection['families'][family]['available_after_all_prior_exclusions']}"
        for family in TARGET_FAMILIES
    )
    return (
        "# ACL 2027 Phase 3D specificity and abstention preflight v1\n\n"
        "## Scope\n\n"
        "This is a zero-network design preflight responding to the frozen Phase 3C specificity warning. It creates no authorization and makes no provider, model, paid, or formal-scaling call.\n\n"
        "## Frozen specificity repair\n\n"
        "The design selects 40 entirely new tasks, 20 each from attribute comparison and bridge attribute comparison, and expands them into 240 requests. It presents cold, global-only, contextual-only, irrelevant-only, and two dual-candidate order conditions. Every presented candidate receives an explicit applicability assessment, and `none` remains a valid selection.\n\n"
        f"Available candidates after all prior exclusions: `{capacities}`. Task, logical-call, and request-hash overlaps with all scanned Phase 2/3A/3B/3C identities are zero. Private gold is separate from every canonical request.\n\n"
        "## Frozen gate\n\n"
        "The positive gate jointly requires correct contextual selection, rejection of irrelevant-only bundles, correct dual-candidate selection under both orders, a bounded order effect, operation and answer changes, alias net wins over the irrelevant control, and non-regression versus cold. Passing specificity without outcome mediation is not sufficient for cross-domain scaling.\n\n"
        "## Execution boundary\n\n"
        "The 240-call schedule is a proposal only. A separate explicit authorization must bind this exact fingerprint before any provider call. No authorization receipt or open authorization file exists.\n\n"
        "## Integrity\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`. Network/provider/model/paid/formal-scaling counters: `0/0/0/0/0`. Authorization status: `not-authorized`.\n"
    )


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    documents = {
        "specificity_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "specificity_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": identities,
        "analysis_plan.json": analysis_plan(),
        "run_manifest.json": result,
        "completion_manifest.json": {
            "schema_version": VERSION,
            "experiment": result["experiment"],
            "status": "complete",
            "completion_kind": "zero_network_design_preflight",
            "completed_calls": 240,
            "rows": 240,
            "provider_calls_executed": 0,
            "authorization_status": "not-authorized",
            "run_manifest": "run_manifest.json",
            "aggregate_fingerprint": result["aggregate_fingerprint"],
        },
    }
    for name, value in documents.items():
        (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result, selection), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-bindings", action="store_true")
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    if args.print_bindings:
        print(json.dumps(source_bindings(), indent=2, sort_keys=True))
        raise SystemExit(0)
    validated = validate()
    if args.write_artifact:
        write_artifact(validated)
    print(json.dumps(validated, indent=2, sort_keys=True))
