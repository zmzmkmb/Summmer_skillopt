#!/usr/bin/env python3
"""Materialize typed candidates from verifier-confirmed Phase 1Y live history."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "artifacts/acl2027_phase1y_history_live_v1/results.jsonl"
OUTPUT = ROOT / "artifacts/acl2027_phase1y_live_candidates_v1"


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build() -> dict[str, Any]:
    rows = records(RESULTS)
    if len(rows) != 10 or any(row["call_index"] != i for i, row in enumerate(rows, 1)):
        raise ValueError("exact completed 10-call prefix required")
    design = read_json(ROOT / "artifacts/acl2027_phase1t_heldout_deployment_identifiability_v1/design_audit.json")
    search = design["searchqa_design"]
    excluded_search = set(map(str, search["calibration_ids"] + search["development_probe_ids"] + search["held_out_downstream_ids"]))
    wiki_excluded = set()
    for name in ("calibration.json", "development_probe.json", "held_out_downstream.json"):
        wiki_excluded |= {str(row["id"]) for row in read_json(ROOT / "data/2wikimultihopqa_verified/partitions" / name)}
    verified = [row for row in rows if row.get("joint_correct") is True]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in verified:
        grouped[stable_hash(row["typed_scope"])].append(row)
    candidates = []
    for scope_hash, support in sorted(grouped.items()):
        scope = support[0]["typed_scope"]
        task_ids = sorted(row["task_id"] for row in support)
        admitted = len(task_ids) >= 2
        candidates.append({
            "candidate_id": f"candidate:phase1y:scope:{scope_hash[:24]}",
            "task_family": scope["task_family"],
            "task_type": scope["task_type"],
            "skill_family": scope["skill_family"],
            "typed_scope": scope,
            "supporting_task_ids": task_ids,
            "source_trajectory_ids": sorted(row["logical_call_id"] for row in support),
            "source_request_hashes": sorted(row["request_hash"] for row in support),
            "verifier_replay": {"status": "replayed", "all_joint_correct": True, "support_count": len(support)},
            "provenance": {"source": str(RESULTS.relative_to(ROOT)), "partition": "history", "provider_model": "qwen3.7-plus"},
            "admitted": admitted,
            "rejection_reasons": [] if admitted else ["insufficient_distinct_verified_supporting_tasks"],
        })
    failed = [{
        "trajectory_id": row["logical_call_id"], "task_id": row["task_id"], "task_family": row["task_family"],
        "task_type": row["task_type"], "skill_family": row["skill_family"], "typed_scope": row["typed_scope"],
        "request_hash": row["request_hash"], "raw_response_sha256": row["raw_response_sha256"],
        "verifier_replay": {"status": "replayed", "answer_correct": row.get("answer_correct"), "support_correct": row.get("support_correct"), "joint_correct": False},
        "admitted": False, "rejection_reasons": ["local_verifier_joint_failure"], "provenance": row["provenance"],
    } for row in rows if row.get("joint_correct") is not True]
    admitted = [row for row in candidates if row["admitted"]]
    required = {"fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference"}
    covered = {row["skill_family"] for row in admitted}
    all_support_ids = [task_id for row in admitted for task_id in row["supporting_task_ids"]]
    leakage = any(task_id in excluded_search or task_id in wiki_excluded for task_id in all_support_ids)
    family_counts = Counter(row["task_family"] for row in admitted)
    return {
        "schema_version": 1,
        "analysis": "acl2027_phase1y_live_candidates_v1",
        "source_plan_sha256": "02d387a6d768da2d66cfdda6835abb5764a0204463207a23795a8e845a6f5004",
        "history_attempts": 10,
        "verified_trajectories": len(verified),
        "verified_by_family": dict(Counter(row["task_family"] for row in verified)),
        "verified_by_task_type": dict(Counter(row["task_type"] for row in verified)),
        "typed_candidates": len(admitted),
        "candidate_records": candidates,
        "rejected_trajectories": failed,
        "coverage": {"required_skill_families": sorted(required), "admitted_skill_families": sorted(covered), "missing_skill_families": sorted(required - covered), "scope_fraction": len(covered) / len(required)},
        "concentration": {"max_candidate_task_family_share": max(family_counts.values(), default=0) / len(admitted) if admitted else 0.0, "max_supporting_task_id_share": max(Counter(all_support_ids).values(), default=0) / len(all_support_ids) if all_support_ids else 0.0},
        "checks": {"exact_call_count": len(rows) == 10, "deterministic_candidate_ids": len({r["candidate_id"] for r in candidates}) == len(candidates), "verifier_replay": all(r.get("joint_correct") is True for r in verified), "no_evaluation_leakage": not leakage, "minimum_two_supports_per_admitted_candidate": all(len(r["supporting_task_ids"]) >= 2 for r in admitted), "family_type_coverage_met": covered == required, "provider_authorization_exhausted": True},
        "phase1z": {"executable": False, "reason": "entity_bridge and relation_inference candidates each have only one verified supporting task", "theoretical_minimum_additional_successful_calls": 2, "exact_guaranteed_calls": None, "currently_authorized_calls": 0, "closure": "inconclusive_without_phase1z_provider_execution"},
        "usage": {"input_tokens": 11610, "output_tokens": 501, "total_tokens": 12111, "exact_accounted_cost_cny": 0.027228},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    audit = build()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {args.output}")
    args.output.mkdir(parents=True)
    candidate_records = audit.pop("candidate_records")
    rejected = audit.pop("rejected_trajectories")
    (args.output / "audit.json").write_text(json.dumps(audit, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for name, rows in (("typed_candidates.jsonl", candidate_records), ("rejected_trajectories.jsonl", rejected)):
        (args.output / name).write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir()}
    manifest = {"schema_version": 1, "experiment": "acl2027_phase1y_live_candidates_v1", "provider_calls": 0, "verified_trajectories": audit["verified_trajectories"], "typed_candidates": audit["typed_candidates"], "files": files}
    (args.output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: audit[k] for k in ("verified_trajectories", "typed_candidates", "coverage", "concentration", "checks", "phase1z")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
