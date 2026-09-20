#!/usr/bin/env python3
"""Freeze the zero-network Phase 3H counterfactual answer-sensitivity design."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import (
    SOURCE_2WIKI,
    V17_PRIORS,
    contains_forbidden_gold_key,
    occupied_task_ids,
    source_candidates,
)

VERSION = 1
EXPERIMENT = "acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1"
TARGET_FAMILIES = ("attribute_comparison", "bridge_attribute_comparison")
TASKS_PER_FAMILY = 20
CONDITIONS = (
    "cold",
    "contextual",
    "incompatible_control",
    "dual_contextual_first",
    "dual_control_first",
)
RESPONSE_KEYS = (
    "skill_assessments",
    "selected_skill_id",
    "intermediate_operation",
    "final_answer",
)
SYSTEM = (
    "Answer from the supplied context and optional procedure candidates. Assess every "
    "candidate independently for compatibility with the question. selected_skill_id is "
    "the procedure actually executed: in forced_candidate mode execute the sole presented "
    "candidate even when it is incompatible; in semantic_selection mode execute the compatible "
    "candidate. Return exactly one JSON object with exactly four keys: skill_assessments "
    "(a candidate-ID-keyed object whose value is exactly {applicable: boolean}), "
    "selected_skill_id, intermediate_operation (a short observable operation/result label, "
    "not chain-of-thought), and final_answer (a non-empty short string)."
)

CONFIG = ROOT / "configs/acl2027/phase3h_counterfactual_answer_sensitivity_preflight_v1.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1.py"
TEST = ROOT / "tests/test_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase3h_counterfactual_answer_sensitivity_preflight_v1.md"
PHASE3F_STRICT = ROOT / "artifacts/acl2027_phase3f_live_v2/specificity_analysis.json"
PHASE3F_DIAGNOSTIC = ROOT / "artifacts/acl2027_phase3f_live_v2/mapping_shape_diagnostic_v1.json"
PHASE3G_REPORT = ROOT / "paper/acl2027/results/phase3g_answer_grounding_audit_v1.md"
CANDIDATE_SOURCE = ROOT / "scripts/run_acl2027_phase2_post_v23_replication_design_preflight_v24.py"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


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
        "task_ids": {str(value) for value in occupied_task_ids()},
        "logical_call_ids": set(),
        "request_hashes": set(),
    }
    for directory in sorted(ROOT.glob("artifacts/acl2027_phase*")):
        if not directory.is_dir() or directory.resolve() == ARTIFACT.resolve():
            continue
        for path in sorted(directory.rglob("*.json")):
            try:
                value = load(path)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            for row in walk_records(value):
                for source, target in (
                    ("task_id", "task_ids"),
                    ("logical_call_id", "logical_call_ids"),
                    ("request_hash", "request_hashes"),
                ):
                    if row.get(source) not in (None, ""):
                        result[target].add(str(row[source]))
    return result


def evidence_record(task: dict[str, Any], title: str, sentence_index: int) -> dict[str, Any] | None:
    for context_title, sentences in task["context"]:
        if normalize(context_title) != normalize(title):
            continue
        if not isinstance(sentence_index, int) or not 0 <= sentence_index < len(sentences):
            return None
        return {"title": context_title, "sentence_index": sentence_index, "sentence": sentences[sentence_index]}
    return None


def counterfactual_task(task: dict[str, Any]) -> dict[str, Any] | None:
    supports = task.get("supporting_evidence")
    if not isinstance(supports, list) or len(supports) < 2:
        return None
    unique_titles: list[str] = []
    for item in supports:
        if not isinstance(item, list) or len(item) != 2:
            return None
        title = str(item[0])
        if normalize(title) not in {normalize(value) for value in unique_titles}:
            unique_titles.append(title)
    compared = unique_titles[:2]
    if len(compared) != 2 or normalize(compared[0]) == normalize(compared[1]):
        return None
    answer = str(task.get("answer", ""))
    matches = [index for index, title in enumerate(compared) if normalize(title) == normalize(answer)]
    if len(matches) != 1:
        return None
    target_index = matches[0]
    control_index = 1 - target_index

    support_records: list[dict[str, Any]] = []
    for title, sentence_index in supports:
        record = evidence_record(task, str(title), int(sentence_index))
        if record is None:
            return None
        support_records.append(record)
    target_positions = [target_index]
    control_positions = [control_index]
    if task["skill_family"] == "bridge_attribute_comparison":
        if len(support_records) < 4:
            return None
        target_positions.append(target_index + 2)
        control_positions.append(control_index + 2)
    target_evidence = [support_records[index] for index in target_positions]
    control_evidence = [support_records[index] for index in control_positions]
    target_value = [record["sentence"] for record in target_evidence]
    control_value = [record["sentence"] for record in control_evidence]
    if stable(target_value) == stable(control_value):
        return None

    return {
        **task,
        "compared_entities": compared,
        "target_answer": answer,
        "counterfactual_answer": compared[control_index],
        "target_entity_index": target_index,
        "counterfactual_entity_index": control_index,
        "target_intermediate_evidence": target_evidence,
        "counterfactual_intermediate_evidence": control_evidence,
        "target_intermediate_value": target_value,
        "counterfactual_intermediate_value": control_value,
        "counterfactual_validity": {
            "distinct_normalized_answers": normalize(answer) != normalize(compared[control_index]),
            "distinct_evidence_values": True,
            "both_answers_preregistered": True,
            "both_answers_source_verifiable": True,
        },
    }


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase3h-v1:counterfactual-answer:{family}:{task_id}".encode()).hexdigest()


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior = prior_identity_universe()
    pools = source_candidates()
    selected: list[dict[str, Any]] = []
    families: dict[str, Any] = {}
    for family in TARGET_FAMILIES:
        eligible = []
        for row in pools[family]:
            if str(row["task_id"]) in prior["task_ids"]:
                continue
            enriched = counterfactual_task(row)
            if enriched is not None:
                eligible.append(enriched)
        ordered = sorted(
            eligible,
            key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])),
        )
        if len(ordered) < TASKS_PER_FAMILY:
            raise RuntimeError(f"insufficient unused counterfactually identifiable tasks for {family}: {len(ordered)}")
        chosen = ordered[:TASKS_PER_FAMILY]
        selected.extend(chosen)
        families[family] = {
            "available_after_all_prior_exclusions_and_identifiability": len(ordered),
            "selected": len(chosen),
            "task_ids": [row["task_id"] for row in chosen],
            "selector_hashes": [selector_hash(family, str(row["task_id"])) for row in chosen],
        }
    selected_ids = {str(row["task_id"]) for row in selected}
    audit = {
        "schema_version": VERSION,
        "selector": "20 lowest SHA256(phase3h-v1:counterfactual-answer:<family>:<task_id>) eligible unused IDs per family",
        "eligibility_rule": "gold answer matches exactly one of the first two supporting entities; the other entity is a distinct source-verifiable counterfactual answer; both evidence traces are non-empty and distinct",
        "selection_uses_gold_for_identifiability_only": True,
        "gold_excluded_from_requests": True,
        "families": families,
        "selected_tasks": len(selected),
        "unique_selected_task_ids": len(selected_ids),
        "prior_task_universe_size": len(prior["task_ids"]),
        "prior_task_universe_sha256": stable(sorted(prior["task_ids"])),
        "prior_task_overlap": len(selected_ids & prior["task_ids"]),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }
    return selected, audit


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: task[key]
        for key in ("task_id", "task_family", "task_type", "skill_family", "question", "context", "source_split")
    }


def candidate_payloads(family: str) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load(V17_PRIORS)["typed"][family]
    target = {
        "candidate_id": f"candidate:phase3h-target:{family}:v1",
        "base_candidate_id": str(base["candidate_id"]),
        "role": "contextual_target_procedure",
        "target_skill_family": family,
        "procedure_contract": "Apply the comparison direction stated in the question and return the supported entity that satisfies it.",
        "examples": base["examples"],
    }
    control = {
        "candidate_id": f"candidate:phase3h-inverse-control:{family}:v1",
        "role": "operation_incompatible_counterfactual_control",
        "target_skill_family": family,
        "procedure_contract": "Invert the comparison direction stated in the question and return the other supported comparison entity.",
        "examples": [],
        "control_validity": "forces a distinct preregistered answer while remaining incompatible with the original question semantics",
    }
    return target, control


def candidates_for_condition(condition: str, family: str) -> tuple[list[dict[str, Any]], str, str]:
    target, control = candidate_payloads(family)
    if condition == "cold":
        return [], "none", "unassisted"
    if condition == "contextual":
        return [target], target["candidate_id"], "forced_candidate"
    if condition == "incompatible_control":
        return [control], control["candidate_id"], "forced_candidate"
    if condition == "dual_contextual_first":
        return [target, control], target["candidate_id"], "semantic_selection"
    return [control, target], target["candidate_id"], "semantic_selection"


def build_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schedule: list[dict[str, Any]] = []
    for task in tasks:
        public = public_task(task)
        family = str(task["skill_family"])
        target_candidate, control_candidate = candidate_payloads(family)
        for condition in CONDITIONS:
            candidates, expected, mode = candidates_for_condition(condition, family)
            candidate_ids = [str(row["candidate_id"]) for row in candidates]
            allowed = ["none", *candidate_ids]
            applicability = {
                candidate_id: candidate_id == target_candidate["candidate_id"]
                for candidate_id in candidate_ids
            }
            instruction = {
                "unassisted": "No procedure candidate is available; answer the original question normally.",
                "forced_candidate": "Execute the sole presented procedure candidate. Still report whether it is semantically applicable to the original question.",
                "semantic_selection": "Select and execute the candidate compatible with the original question; reject the inverse procedure.",
            }[mode]
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "3H",
                "stage": "counterfactual_answer_sensitivity_preflight",
                "partition": "counterfactual_answer_sensitive_held_out",
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "task_id": task["task_id"],
                "condition": condition,
                "execution_mode": mode,
                "condition_instruction": instruction,
                "candidate_version": "phase3h-v1-design-only",
                "available_skill_ids": allowed,
                "expected_selected_skill_id": expected,
                "candidate_order": candidate_ids,
                "public_payload_sha256": stable(public),
                "candidate_payload_sha256": stable(candidates),
                "prompt_template_version": "phase3h-counterfactual-grounding-native-mapping-v1",
                "response_contract": {
                    "exact_keys": list(RESPONSE_KEYS),
                    "skill_assessments": {
                        "type": "object",
                        "exact_candidate_id_keys": candidate_ids,
                        "value_exact_keys": ["applicable"],
                        "applicable_type": "boolean",
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
                            "Condition instruction: " + instruction
                            + "\nAvailable skill IDs: " + json.dumps(allowed, ensure_ascii=True)
                            + "\nProcedure candidates in assessment order:\n"
                            + json.dumps(candidates, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                            + "\n\nQuestion:\n" + str(task["question"])
                            + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)
                        ),
                    },
                ],
            }
            sequence = len(schedule) + 1
            schedule.append({
                "schema_version": VERSION,
                "sequence": sequence,
                "staged_execution_index": sequence,
                "logical_call_id": f"phase3h-v1:counterfactual-answer:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "provider_response_id": None,
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "condition": condition,
                "execution_mode": mode,
                "candidate_order": candidate_ids,
                "expected_selected_skill_id": expected,
                "expected_applicability": applicability,
                "target_candidate_id": target_candidate["candidate_id"],
                "control_candidate_id": control_candidate["candidate_id"],
                "candidate_payload_sha256": body["candidate_payload_sha256"],
                "public_payload_sha256": body["public_payload_sha256"],
                "canonical_request_body": body,
                "provenance": {
                    "source_dataset": task["task_family"],
                    "source_record_id": task["task_id"],
                    "source_split": task["source_split"],
                    "gold_is_not_request": True,
                    "selection_used_gold_for_identifiability_only": True,
                    "network_calls": 0,
                    "provider_calls": 0,
                    "model_calls": 0,
                    "paid_api_calls": 0,
                },
                "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
            })
    return schedule, tasks


def identity_audit(tasks: list[dict[str, Any]], schedule: list[dict[str, Any]], selection: dict[str, Any]) -> dict[str, Any]:
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
        "phase3f_strict_sha256": PHASE3F_STRICT,
        "phase3f_diagnostic_sha256": PHASE3F_DIAGNOSTIC,
        "phase3g_report_sha256": PHASE3G_REPORT,
        "preflight_source_sha256": SCRIPT,
        "preflight_test_sha256": TEST,
        "source_2wiki_dev_sha256": SOURCE_2WIKI,
        "v17_prior_bundles_sha256": V17_PRIORS,
    }


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if cfg["experiment"] != EXPERIMENT:
        raise RuntimeError("Phase 3H experiment ID drift")
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("Phase 3H must remain zero-network and closed")
    if cfg["future_execution_proposal"]["status"] != "not_authorized":
        raise RuntimeError("Phase 3H future execution must remain unauthorized")
    if cfg["bindings"]["source_files"] != source_bindings():
        raise RuntimeError("Phase 3H source binding drift")
    if load(PHASE3F_STRICT)["aggregate_fingerprint"] != cfg["bindings"]["phase3f_strict_fingerprint"]:
        raise RuntimeError("Phase 3F strict binding drift")
    if load(PHASE3F_DIAGNOSTIC)["aggregate_fingerprint"] != cfg["bindings"]["phase3f_diagnostic_fingerprint"]:
        raise RuntimeError("Phase 3F diagnostic binding drift")

    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    if len(tasks) != 40 or Counter(row["skill_family"] for row in tasks) != Counter({family: 20 for family in TARGET_FAMILIES}):
        raise RuntimeError("Phase 3H task balance drift")
    if len(schedule) != 200 or len({row["logical_call_id"] for row in schedule}) != 200 or len({row["request_hash"] for row in schedule}) != 200:
        raise RuntimeError("Phase 3H schedule identity drift")
    if Counter(row["condition"] for row in schedule) != Counter({condition: 40 for condition in CONDITIONS}):
        raise RuntimeError("Phase 3H condition balance drift")
    if any(identities[key] != 0 for key in ("task_id_overlap", "logical_call_id_overlap", "request_hash_overlap")):
        raise RuntimeError("Phase 3H prior identity overlap")
    if any(contains_forbidden_gold_key(row["canonical_request_body"]) for row in schedule):
        raise RuntimeError("Phase 3H private gold leaked")
    for task in private_gold:
        validity = task["counterfactual_validity"]
        if not all(validity.values()):
            raise RuntimeError("Phase 3H counterfactual identifiability drift")
        grid = {row["condition"]: row for row in schedule if row["task_id"] == task["task_id"]}
        if set(grid) != set(CONDITIONS):
            raise RuntimeError("Phase 3H condition grid drift")
        if grid["dual_contextual_first"]["candidate_order"] != list(reversed(grid["dual_control_first"]["candidate_order"])):
            raise RuntimeError("Phase 3H dual order drift")
        if grid["incompatible_control"]["expected_selected_skill_id"] != grid["incompatible_control"]["control_candidate_id"]:
            raise RuntimeError("Phase 3H forced counterfactual intervention drift")
        contract = grid["contextual"]["canonical_request_body"]["response_contract"]["skill_assessments"]
        if contract["type"] != "object" or contract["exact_candidate_id_keys"] != grid["contextual"]["candidate_order"]:
            raise RuntimeError("Phase 3H native mapping contract drift")

    result = {
        "schema_version": VERSION,
        "experiment": EXPERIMENT,
        "status": "design-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "authorization_artifact_created": False,
        "config_sha256": sha256_file(CONFIG),
        "source_bindings": source_bindings(),
        "phase3f_strict_fingerprint": cfg["bindings"]["phase3f_strict_fingerprint"],
        "phase3f_diagnostic_fingerprint": cfg["bindings"]["phase3f_diagnostic_fingerprint"],
        "phase3g_report_sha256": cfg["bindings"]["source_files"]["phase3g_report_sha256"],
        "task_count": len(tasks),
        "logical_calls_proposed": len(schedule),
        "family_counts": dict(Counter(row["skill_family"] for row in tasks)),
        "condition_counts": dict(Counter(row["condition"] for row in schedule)),
        "counterfactually_identifiable_tasks": sum(all(row["counterfactual_validity"].values()) for row in private_gold),
        "response_schema": "candidate_id_keyed_object_mapping",
        "identity_overlap_audit": identities,
        "analysis_plan": cfg["analysis_plan"],
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any]) -> str:
    return f"""# Phase 3H counterfactual answer-sensitivity preflight

