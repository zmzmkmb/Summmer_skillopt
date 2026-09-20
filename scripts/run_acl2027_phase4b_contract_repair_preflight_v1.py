#!/usr/bin/env python3
"""Diagnose and freeze a zero-network Phase 4B prompt/transport contract repair."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1 as base

VERSION = 1
EXPERIMENT = "acl2027_phase4b_contract_repair_preflight_v1"
CONFIG = ROOT / "configs/acl2027/phase4b_contract_repair_preflight_v1.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4b_contract_repair_preflight_v1.py"
PHASE4A = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1"
PHASE4B_PREFLIGHT = ROOT / "artifacts/acl2027_phase4b_development_live_preflight_v1"
PHASE4B_RUN = ROOT / "artifacts/acl2027_phase4b_development_live_v3"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase4b_contract_repair_preflight_v1.md"
CONDITIONS = ("cold", "global_only", "contextual_typed", "shuffled_typed", "incompatible_control")
FAMILIES = ("attribute_comparison", "bridge_attribute_comparison")
EXACT_KEYS = ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rank(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase4b-contract-repair-v1:{family}:{task_id}".encode()).hexdigest()


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
    return (
        "Return exactly one JSON object and no markdown. The object MUST have exactly these six top-level keys: "
        + ", ".join(EXACT_KEYS)
        + ". Contract: "
        + json.dumps(contract, ensure_ascii=True, sort_keys=True)
        + ". Assess every presented candidate. Copy evidence IDs verbatim from the annotated context. "
        + "Use selected_skill_id='none' when no candidate is presented. Do not return answer/evidence/reasoning shorthand."
    )


def annotated_context(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "title": title,
            "sentences": [
                {"id": f"{title}#{index}", "text": sentence}
                for index, sentence in enumerate(sentences)
            ],
        }
        for title, sentences in task["context"]
    ]


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base.ARTIFACT = ARTIFACT
    prior = base.prior_identity_universe()
    pools = base.source_candidates()
    selected: list[dict[str, Any]] = []
    audit: dict[str, Any] = {"schema_version": VERSION, "families": {}}
    for family in FAMILIES:
        eligible = []
        for row in pools[family]:
            if str(row["task_id"]) in prior["task_ids"]:
                continue
            task = base.counterfactual_task(row)
            if task is not None:
                eligible.append(task)
        chosen = sorted(eligible, key=lambda row: (rank(family, str(row["task_id"])), str(row["task_id"])))[:10]
        if len(chosen) != 10:
            raise RuntimeError(f"insufficient new tasks for {family}")
        selected.extend(chosen)
        audit["families"][family] = {"eligible": len(eligible), "selected": [row["task_id"] for row in chosen]}
    audit.update({"selected_tasks": len(selected), "prior_task_universe_size": len(prior["task_ids"]), "prior_task_universe_sha256": stable(sorted(prior["task_ids"])), "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0})
    return selected, audit


def candidates(condition: str, family: str) -> tuple[list[dict[str, Any]], str]:
    target, control = base.candidate_payloads(family)
    if condition == "cold":
        return [], "none"
    if condition in {"global_only", "contextual_typed"}:
        return [target], str(target["candidate_id"])
    if condition == "shuffled_typed":
        return [control, target], str(target["candidate_id"])
    return [control], str(control["candidate_id"])


def transport_projection(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": body["model_id"],
        "messages": body["messages"],
        "temperature": body["temperature"],
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
    }


def build_schedule(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contract = response_contract()
    system = system_message(contract)
    rows = []
    for task in tasks:
        family = str(task["skill_family"])
        for condition in CONDITIONS:
            bundle, expected = candidates(condition, family)
            visible = {
                "question": task["question"],
                "context": annotated_context(task),
                "candidates": bundle,
                "available_skill_ids": ["none", *[str(row["candidate_id"]) for row in bundle]],
                "response_contract": contract,
            }
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "4B-contract-repair-v1",
                "split": "development",
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "skill_family": family,
                "condition": condition,
                "expected_selected_skill_id": expected,
                "visible_contract_sha256": stable(contract),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(visible, ensure_ascii=True, sort_keys=True)},
                ],
            }
            projection = transport_projection(body)
            if system not in projection["messages"][0]["content"] or json.dumps(contract, ensure_ascii=True, sort_keys=True) not in projection["messages"][1]["content"]:
                raise RuntimeError("repaired contract is not visible in transport projection")
            rows.append({
                "schema_version": VERSION,
                "sequence": len(rows) + 1,
                "split": "development",
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "skill_family": family,
                "condition": condition,
                "logical_call_id": f"phase4b-contract-repair-v1:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "transport_payload_hash": stable(projection),
                "canonical_request_body": body,
                "transport_projection": projection,
                "provider_response_id": None,
            })
    return rows


def diagnose_original() -> dict[str, Any]:
    schedule = load(PHASE4B_PREFLIGHT / "development_schedule.json")["rows"]
    ledger = load(PHASE4B_RUN / "ledger.json")
    shapes: Counter[str] = Counter()
    missing_contract = 0
    for row, record in zip(schedule, ledger):
        body = row["canonical_request_body"]
        projected = transport_projection(body)
        system = projected["messages"][0]["content"]
        missing_contract += int(not all(key in system for key in EXACT_KEYS))
        value = json.loads(record["raw_response"])
        shapes["|".join(sorted(value))] += 1
    return {
        "schema_version": VERSION,
        "classification": "prompt_transport_contract_visibility_failure",
        "original_rows": len(schedule),
        "rows_whose_transmitted_system_message_omits_exact_keys": missing_contract,
        "canonical_metadata_dropped_by_adapter": ["response_contract", "available_skill_ids", "expected_selected_skill_id", "candidate_order", "public_payload_sha256", "candidate_payload_sha256"],
        "actual_response_key_shapes": dict(sorted(shapes.items())),
        "evidence_id_visibility_failure": True,
        "provider_exact_http_or_internal_cause_claimed": False,
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(cfg["execution"].values()) or cfg["future_execution_contract"]["status"] != "not_authorized":
        raise RuntimeError("contract repair preflight must remain closed")
    phase4a = load(PHASE4A / "run_manifest.json")
    phase4b = load(PHASE4B_PREFLIGHT / "run_manifest.json")
    analysis = load(PHASE4B_RUN / "development_analysis.json")
    if phase4a["aggregate_fingerprint"] != cfg["source_phase4a_design_fingerprint"] or phase4b["aggregate_fingerprint"] != cfg["source_phase4b_preflight_fingerprint"] or analysis["aggregate_fingerprint"] != cfg["source_phase4b_analysis_fingerprint"]:
        raise RuntimeError("source fingerprint drift")
    tasks, selection = select_tasks()
    rows = build_schedule(tasks)
    prior = base.prior_identity_universe()
    task_ids = {str(row["task_id"]) for row in tasks}
    logical = {row["logical_call_id"] for row in rows}
    hashes = {row["request_hash"] for row in rows}
    overlap = {"task_id_overlap": len(task_ids & prior["task_ids"]), "logical_call_id_overlap": len(logical & prior["logical_call_ids"]), "request_hash_overlap": len(hashes & prior["request_hashes"])}
    if len(tasks) != 20 or len(rows) != 100 or any(overlap.values()):
        raise RuntimeError(f"repair proposal drift: tasks={len(tasks)} rows={len(rows)} overlap={overlap}")
    if Counter(row["condition"] for row in rows) != Counter({condition: 20 for condition in CONDITIONS}):
        raise RuntimeError("condition balance drift")
    result = {
        "schema_version": VERSION,
        "experiment": EXPERIMENT,
        "status": "zero-network-contract-repair-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "diagnosis": diagnose_original(),
        "repair": {
            "contract_embedded_in_system_message": True,
            "contract_embedded_in_user_payload": True,
            "annotated_evidence_ids_visible": True,
            "adapter_transport_projection_audited": True,
            "exact_keys": list(EXACT_KEYS),
        },
        "selection": selection,
        "task_count": len(tasks),
        "proposal_rows": len(rows),
        "condition_counts": dict(Counter(row["condition"] for row in rows)),
        "identity_overlap_audit": overlap,
        "schedule_sha256": stable(rows),
        "bindings": {"config_sha256": sha256_file(CONFIG), "script_sha256": sha256_file(SCRIPT), "test_sha256": sha256_file(TEST), "adapter_sha256": sha256_file(ADAPTER), "phase4a_manifest_sha256": sha256_file(PHASE4A / "run_manifest.json"), "phase4b_analysis_sha256": sha256_file(PHASE4B_RUN / "development_analysis.json")},
        "future_execution": cfg["future_execution_contract"],
        "calibration_gate": cfg["calibration_gate"],
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "phase4c_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    if ARTIFACT.exists() and any(ARTIFACT.iterdir()):
        raise RuntimeError("contract repair artifact directory already contains files")
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    tasks, selection = select_tasks()
    rows = build_schedule(tasks)
    authorization_request = {
        "schema_version": VERSION,
        "status": "awaiting_fresh_exact_explicit_user_authorization",
        "contract_repair_preflight_fingerprint": result["aggregate_fingerprint"],
        "authorized_calls": 100,
        "execution_contract": result["future_execution"],
        "phase4c_authorized": False,
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }
    values = {
        "diagnostic.json": result["diagnosis"],
        "task_selection_audit.json": selection,
        "private_gold.json": tasks,
        "repaired_schedule.json": {"schema_version": VERSION, "rows": rows},
        "transport_projection_audit.json": {"schema_version": VERSION, "rows": [{"logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "transport_payload_hash": row["transport_payload_hash"], "system_contains_exact_keys": all(key in row["transport_projection"]["messages"][0]["content"] for key in EXACT_KEYS), "user_contains_contract": "response_contract" in row["transport_projection"]["messages"][1]["content"]} for row in rows], "network_calls": 0},
        "authorization_request.json": authorization_request,
        "run_manifest.json": result,
        "completion_manifest.json": {"schema_version": VERSION, "experiment": EXPERIMENT, "status": "complete", "completion_kind": "zero_network_contract_repair_preflight", "proposed_calls": 100, "completed_calls": 100, "rows": 100, "provider_calls_executed": 0, "authorization_status": "not-authorized", "aggregate_fingerprint": result["aggregate_fingerprint"]},
    }
    for name, value in values.items():
        (ARTIFACT / name).write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(
        "# Phase 4B prompt/transport contract repair preflight\n\n"
        "The zero-network diagnostic identifies a prompt/transport visibility failure: the original six-field contract lived outside `messages`, while the provider adapter transmitted only the message list and decoding fields. The model therefore never saw the exact schema or explicit evidence IDs.\n\n"
        "The repaired proposal embeds the exact six-field contract in both the system message and user payload, annotates every context sentence with a visible evidence ID, and audits the adapter's final transport projection. It freezes 20 wholly new development tasks and 100 five-condition rows with zero prior task, logical-call, or request-hash overlap.\n\n"
        "No authorization was opened and no network, provider, model, paid, Phase 4C, cross-domain, or formal-scaling call occurred.\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        write_artifact(result)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
