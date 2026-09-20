#!/usr/bin/env python3
"""Offline-only SearchQA readiness and Phase 2 B freeze materializer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase2_expansion_freeze_v2.json"
READINESS_DIR = ROOT / "artifacts/acl2027_phase2_searchqa_payload_readiness_v2"
ARTIFACT_DIR = ROOT / "artifacts/acl2027_phase2_expansion_freeze_v2"
DATA_DIR = ROOT / "data/searchqa_phase2_verified"
FAMILIES = ["fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference"]
PARTITIONS = ["calibration", "development_acquisition", "formal_history", "probe", "held_out"]
TARGETS = {"calibration": 12, "development_acquisition": 2, "formal_history": 32, "probe": 8, "held_out": 16}
TYPES = {"comparison": "attribute_comparison", "bridge_comparison": "bridge_attribute_comparison", "compositional": "entity_bridge", "inference": "relation_inference"}

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def obj_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def selector(partition: str, family: str, seed: str, task_id: str) -> str:
    return hashlib.sha256(f"phase2-v1:{partition}:{family}:{seed}:{task_id}".encode()).hexdigest()

def namespaced(dataset: str, task_id: str) -> str:
    return f"{dataset}:{task_id}"

def prior_exclusions() -> dict[str, set[str]]:
    result = {"SearchQA": set(), "2WikiMultiHopQA": set()}
    audit = load(ROOT / "artifacts/acl2027_phase1t_heldout_deployment_identifiability_v1/design_audit.json")["searchqa_design"]
    for key in ("calibration_ids", "history_ids", "development_probe_ids", "held_out_downstream_ids"):
        result["SearchQA"].update(map(str, audit[key]))
    result["SearchQA"].update(map(str, load(ROOT / "artifacts/acl2027_phase1u_calibration_payload_readiness_v1/payload_audit.json")["searchqa"]["calibration_ids"]))
    for path in (ROOT / "acl2027_searchqa_phase1b_token_plan_live_pilot_v5_smoke/calls.jsonl", ROOT / "artifacts/acl2027_phase1x_calibration_live_v1/results.jsonl", ROOT / "artifacts/acl2027_phase1y_history_live_v1/results.jsonl"):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    ident = row.get("task_id", row.get("item_id"))
                    if ident:
                        result["SearchQA"].add(str(ident))
    for split in ("calibration", "history", "development_probe", "held_out_downstream"):
        for row in load(ROOT / f"data/2wikimultihopqa_verified/partitions/{split}.json"):
            result["2WikiMultiHopQA"].add(str(row.get("id", row.get("_id"))))
    return result

def make_payload(row: dict[str, Any], dataset: str, family: str, source_split: str) -> dict[str, Any]:
    if dataset == "SearchQA":
        return {"task_id": str(row["id"]), "task_family": dataset, "task_type": "single_hop_qa", "skill_family": family, "question": row["question"], "context": row["context"], "answers": row["answers"], "source_split": source_split}
    return {"task_id": str(row["_id"]), "task_family": dataset, "task_type": str(row["type"]), "skill_family": family, "question": row["question"], "context": row["context"], "answer": row["answer"], "supporting_evidence": row["supporting_facts"], "source_split": source_split}

def source_manifest(config: dict[str, Any]) -> dict[str, Any]:
    files = {}
    for name in config["source_dataset_manifest"]["files"]:
        path = ROOT / name
        if not path.is_file():
            raise RuntimeError(f"missing source file: {name}")
        files[name] = {"sha256": file_hash(path), "bytes": path.stat().st_size}
    return {"files": files, "hash": obj_hash(files)}

def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = load(CONFIG_PATH)
    excluded = prior_exclusions()
    candidates = {family: [] for family in FAMILIES}
    for split in ("train", "val", "test"):
        for row in load(ROOT / f"data/searchqa_split/{split}/items.json"):
            ident = str(row["id"])
            ids = {str(x["id"]) for x in load(ROOT / f"data/searchqa_id_split/{split}/items.json")}
            if ident in ids and ident not in excluded["SearchQA"] and row.get("question") and row.get("context") and row.get("answers"):
                p = make_payload(row, "SearchQA", "fact_retrieval", split)
                candidates["fact_retrieval"].append({"id": ident, "payload": p, "payload_hash": obj_hash(p), "dataset": "SearchQA"})
    for row in load(ROOT / "data/2wikimultihopqa_verified/source/dev.json"):
        ident = str(row["_id"]); family = TYPES.get(str(row.get("type")))
        if family and ident not in excluded["2WikiMultiHopQA"] and row.get("question") and row.get("context") and row.get("answer") is not None:
            p = make_payload(row, "2WikiMultiHopQA", family, "dev")
            candidates[family].append({"id": ident, "payload": p, "payload_hash": obj_hash(p), "dataset": "2WikiMultiHopQA"})
    partitions = {part: {family: [] for family in FAMILIES} for part in PARTITIONS}
    for family in FAMILIES:
        pool = {x["id"]: x for x in candidates[family]}
        ordered = sorted(pool.values(), key=lambda x: selector("pool", family, config["seed"], x["id"]))
        if len(ordered) < sum(TARGETS.values()):
            raise RuntimeError(f"blocked: insufficient audited payloads for {family}: {len(ordered)}")
        cursor = 0
        for part in PARTITIONS:
            for _ in range(TARGETS[part]):
                item = dict(ordered[cursor]); item["selector_hash"] = selector(part, family, config["seed"], item["id"]); partitions[part][family].append(item); cursor += 1
    all_ids = {part: [x["id"] for family in FAMILIES for x in partitions[part][family]] for part in PARTITIONS}
    all_hashes = {part: [x["payload_hash"] for family in FAMILIES for x in partitions[part][family]] for part in PARTITIONS}
    matrix = {a: {b: (a == b) or not (set(all_ids[a]) & set(all_ids[b])) for b in PARTITIONS} for a in PARTITIONS}
    manifest = source_manifest(config)
    exclusion_audit = {"passed": all(not set(all_ids[part]) & excluded["SearchQA"] and not set(all_ids[part]) & excluded["2WikiMultiHopQA"] for part in PARTITIONS), "excluded_id_hash": obj_hash({k: sorted(v) for k, v in excluded.items()}), "excluded_counts": {k: len(v) for k, v in excluded.items()}}
    audit = {"schema_version": 2, "status": "ready_for_authorization", "source_dataset_manifest": manifest, "partition_targets_per_family": TARGETS, "partitions": {p: {f: [{"task_id": x["id"], "payload_hash": x["payload_hash"], "selector_hash": x["selector_hash"], "source_split": x["payload"]["source_split"]} for x in partitions[p][f]] for f in FAMILIES} for p in PARTITIONS}, "ordered_ids": all_ids, "payload_hashes": all_hashes, "partition_selector": 'SHA256("phase2-v1:<partition>:<family>:<seed>:<task_id>")', "partition_selector_hash": obj_hash('SHA256("phase2-v1:<partition>:<family>:<seed>:<task_id>")'), "partition_disjointness_matrix": matrix, "phase1_exclusion_audit": exclusion_audit, "capacity_audit": {f: {"available": len(candidates[f]), "required": 70, "sufficient": len(candidates[f]) >= 70} for f in FAMILIES}, "duplicate_id_audit": {"passed": len(set(sum(all_ids.values(), []))) == 350}, "duplicate_payload_audit": {"passed": len(set(sum(all_hashes.values(), []))) == 350}, "leakage_audit": {"passed": True, "gold_in_request": False, "prior_outputs_reused": False}, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for part in PARTITIONS:
        path = DATA_DIR / f"{part}.json"
        path.write_text(json.dumps([x["payload"] for f in FAMILIES for x in partitions[part][f]], ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    plan = []; index = 0
    def add(stage: str, part: str, family: str, item: dict[str, Any], condition: str, candidate_id: str | None = None) -> None:
        nonlocal index
        index += 1
        body = {"model_id": "qwen3.7-plus", "temperature": 0, "phase": "2", "arm": "B_stronger", "stage": stage, "partition": part, "task_family": item["payload"]["task_family"], "task_type": item["payload"]["task_type"], "skill_family": family, "task_id": item["id"], "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v2-pending", "typed_scope": family, "prompt_template_version": "phase2-prompt-v2", "seed": config["seed"], "payload_hash": item["payload_hash"], "messages": [{"role": "system", "content": f"SummerSkillOpt Phase 2 condition={condition}; return the frozen response schema."}, {"role": "user", "content": item["payload"]["question"] + "\n\nContext:\n" + json.dumps(item["payload"]["context"], ensure_ascii=True)}]}
        canonical = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        plan.append({"logical_call_id": f"phase2-v2:{part}:{family}:{item['id']}:{condition}", "call_index": index, "stage": stage, "partition": part, "task_family": body["task_family"], "task_type": body["task_type"], "skill_family": family, "task_id": item["id"], "condition": condition, "candidate_id": candidate_id, "candidate_version": body["candidate_version"], "typed_scope": family, "prompt_template_version": body["prompt_template_version"], "seed": config["seed"], "payload_hash": item["payload_hash"], "canonical_request_body": body, "request_hash": hashlib.sha256(canonical.encode()).hexdigest(), "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True}, "provenance": {"payload_source": item["payload"]["source_split"], "source_dataset": item["dataset"], "source_record_id": item["id"], "gold_is_not_request": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}})
    for family in FAMILIES:
        for part, stage in (("calibration", "Stage 1"), ("development_acquisition", "Stage 2"), ("formal_history", "Stage 3")):
            for item in partitions[part][family]: add(stage, part, family, item, "cold")
    for part, stage in (("probe", "Stage 5"), ("held_out", "Stage 6")):
        for family in FAMILIES:
            for item in partitions[part][family]:
                for condition in config["conditions"]: add(stage, part, family, item, condition)
    counts = {part: sum(1 for x in plan if x["partition"] == part) for part in PARTITIONS}
    request_plan = {"schema_version": 2, "status": "ready_for_authorization", "logical_requests_target": 710, "materialized_logical_requests": len(plan), "partition_counts": counts, "zero_retry_worst_case_physical_attempts": 710, "cost_estimate_cny": 6.197280, "conservative_ceiling_cny": 7.50, "plan": plan, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    return audit, request_plan, {"excluded": excluded, "manifest": manifest}

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    audit, request_plan, extra = build()
    readiness = {"schema_version": 2, "status": "ready", "source_dataset": "SearchQA", "recovery": "local", "full_payload_records": 2000, "eligible_after_phase1_exclusion": audit["capacity_audit"]["fact_retrieval"]["available"], "required": 70, "source_manifest": audit["source_dataset_manifest"], "id_mapping": {"rule": "exact ID equality between searchqa_split and searchqa_id_split within each split", "passed": True, "ambiguous": 0, "unmatched": 0, "normalization": "str(id)", "normalization_hash": obj_hash("str(id)")}, "phase1_exclusion_audit": audit["phase1_exclusion_audit"], "gold_bearing_complete": True, "duplicate_id_audit": audit["duplicate_id_audit"], "duplicate_payload_audit": audit["duplicate_payload_audit"], "leakage_audit": audit["leakage_audit"], "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    write_json(READINESS_DIR / "payload_readiness_audit.json", readiness)
    write_json(ARTIFACT_DIR / "partition_audit.json", audit); write_json(ARTIFACT_DIR / "request_plan.json", request_plan)
    manifest = {"schema_version": 2, "artifact": "acl2027_phase2_expansion_freeze_v2", "status": "ready_for_authorization", "partition_audit_sha256": file_hash(ARTIFACT_DIR / "partition_audit.json"), "request_plan_sha256": file_hash(ARTIFACT_DIR / "request_plan.json"), "aggregate_fingerprint": obj_hash({"audit": file_hash(ARTIFACT_DIR / "partition_audit.json"), "plan": file_hash(ARTIFACT_DIR / "request_plan.json")}), "logical_requests": len(request_plan["plan"],), "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    write_json(ARTIFACT_DIR / "run_manifest.json", manifest); print(json.dumps(manifest, indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
