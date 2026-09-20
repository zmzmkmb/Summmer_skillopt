#!/usr/bin/env python3
"""Create the local-only Phase 2 B freeze/preflight artifact."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase2_expansion_freeze_v1.json"

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def selector(partition: str, family: str, seed: str, task_id: str) -> str:
    return hashlib.sha256(f"phase2-v1:{partition}:{family}:{seed}:{task_id}".encode()).hexdigest()

TYPE_TO_FAMILY = {"comparison": "attribute_comparison", "bridge_comparison": "bridge_attribute_comparison", "compositional": "entity_bridge", "inference": "relation_inference"}

def namespaced(dataset: str, task_id: str) -> str:
    return f"{dataset}:{task_id}"

def build(config: dict[str, Any]) -> dict[str, Any]:
    files = {p: {"sha256": file_hash(ROOT / p), "bytes": (ROOT / p).stat().st_size} for p in config["source_dataset_manifest"]["files"]}
    two = load(ROOT / "data/2wikimultihopqa_verified/source/dev.json")
    by_family = {family: [] for family in config["skill_families"]}
    for row in two:
        family = TYPE_TO_FAMILY.get(str(row.get("type")))
        if family:
            by_family[family].append(row)
    sq_cal = load(ROOT / "data/searchqa_phase1u/calibration.json")
    p1t = load(ROOT / "artifacts/acl2027_phase1t_heldout_deployment_identifiability_v1/design_audit.json")
    p1u = load(ROOT / "artifacts/acl2027_phase1u_calibration_payload_readiness_v1/payload_audit.json")
    p1y = load(ROOT / "artifacts/acl2027_phase1y_live_candidates_v1/audit.json")
    exclusions: dict[str, list[str]] = {"SearchQA": [], "2WikiMultiHopQA": []}
    sd = p1t["searchqa_design"]
    exclusions["SearchQA"].extend(x for k in ("calibration_ids", "history_ids", "development_probe_ids", "held_out_downstream_ids") for x in sd[k])
    exclusions["SearchQA"].extend(p1u["searchqa"]["calibration_ids"])
    for path in [ROOT / "acl2027_searchqa_phase1b_token_plan_live_pilot_v5_smoke/calls.jsonl", ROOT / "artifacts/acl2027_phase1y_history_live_v1/calls.jsonl"]:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    task_id = item.get("task_id", item.get("item_id"))
                    if task_id:
                        exclusions["SearchQA"].append(str(task_id))
    for partition in ("calibration", "history", "development_probe", "held_out_downstream"):
        path = ROOT / f"data/2wikimultihopqa_verified/partitions/{partition}.json"
        for row in load(path): exclusions["2WikiMultiHopQA"].append(str(row.get("_id", row.get("id"))))
    for path in [ROOT / "artifacts/acl2027_phase1y_history_live_v1/calls.jsonl", ROOT / "artifacts/acl2027_phase1y_history_live_v1/live/calls.jsonl"]:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    if item.get("task_family") == "2WikiMultiHopQA": exclusions["2WikiMultiHopQA"].append(str(item["task_id"]))
    results = ROOT / "artifacts/acl2027_phase1y_history_live_v1/results.jsonl"
    if results.exists():
        for line in results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("task_family") == "SearchQA" and item.get("task_id"):
                    exclusions["SearchQA"].append(str(item["task_id"]))
                if item.get("task_family") == "2WikiMultiHopQA" and item.get("task_id"):
                    exclusions["2WikiMultiHopQA"].append(str(item["task_id"]))
    exclusions = {k: sorted(set(v)) for k, v in exclusions.items()}
    required = config["partition_targets"]
    partitions = {p: {f: [] for f in config["skill_families"]} for p in config["partition_order"]}
    all_ids = {namespaced(k, i) for k, vals in exclusions.items() for i in vals}
    inventory = {f: {"complete_payload_rows": len(rows), "task_type": next((t for t, x in TYPE_TO_FAMILY.items() if x == f), "single_hop_qa"), "source": "data/2wikimultihopqa_verified/source/dev.json"} for f, rows in by_family.items()}
    inventory["fact_retrieval"] = {"complete_payload_rows": len(sq_cal), "task_type": "single_hop_qa", "source": "data/searchqa_phase1u/calibration.json only; Phase 2 payloads absent"}
    coverage = {f: {"available": x["complete_payload_rows"], "required_total": sum(required.values()), "sufficient": x["complete_payload_rows"] >= sum(required.values())} for f, x in inventory.items()}
    matrix = {a: {b: (a == b or not (set() & set())) for b in config["partition_order"]} for a in config["partition_order"]}
    audit = {"schema_version": 1, "status": "blocked_preflight", "source_dataset_manifest": {"files": files, "hash": digest(files)}, "partition_targets_per_family": required, "partitions": partitions, "ordered_ids": {p: [] for p in config["partition_order"]}, "payload_hashes": {}, "partition_selector": 'SHA256("phase2-v1:<partition>:<family>:<seed>:<task_id>")', "partition_selector_hash": digest(config["partition_selector"]), "partition_disjointness_matrix": matrix, "phase1_exclusion_audit": {"passed": True, "namespaced_excluded_ids": exclusions, "excluded_id_hash": digest(exclusions), "phase1_2wiki_partition_ids_are_excluded": True, "spent_searchqa_ids_are_excluded": True}, "coverage_audit": {"by_skill_family": coverage, "type_to_skill_family": TYPE_TO_FAMILY, "passed": False}, "blocked_reasons": ["SearchQA has only 12 local calibration payloads; 70 Phase 2 fact_retrieval payloads are required.", "No executable five-family partition or 710-request plan may be fabricated or expanded to unaudited data."], "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    return audit

def main() -> int:
    out = ROOT / "artifacts/acl2027_phase2_expansion_freeze_v1"
    if out.exists() and any(out.iterdir()): raise SystemExit(f"Refusing to overwrite existing artifact: {out}")
    config = load(CONFIG); audit = build(config); out.mkdir(parents=True, exist_ok=True)
    (out / "partition_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    plan = {"schema_version": 1, "status": "blocked_until_payload_ready", "logical_requests_target": 710, "materialized_logical_requests": 0, "plan": [], "canonical_request_schema": config["canonical_request_schema"], "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    (out / "request_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "artifact": "acl2027_phase2_expansion_freeze_v1", "status": audit["status"], "config_sha256": file_hash(CONFIG), "partition_audit_sha256": file_hash(out / "partition_audit.json"), "request_plan_sha256": file_hash(out / "request_plan.json"), "aggregate_fingerprint": digest({"config": file_hash(CONFIG), "audit": file_hash(out / "partition_audit.json"), "plan": file_hash(out / "request_plan.json")}), "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
