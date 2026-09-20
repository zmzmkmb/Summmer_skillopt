#!/usr/bin/env python3
"""Build the zero-network, model-identifiable Phase 2 v17 probe schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_integrity_v4 import verify_integrity
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase2_probe_identifiable_schedule_preflight_v17.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
CANDIDATES = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/combined_candidates_v13.json"
V13_MANIFEST = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/run_manifest.json"
HISTORY_SCHEDULE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v12/combined_formal_history_schedule.json"
V11_LEDGER = ROOT / "artifacts/acl2027_phase2_formal_history_v11/ledger.json"
V12_LEDGER = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_live_v12/ledger.json"
V16_REPLACEMENT = ROOT / "artifacts/acl2027_phase2_probe_replacement_schedule_preflight_v16/replacement_selection_audit.json"
V16_MANIFEST = ROOT / "artifacts/acl2027_phase2_probe_replacement_schedule_preflight_v16/run_manifest.json"
ORIGINAL_PROBE_GOLD = ROOT / "data/searchqa_phase2_verified/probe.json"
HELD_OUT_GOLD = ROOT / "data/searchqa_phase2_verified/held_out.json"
ORIGINAL_SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
V14_LEDGER = ROOT / "artifacts/acl2027_phase2_probe_only_live_v14/ledger.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17"
TEST = ROOT / "tests/test_acl2027_phase2_probe_identifiable_schedule_preflight_v17.py"
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")
SYSTEM = 'Answer the question from the supplied context and optional prior bundle. Return exactly one JSON object and no other text, markdown, or explanation. The object must contain exactly one key named answer whose value is a non-empty short string. Required shape: {"answer":"<short answer>"}.'


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def parse_answer(raw: str) -> str:
    value = json.loads(raw)
    if set(value) != {"answer"} or not isinstance(value["answer"], str) or not value["answer"].strip():
        raise RuntimeError("verified history response contract drift")
    return value["answer"].strip()


def question_from_row(row: dict[str, Any]) -> str:
    content = row["canonical_request_body"]["messages"][-1]["content"]
    return content.split("\n\nContext:\n", 1)[0]


def verified_examples() -> dict[str, list[dict[str, Any]]]:
    candidate = load(CANDIDATES)
    schedule = {row["logical_call_id"]: row for row in load(HISTORY_SCHEDULE)["schedule"]}
    ledgers = {row["logical_call_id"]: row for row in load(V11_LEDGER) + load(V12_LEDGER) if row.get("status") == "completed"}
    result = {family: [] for family in FAMILIES}
    for trajectory in candidate["trajectories"]:
        if trajectory.get("verifier_confirmed_success") is not True:
            continue
        logical_id = trajectory["logical_call_id"]
        planned, record = schedule[logical_id], ledgers[logical_id]
        result[trajectory["family"]].append({"support_id": trajectory["support_id"], "task_id": trajectory["task_id"], "family": trajectory["family"], "question": question_from_row(planned), "answer": parse_answer(record["raw_response"])})
    if any(len(result[family]) < 10 for family in FAMILIES):
        raise RuntimeError("insufficient verified examples for v17 prior bundles")
    return result


def select(values: list[dict[str, Any]], prefix: str, count: int) -> list[dict[str, Any]]:
    return sorted(values, key=lambda row: hashlib.sha256(f"{prefix}:{row['support_id']}".encode()).hexdigest())[:count]


def build_prior_bundles() -> dict[str, Any]:
    examples = verified_examples()
    global_examples = []
    for family in FAMILIES:
        global_examples.extend(select(examples[family], f"phase2-v17:global:{family}", 2))
    typed = {family: select(examples[family], f"phase2-v17:typed:{family}", 10) for family in FAMILIES}
    return {"schema_version": 17, "source": "v13_verifier_confirmed_trajectories", "global": {"candidate_id": "candidate:global:v17", "source_scope": "global", "examples": global_examples}, "typed": {family: {"candidate_id": f"candidate:{family}:v13", "source_scope": f"family:{family}", "examples": typed[family]} for family in FAMILIES}}


def probe_gold() -> list[dict[str, Any]]:
    original = load(ORIGINAL_PROBE_GOLD)
    spent_task = load(V14_LEDGER)[0]["task_id"]
    replacement = load(V16_REPLACEMENT)["payload"]
    rows = [replacement if row["task_id"] == spent_task else row for row in original]
    if len(rows) != 40 or len({row["task_id"] for row in rows}) != 40 or spent_task in {row["task_id"] for row in rows}:
        raise RuntimeError("replacement probe gold grid drift")
    return rows


def condition_prior(condition: str, family: str, bundles: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if condition == "cold":
        return "candidate:none:v17", {"slot": "none", "source_scope": "none", "examples": []}
    if condition == "global_only":
        return bundles["global"]["candidate_id"], {"slot": "global", "source_scope": "global", "examples": bundles["global"]["examples"]}
    if condition == "copied_global":
        return f"candidate:copied-global:{family}:v17", {"slot": f"family:{family}", "source_scope": "global_copied", "examples": bundles["global"]["examples"]}
    typed = bundles["typed"][family]
    return typed["candidate_id"], {"slot": f"family:{family}", "source_scope": typed["source_scope"], "examples": typed["examples"]}


def build_schedule() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    bundles, gold = build_prior_bundles(), probe_gold()
    replacement_task_id = load(CONFIG)["schedule_contract"]["replacement_task_id"]
    rows = []
    index = 0
    for task in gold:
        family = task["skill_family"]
        for condition in CONDITIONS:
            index += 1
            candidate_id, prior = condition_prior(condition, family, bundles)
            payload_hash = stable(task)
            prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            user = "Prior bundle:\n" + prior_text + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)
            body = {"model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "phase": "2", "stage": "Stage 5", "partition": "probe", "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family, "task_id": task["task_id"], "payload_hash": payload_hash, "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v17", "typed_scope": family, "prompt_template_version": "phase2-probe-identifiable-json-v17", "prior_payload_sha256": stable(prior), "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
            request_hash = stable(body)
            rows.append({"schema_version": 17, "sequence": index, "staged_execution_index": index, "logical_call_id": f"phase2-v17:probe:{family}:{task['task_id']}:{condition}", "request_hash": request_hash, "partition": "probe", "stage": "Stage 5", "task_id": task["task_id"], "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family, "typed_scope": family, "payload_hash": payload_hash, "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v17", "prompt_template_version": "phase2-probe-identifiable-json-v17", "prior_payload_sha256": body["prior_payload_sha256"], "canonical_request_body": body, "provenance": {"source_dataset": "SearchQA", "source_record_id": task["task_id"], "payload_source": task["source_split"], "gold_is_not_request": True, "replacement_selected_by_v16": task["task_id"] == replacement_task_id, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}, "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True}})
    return rows, bundles, gold


def artifact_documents(rows: list[dict[str, Any]], bundles: dict[str, Any], gold: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "probe_schedule.json": {"schema_version": 17, "schedule": rows},
        "prior_bundles.json": bundles,
        "replacement_probe_gold.json": gold,
    }


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(cfg["execution"].get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise RuntimeError("v17 execution switches must remain closed")
    paths = {"v4_manifest_sha256": V4_MANIFEST, "v13_manifest_sha256": V13_MANIFEST, "v16_manifest_sha256": V16_MANIFEST, "v13_candidate_sha256": CANDIDATES, "combined_history_schedule_sha256": HISTORY_SCHEDULE, "v11_ledger_sha256": V11_LEDGER, "v12_ledger_sha256": V12_LEDGER, "v16_replacement_audit_sha256": V16_REPLACEMENT, "v14_terminal_ledger_sha256": V14_LEDGER, "original_probe_schedule_sha256": ORIGINAL_SCHEDULE, "original_probe_gold_sha256": ORIGINAL_PROBE_GOLD, "held_out_gold_sha256": HELD_OUT_GOLD}
    if any(sha256_file(path) != cfg["bindings"][name] for name, path in paths.items()):
        raise RuntimeError("v17 source binding drift")
    verify_integrity(V4_CONFIG, V4_MANIFEST, root=ROOT)
    v4, v13, v16 = load(V4_MANIFEST), load(V13_MANIFEST), load(V16_MANIFEST)
    if v4.get("aggregate_fingerprint") != cfg["bindings"]["v4_aggregate_fingerprint"]:
        raise RuntimeError("v17 v4 acceptance drift")
    if v13.get("aggregate_fingerprint") != cfg["bindings"]["v13_aggregate_fingerprint"] or v13.get("status") != "preflight-passed-correction":
        raise RuntimeError("v17 v13 acceptance drift")
    if v16.get("aggregate_fingerprint") != cfg["bindings"]["v16_aggregate_fingerprint"] or v16.get("status") != "blocked-condition-semantics":
        raise RuntimeError("v17 v16 replacement audit drift")
    rows, bundles, gold = build_schedule()
    v14_records = load(V14_LEDGER)
    spent_logical = v14_records[0]["logical_call_id"] if v14_records else None
    spent_task = v14_records[0]["task_id"] if v14_records else None
    if len(v14_records) != 1 or not v14_records[0].get("terminal") or v14_records[0].get("task_id") != spent_task:
        raise RuntimeError("v14 spent request terminal provenance drift")
    if len(rows) != 160 or len({r["logical_call_id"] for r in rows}) != 160 or len({r["request_hash"] for r in rows}) != 160 or spent_logical in {r["logical_call_id"] for r in rows} or spent_task in {r["task_id"] for r in rows}:
        raise RuntimeError("v17 schedule identity/exclusion drift")
    old_probe = [r for r in load(ORIGINAL_SCHEDULE)["schedule"] if r.get("partition") == "probe"]
    if {r["logical_call_id"] for r in rows} & {r["logical_call_id"] for r in old_probe} or {r["request_hash"] for r in rows} & {r["request_hash"] for r in old_probe}:
        raise RuntimeError("v17 logical/request identities are not entirely new")
    if len(gold) != 40 or any(sum(r["task_id"] == task["task_id"] for r in rows) != 4 for task in gold):
        raise RuntimeError("v17 task-condition grid drift")
    if [r["staged_execution_index"] for r in rows] != list(range(1, 161)) or any(r["payload_hash"] != stable(next(task for task in gold if task["task_id"] == r["task_id"])) for r in rows):
        raise RuntimeError("v17 stage index or payload binding drift")
    counts = {condition: sum(r["condition"] == condition for r in rows) for condition in CONDITIONS}
    if counts != {condition: 40 for condition in CONDITIONS}:
        raise RuntimeError("v17 condition counts drift")
    if any("max_tokens" in r["canonical_request_body"] or r["canonical_request_body"]["response_format"] != {"type": "json_object"} or r["canonical_request_body"].get("enable_thinking") is not False or r["canonical_request_body"].get("temperature") != 0 or r["canonical_request_body"].get("model_id") != "qwen3.7-plus" or r["candidate_id"] is None or r["candidate_version"] == "phase2-v2-pending" for r in rows):
        raise RuntimeError("v17 route/candidate contract drift")
    global_ids = [x["support_id"] for x in bundles["global"]["examples"]]
    if len(global_ids) != len(set(global_ids)) != 0 or len(global_ids) != 10 or any(len(bundles["typed"][family]["examples"]) != 10 for family in FAMILIES):
        raise RuntimeError("v17 prior bundle cardinality drift")
    support_task_ids = {example["task_id"] for example in bundles["global"]["examples"]}
    for typed in bundles["typed"].values():
        support_task_ids.update(example["task_id"] for example in typed["examples"])
    held_out_ids = {row["task_id"] for row in load(HELD_OUT_GOLD)}
    if support_task_ids & {task["task_id"] for task in gold} or support_task_ids & held_out_ids:
        raise RuntimeError("v17 prior construction crossed probe/held-out partition")
    for task in gold:
        grid = {row["condition"]: row for row in rows if row["task_id"] == task["task_id"]}
        if len({row["prior_payload_sha256"] for row in grid.values()}) != 4:
            raise RuntimeError("v17 condition semantics are not model-visible and distinct")
    documents = artifact_documents(rows, bundles, gold)
    candidate = load(CANDIDATES)
    if candidate.get("coverage_status") != "coverage-passed" or candidate.get("passed") is not True or candidate.get("history_rows") != 160:
        raise RuntimeError("v13 coverage eligibility gate drift")
    result = {"schema_version": 17, "experiment": "acl2027_phase2_probe_identifiable_schedule_preflight_v17", "status": "ready-for-explicit-authorization", "authorization_request_status": "awaiting_fresh_explicit_user_authorization", "probe_calls": 160, "task_count": 40, "condition_counts": counts, "coverage_gate_passed": True, "coverage_supports": candidate["independent_verified_supports"], "replacement_task_id": cfg["schedule_contract"]["replacement_task_id"], "spent_v14_task_excluded": True, "all_logical_ids_new": True, "all_request_hashes_new": True, "unique_request_hashes": 160, "global_examples": 10, "typed_examples_per_family": 10, "private_probe_gold_used_for_priors": False, "held_out_gold_used_for_priors": False, "prior_probe_task_overlap": 0, "prior_held_out_task_overlap": 0, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "held_out_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False, "proposed_authorization": cfg["authorization_request"], "bindings": {"preflight_config_sha256": sha256_file(CONFIG), "preflight_source_sha256": sha256_file(Path(__file__).resolve()), "preflight_test_sha256": sha256_file(TEST), **{name: sha256_file(path) for name, path in paths.items()}, "v4_aggregate_fingerprint": v4["aggregate_fingerprint"], "v13_aggregate_fingerprint": v13["aggregate_fingerprint"], "v16_aggregate_fingerprint": v16["aggregate_fingerprint"], "probe_schedule_artifact_sha256": rendered_sha256(documents["probe_schedule.json"]), "prior_bundles_artifact_sha256": rendered_sha256(documents["prior_bundles.json"]), "replacement_probe_gold_artifact_sha256": rendered_sha256(documents["replacement_probe_gold.json"]), "schedule_canonical_sha256": stable(rows), "prior_bundles_canonical_sha256": stable(bundles), "replacement_probe_gold_canonical_sha256": stable(gold)}}
    result["aggregate_fingerprint"] = stable(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        ARTIFACT.mkdir(parents=True, exist_ok=False)
        rows, bundles, gold = build_schedule()
        documents = artifact_documents(rows, bundles, gold)
        for name, value in documents.items():
            (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
        for name, binding in (("probe_schedule.json", "probe_schedule_artifact_sha256"), ("prior_bundles.json", "prior_bundles_artifact_sha256"), ("replacement_probe_gold.json", "replacement_probe_gold_artifact_sha256")):
            if sha256_file(ARTIFACT / name) != result["bindings"][binding]:
                raise RuntimeError(f"v17 artifact byte hash drift: {name}")
        (ARTIFACT / "run_manifest.json").write_text(render(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
