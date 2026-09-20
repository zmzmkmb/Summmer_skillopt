#!/usr/bin/env python3
"""Materialize the exact, zero-retry Phase 1Y history request plan locally."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.isascii()


def wiki_context(context: list[list[Any]]) -> str:
    return "\n\n".join(f"Title: {title}\n" + "\n".join(f"[{i}] {text}" for i, text in enumerate(sentences)) for title, sentences in context)


def build(config: dict[str, Any]) -> dict[str, Any]:
    id_rows = read(ROOT / config["searchqa_ids"])
    payload_rows = {str(row["id"]): row for row in read(ROOT / config["searchqa_payload"])}
    design = read(ROOT / config["phase1t_design"])["searchqa_design"]
    history_ids = [str(x) for x in design["history_ids"]]
    calibration_ids = set(map(str, design["calibration_ids"]))
    probe_ids = set(map(str, design["development_probe_ids"]))
    heldout_ids = set(map(str, design["held_out_downstream_ids"]))
    spent = {str(row["item_id"]) for row in (ROOT / config["spent_calls"]).read_text(encoding="utf-8").splitlines() if row.strip() for row in [json.loads(row)]}
    if len(id_rows) != 400 or not set(history_ids).issubset({str(x["id"]) for x in id_rows}):
        raise ValueError("SearchQA history ID binding failed")
    if calibration_ids & set(history_ids) or probe_ids & set(history_ids) or heldout_ids & set(history_ids) or spent & set(history_ids):
        raise ValueError("SearchQA history leaks into an excluded or spent partition")
    candidates = [payload_rows[x] for x in history_ids if x in payload_rows]
    if len(candidates) != 120 or any(not (nonblank(r.get("question")) and nonblank(r.get("context")) and isinstance(r.get("answers"), list) and r["answers"] and all(nonblank(a) for a in r["answers"])) for r in candidates):
        raise ValueError("complete ASCII SearchQA history payloads are required")
    selected = sorted(candidates, key=lambda r: hashlib.sha256(f"SearchQA:phase1y-minimum:{r['id']}".encode()).hexdigest())[:2]
    search_system = "Answer the question using the supplied context. Return strict JSON with exactly one key: answer. answer must be a non-empty string. No markdown or extra keys."
    plan: list[dict[str, Any]] = []
    for row in selected:
        request = {"temperature": 0, "messages": [{"role": "system", "content": search_system}, {"role": "user", "content": f"Question: {row['question']}\n\nContext: {row['context']}"}]}
        plan.append({"task_family": "SearchQA", "task_id": str(row["id"]), "task_type": "single_hop_qa", "skill_family": "fact_retrieval", "typed_scope": {"task_family": "SearchQA", "task_type": "single_hop_qa", "skill_family": "fact_retrieval", "support_contract": "answer"}, "request": request, "request_hash": stable_hash(request), "payload_sha256": stable_hash(row), "provenance": {"payload_source": config["searchqa_payload"], "partition": "history", "source_record_id": str(row["id"]), "source_record_verified": True}, "retries": 0, "max_tokens_present": False})
    wiki = read(ROOT / config["two_wiki_history"])
    by_type = {t: sorted([r for r in wiki if r["dataset_task_type"] == t], key=lambda r: hashlib.sha256(f"{t}:phase1y-minimum:{r['id']}".encode()).hexdigest())[:2] for t in ("comparison", "bridge_comparison", "compositional", "inference")}
    for t in by_type:
        for row in by_type[t]:
            request = {"temperature": 0, "messages": [{"role": "system", "content": "Answer the question using the supplied titled, sentence-indexed context. Return strict JSON with exactly the keys answer and supporting_evidence. answer must be a non-empty string. supporting_evidence must be a non-empty list of unique [title, sentence_index] pairs. Use the displayed zero-based sentence indices. No markdown or extra keys."}, {"role": "user", "content": f"Question: {row['question']}\n\nContext:\n{wiki_context(row['context'])}"}]}
            plan.append({"task_family": "2WikiMultiHopQA", "task_id": str(row["id"]), "task_type": t, "skill_family": row["skill_family"], "typed_scope": {"task_family": "2WikiMultiHopQA", "task_type": t, "skill_family": row["skill_family"], "support_contract": "answer_plus_supporting_evidence"}, "request": request, "request_hash": stable_hash(request), "payload_sha256": stable_hash(row), "provenance": {"payload_source": config["two_wiki_history"], "partition": "history", "source_record_id": str(row["id"]), "gold_is_not_trajectory": True}, "retries": 0, "max_tokens_present": False})
    for i, row in enumerate(plan, 1):
        row["call_index"] = i
        row["logical_call_id"] = f"phase1y-history:{row['task_family']}:{row['task_id']}"
    input_tokens = sum(len(m["content"]) for row in plan for m in row["request"]["messages"]) // 4 + len(plan)
    ceiling = (input_tokens * config["pricing"]["input_cny_per_million"] + len(plan) * config["pricing"]["output_token_ceiling"] * config["pricing"]["output_cny_per_million"]) / 1_000_000
    return {"schema_version": 1, "plan": plan, "plan_sha256": stable_hash(plan), "request_count": len(plan), "counts_by_family": {"SearchQA": 2, "2WikiMultiHopQA": 8}, "estimated_input_tokens": input_tokens, "output_token_ceiling": len(plan) * config["pricing"]["output_token_ceiling"], "cost_ceiling_cny": round(ceiling, 6), "cost_basis": config["pricing"], "resume": "exact append-only prefix; existing records must match call_index, logical_call_id, and request_hash; no skipping or reordering", "hard_stops": ["unknown_usage", "provider_exception", "request_hash_drift", "authorization_drift", "cost_ceiling", "non_prefix_resume", "duplicate_logical_call_id"], "authorization": "closed_until_fresh_explicit_authorization_for_exactly_10_attempts"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/acl2027/phase1y_history_request_plan_v1.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/acl2027_phase1y_history_request_plan_v1")
    args = parser.parse_args()
    result = build(read(args.config))
    if result["request_count"] != 10 or len({r["request_hash"] for r in result["plan"]}) != 10:
        raise ValueError("final plan must contain exactly 10 unique requests")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {args.output}")
    args.output.mkdir(parents=True)
    write(args.output / "request_plan.json", result["plan"])
    write(args.output / "plan_audit.json", result)
    manifest = {"schema_version": 1, "experiment": "acl2027_phase1y_history_request_plan_v1", "config_sha256": file_hash(args.config), "plan_sha256": result["plan_sha256"], "request_count": 10, "provider_calls": 0, "network_calls": 0, "cost_ceiling_cny": result["cost_ceiling_cny"], "files": {"request_plan": file_hash(args.output / "request_plan.json"), "plan_audit": file_hash(args.output / "plan_audit.json")}}
    write(args.output / "run_manifest.json", manifest)
    print(json.dumps({k: result[k] for k in ("plan_sha256", "request_count", "counts_by_family", "estimated_input_tokens", "output_token_ceiling", "cost_ceiling_cny", "resume", "hard_stops")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
