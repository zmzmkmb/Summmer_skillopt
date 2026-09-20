"""Freeze the zero-network Phase 4A strong-conclusion design."""
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
EXPERIMENT = "acl2027_phase4a_zero_network_design_preflight_v1"
CONFIG = ROOT / "configs/acl2027/phase4a_zero_network_design_preflight_v1.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase4a_zero_network_design_preflight_v1.py"
TEST = ROOT / "tests/test_acl2027_phase4a_zero_network_design_preflight_v1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase4a_zero_network_design_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase4a_zero_network_design_preflight_v1.md"
FAMILIES = ("attribute_comparison", "bridge_attribute_comparison")
CONDITIONS = ("cold", "global_only", "contextual_typed", "shuffled_typed", "incompatible_control")
base.ARTIFACT = ARTIFACT


def rank(split: str, family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase4a-v1:{split}:{family}:{task_id}".encode()).hexdigest()


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior = base.prior_identity_universe()
    pools = base.source_candidates()
    selected = []
    families = {}
    for family in FAMILIES:
        eligible = []
        for row in pools[family]:
            if str(row["task_id"]) in prior["task_ids"]:
                continue
            task = base.counterfactual_task(row)
            if task is not None:
                eligible.append(task)
        dev = sorted(eligible, key=lambda x: (rank("development", family, str(x["task_id"])), str(x["task_id"])))[:10]
        dev_ids = {str(x["task_id"]) for x in dev}
        held = sorted((x for x in eligible if str(x["task_id"]) not in dev_ids), key=lambda x: (rank("heldout", family, str(x["task_id"])), str(x["task_id"])))[:40]
        selected.extend(("development", x) for x in dev)
        selected.extend(("heldout", x) for x in held)
        families[family] = {
            "eligible": len(eligible),
            "development": [x["task_id"] for x in dev],
            "heldout": [x["task_id"] for x in held],
        }
    audit = {
        "schema_version": VERSION,
        "families": families,
        "selected_tasks": len(selected),
        "prior_task_universe_size": len(prior["task_ids"]),
        "prior_task_universe_sha256": stable(sorted(prior["task_ids"])),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }
    return selected, audit


def schedule_rows(selected: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for split, task in selected:
        family = str(task["skill_family"])
        target, control = base.candidate_payloads(family)
        for condition in CONDITIONS:
            candidates = [] if condition == "cold" else [target] if condition in {"global_only", "contextual_typed"} else [control, target] if condition == "shuffled_typed" else [control]
            ids = [str(x["candidate_id"]) for x in candidates]
            expected = "none" if condition == "cold" else (target["candidate_id"] if condition != "incompatible_control" else control["candidate_id"])
            public = base.public_task(task)
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "4A",
                "stage": "strong_conclusion_zero_network_design",
                "split": split,
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "skill_family": family,
                "condition": condition,
                "available_skill_ids": ["none", *ids],
                "candidate_order": ids,
                "expected_selected_skill_id": expected,
                "public_payload_sha256": stable(public),
                "candidate_payload_sha256": stable(candidates),
                "prompt_template_version": "phase4a-uniform-evidence-contract-v1",
                "response_contract": {
                    "exact_keys": ["skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer"],
                    "evidence_sentence_ids": {"type": "array", "non_empty": True, "must_resolve": True},
                    "extracted_operands": {"type": "object", "evidence_grounded": True},
                    "intermediate_result": {"type": "string", "non_empty": True, "chain_of_thought": False},
                    "final_answer": {"type": "string", "non_empty": True},
                },
                "messages": [{"role": "system", "content": "Return exactly one JSON object following the uniform evidence-grounded response contract."}, {"role": "user", "content": json.dumps({"candidates": candidates, "question": task["question"], "context": task["context"]}, ensure_ascii=True, sort_keys=True)}],
            }
            rows.append({
                "schema_version": VERSION,
                "sequence": len(rows) + 1,
                "split": split,
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "condition": condition,
                "logical_call_id": f"phase4a-v1:{split}:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "canonical_request_body": body,
                "provider_response_id": None,
                "provenance": {"source_record_id": task["task_id"], "gold_is_not_request": True, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0},
            })
    return rows


def validate() -> dict[str, Any]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if cfg["future_execution_proposal"]["status"] != "not_authorized" or any(cfg["execution"].values()):
        raise RuntimeError("Phase 4A must remain closed and zero-network")
    selected, selection = select_tasks()
    rows = schedule_rows(selected)
    prior = base.prior_identity_universe()
    task_ids = {str(x[1]["task_id"]) for x in selected}
    logical = {str(x["logical_call_id"]) for x in rows}
    hashes = {str(x["request_hash"]) for x in rows}
    overlap = {"task_id_overlap": len(task_ids & prior["task_ids"]), "logical_call_id_overlap": len(logical & prior["logical_call_ids"]), "request_hash_overlap": len(hashes & prior["request_hashes"])}
    if len(selected) != 100 or len(rows) != 500 or any(overlap.values()):
        raise RuntimeError(f"Phase 4A design drift: selected={len(selected)} rows={len(rows)} overlap={overlap}")
    result = {
        "schema_version": VERSION,
        "experiment": EXPERIMENT,
        "status": "design-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "config_sha256": sha256_file(CONFIG),
        "script_sha256": sha256_file(SCRIPT),
        "test_sha256": sha256_file(TEST),
        "selection": selection,
        "task_count": len(selected),
        "development_tasks": sum(split == "development" for split, _ in selected),
        "heldout_tasks": sum(split == "heldout" for split, _ in selected),
        "logical_calls_proposed": len(rows),
        "condition_counts": dict(Counter(row["condition"] for row in rows)),
        "identity_overlap_audit": overlap,
        "response_contract": cfg["response_contract"],
        "analysis_plan": cfg["analysis_plan"],
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "later_stage_calls": 0,
        "cross_domain_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    selected, selection = select_tasks()
    rows = schedule_rows(selected)
    private = [{"split": split, **task} for split, task in selected]
    for name, value in {
        "design_schedule.json": {"schema_version": VERSION, "rows": rows},
        "private_gold.json": private,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": result["identity_overlap_audit"],
        "analysis_plan.json": result["analysis_plan"],
        "run_manifest.json": result,
        "completion_manifest.json": {"schema_version": VERSION, "experiment": EXPERIMENT, "status": "complete", "completion_kind": "zero_network_design_preflight", "proposed_calls": 500, "completed_calls": 500, "rows": 500, "provider_calls_executed": 0, "authorization_status": "not-authorized", "aggregate_fingerprint": result["aggregate_fingerprint"]},
    }.items():
        (ARTIFACT / name).write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(f"# Phase 4A zero-network design preflight\n\nFrozen 100 wholly new tasks (20 development, 80 held-out) across two task families and 500 five-condition proposal rows. The uniform response contract requires evidence sentence IDs, extracted operands, an observable intermediate result, and a final answer. Prior task, logical-call, and request-hash overlaps are all zero.\n\nThis artifact is design-only and not authorized: network/provider/model/paid calls = 0. Phase 4B/4C execution requires fresh explicit authorization after this preflight.\n\nAggregate fingerprint: `{result['aggregate_fingerprint']}`.\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        write_artifact(result)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