This zero-network preflight responds to Phase 3G's answer-grounding diagnosis. It freezes {result['task_count']} wholly new 2WikiMultiHopQA comparison tasks, split evenly across attribute and bridge-attribute comparison. Every admitted task has two distinct source-verifiable answers: the dataset answer under the question's comparison direction and the other compared entity under the preregistered inverse procedure.

The proposed schedule contains {result['logical_calls_proposed']} unique requests across cold, contextual, forced incompatible-control, and two reversed-order dual conditions. Private gold records both answers and both evidence traces; neither answer is included in any canonical request. All prior task, logical-call, and request-hash overlaps are zero.

The primary gate is answer grounding, not selector uptake: after the target and inverse procedures are executed and the observable operation changes, final answers must flip to their corresponding preregistered answers. The proposal remains `not_authorized`; no network, provider, model, paid, later-stage, cross-domain, or formal-scaling call was made.

Fingerprint: `{result['aggregate_fingerprint']}`.
"""


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    documents = {
        "counterfactual_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "counterfactual_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": result["identity_overlap_audit"],
        "analysis_plan.json": result["analysis_plan"],
        "run_manifest.json": result,
        "completion_manifest.json": {
            "schema_version": VERSION,
            "experiment": EXPERIMENT,
            "status": "complete",
            "completion_kind": "zero_network_design_preflight",
            "proposed_calls": result["logical_calls_proposed"],
            "completed_calls": 0,
            "provider_calls_executed": 0,
            "authorization_status": "not-authorized",
            "run_manifest": "run_manifest.json",
            "aggregate_fingerprint": result["aggregate_fingerprint"],
        },
    }
    for name, value in documents.items():
        (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-bindings", action="store_true")
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    if args.print_bindings:
        print(json.dumps(source_bindings(), indent=2, sort_keys=True))
        raise SystemExit(0)
    validation = validate()
    if args.write_artifact:
        write_artifact(validation)
    print(json.dumps(validation, indent=2, sort_keys=True))
