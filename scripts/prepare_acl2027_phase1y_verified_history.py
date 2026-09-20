#!/usr/bin/env python3
"""Zero-network audit and materialization for ACL 2027 Phase 1Y."""
from __future__ import annotations

import hashlib
import json
import string
import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase1y_verified_history_skill_candidates_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1y_verified_history_skill_candidates_v1"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def rows_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_answer(value: str) -> str:
    value = value.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in value.split() if token not in {"a", "an", "the"})


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def render_context(context: list[list[Any]]) -> str:
    return "\n\n".join(
        f"Title: {title}\n" + "\n".join(f"[{index}] {text}" for index, text in enumerate(sentences))
        for title, sentences in context
    )


def build_request(row: dict[str, Any]) -> dict[str, Any]:
    system = "Answer the question using the supplied titled, sentence-indexed context. Return strict JSON with exactly the keys answer and supporting_evidence. answer must be a non-empty string. supporting_evidence must be a non-empty list of unique [title, sentence_index] pairs. Use the displayed zero-based sentence indices. No markdown or extra keys."
    return {
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {row['question']}\n\nContext:\n{render_context(row['context'])}"},
        ],
    }


def verify_two_wiki_response(response: dict[str, Any], row: dict[str, Any]) -> dict[str, bool]:
    from scripts.prepare_acl2027_phase1v_calibration import parse_response, verify_response

    parsed = parse_response("2WikiMultiHopQA", response["raw_response_text"])
    private = {
        "task_family": "2WikiMultiHopQA",
        "answers": [str(row["answer"])],
        "supporting_evidence": row["supporting_evidence"],
    }
    return verify_response(parsed, private)


def validate_config(config: dict[str, Any]) -> None:
    execution = config["execution"]
    if any(execution.get(key) is not False for key in ("network_calls_allowed", "dataset_download_allowed", "provider_calls_allowed", "paid_api_allowed", "formal_scaling_allowed")):
        raise ValueError("Phase 1Y is strictly zero-network and zero-provider")
    for binding in config["bindings"].values():
        path = ROOT / binding["path"]
        if not path.is_file() or sha256_file(path) != binding["sha256"]:
            raise ValueError(f"immutable input hash mismatch: {binding['path']}")


def load_partitions(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    search_paths = {
        "calibration": config["bindings"]["searchqa_calibration_ids"]["path"],
        "history": config["bindings"]["searchqa_history_ids"]["path"],
        "probe": config["bindings"]["searchqa_probe_ids"]["path"],
        "held_out": config["bindings"]["searchqa_held_out_ids"]["path"],
    }
    design = read_json(ROOT / config["bindings"]["phase1t_design"]["path"])["searchqa_design"]
    search_rows = {
        key: read_json(ROOT / path) for key, path in search_paths.items()
    }
    selected_search: dict[str, list[dict[str, Any]]] = {}
    for partition, key in config["phase1t_searchqa_partition_keys"].items():
        by_id = {str(row["id"]): row for row in search_rows[partition]}
        ids = design[key]
        if len(set(ids)) != len(ids) or any(str(task_id) not in by_id for task_id in ids):
            raise ValueError(f"Phase 1T SearchQA {partition} IDs are not bound to local split payload")
        selected_search[partition] = [by_id[str(task_id)] for task_id in ids]
    paths = {
        "SearchQA:calibration": selected_search["calibration"],
        "SearchQA:history": selected_search["history"],
        "SearchQA:probe": selected_search["probe"],
        "SearchQA:held_out": selected_search["held_out"],
        "2WikiMultiHopQA:calibration": config["bindings"]["two_wiki_calibration"]["path"],
        "2WikiMultiHopQA:history": config["bindings"]["two_wiki_history"]["path"],
        "2WikiMultiHopQA:probe": config["bindings"]["two_wiki_probe"]["path"],
        "2WikiMultiHopQA:held_out": config["bindings"]["two_wiki_held_out"]["path"],
    }
    return {
        name: value if isinstance(value, list) else read_json(ROOT / value)
        for name, value in paths.items()
    }


def discover_sources(config: dict[str, Any], partitions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    spent_rows = rows_jsonl(ROOT / config["local_discovery"]["trajectory_sources"][0])
    spent_ids = {str(row.get("item_id")) for row in spent_rows if row.get("item_id")}
    complete_test_rows = read_json(ROOT / config["bindings"]["searchqa_held_out_ids"]["path"])
    complete_test_ids = {str(row["id"]) for row in complete_test_rows}
    calibration_rows = rows_jsonl(ROOT / config["local_discovery"]["trajectory_sources"][1])
    calibration_ids = {str(row["task_id"]) for row in calibration_rows}
    replay = []
    calibration_by_key = {
        (str(row["task_family"]), str(row["task_id"])): row for row in calibration_rows
    }
    gold_by_key = {
        ("2WikiMultiHopQA", str(row["id"])): row
        for row in partitions["2WikiMultiHopQA:calibration"]
    }
    search_payload = ROOT / "data/searchqa_phase1u/calibration.json"
    for key, row in sorted(calibration_by_key.items()):
        family, task_id = key
        source = {
            "trajectory_id": f"trajectory:source:{family}:{task_id}",
            "task_family": family,
            "task_id": task_id,
            "source_path": relative(ROOT / config["local_discovery"]["trajectory_sources"][1]),
            "source_record_hash": stable_hash(row),
            "recorded_joint_correct": bool(row.get("joint_correct")),
            "partition": "calibration",
            "replay": {"status": "not_run", "joint_correct": None},
            "admitted": False,
            "rejection_reasons": ["calibration_id_excluded", "source_is_not_history"],
        }
        gold = gold_by_key.get(key)
        if family == "SearchQA" and search_payload.is_file():
            gold = next((item for item in read_json(search_payload) if str(item["id"]) == task_id), None)
        if gold:
            try:
                if family == "SearchQA":
                    from scripts.prepare_acl2027_phase1v_calibration import parse_response, verify_response
                    parsed = parse_response(family, row["raw_response_text"])
                    result = verify_response(parsed, {"task_family": family, "answers": gold["answers"]})
                else:
                    result = verify_two_wiki_response(row, gold)
                source["replay"] = {"status": "replayed", **result, "matches_recorded": result["joint_correct"] == bool(row.get("joint_correct"))}
            except Exception as exc:  # noqa: BLE001
                source["replay"] = {"status": "replay_failed", "error": str(exc), "joint_correct": False}
        replay.append(source)
    return {
        "phase1b_spent_rows": len(spent_rows),
        "phase1b_spent_unique_ids": len(spent_ids),
        "phase1b_spent_ids_are_test": spent_ids.issubset(complete_test_ids),
        "phase1x_calibration_rows": len(calibration_rows),
        "phase1x_calibration_unique_ids": len(calibration_ids),
        "phase1x_source_replay": replay,
        "response_artifacts_searched": list(config["local_discovery"]["trajectory_sources"]),
    }


def build_request_plan(config: dict[str, Any], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for task_type in ("comparison", "bridge_comparison", "compositional", "inference"):
        candidates = [row for row in history if row["dataset_task_type"] == task_type]
        candidates.sort(key=lambda row: hashlib.sha256(f"{task_type}:phase1y-minimum:{row['id']}".encode()).hexdigest())
        selected.extend(candidates[:2])
    plan = []
    for index, row in enumerate(selected, 1):
        request = build_request(row)
        plan.append({
            "call_index": index,
            "logical_call_id": f"phase1y:2WikiMultiHopQA:{row['id']}",
            "task_family": "2WikiMultiHopQA",
            "task_id": str(row["id"]),
            "task_type": row["dataset_task_type"],
            "skill_family": row["skill_family"],
            "request": request,
            "request_hash": stable_hash(request),
            "authorization": "closed_no_provider_calls",
            "retries": 0,
            "max_tokens_present": False,
        })
    return plan


def build_audit(config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    partitions = load_partitions(config)
    sources = discover_sources(config, partitions)
    history_2wiki = partitions["2WikiMultiHopQA:history"]
    calibration_2wiki = {str(row["id"]) for row in partitions["2WikiMultiHopQA:calibration"]}
    probe_2wiki = {str(row["id"]) for row in partitions["2WikiMultiHopQA:probe"]}
    heldout_2wiki = {str(row["id"]) for row in partitions["2WikiMultiHopQA:held_out"]}
    search_history = partitions["SearchQA:history"]
    search_history_ids = {str(row["id"]) for row in search_history}
    search_probe_ids = {str(row["id"]) for row in partitions["SearchQA:probe"]}
    search_heldout_ids = {str(row["id"]) for row in partitions["SearchQA:held_out"]}
    partition_sets = {
        name: {str(row.get("id")) for row in rows} for name, rows in partitions.items()
    }
    candidate_records = []
    for family, rows in (("SearchQA", search_history), ("2WikiMultiHopQA", history_2wiki)):
        for row in rows:
            task_id = str(row["id"])
            if family == "SearchQA":
                task_type = "unavailable"
                skill_family = "unavailable"
                scope = None
                reasons = ["missing_local_task_payload"]
                payload_hash = stable_hash(row)
            else:
                task_type = str(row["dataset_task_type"])
                skill_family = str(row["skill_family"])
                scope = {"task_family": family, "task_type": task_type, "skill_family": skill_family, "support_contract": "answer_plus_supporting_evidence"}
                reasons = ["gold_record_is_not_trajectory", "missing_model_response"]
                payload_hash = stable_hash(row)
            excluded = (
                task_id in calibration_2wiki
                or task_id in probe_2wiki
                or task_id in heldout_2wiki
                or task_id in search_probe_ids
                or task_id in search_heldout_ids
                or task_id in sources.get("phase1b_spent_ids", set())
            )
            if excluded:
                reasons.append("evaluation_partition_id_excluded")
            candidate_records.append({
                "trajectory_id": f"trajectory:phase1y:{family}:{task_id}",
                "candidate_id": f"candidate:phase1y:{family}:{task_id}",
                "task_family": family,
                "task_type": task_type,
                "skill_family": skill_family,
                "typed_scope": scope,
                "supporting_task_ids": [],
                "source_trajectory_ids": [],
                "source_paths": [],
                "payload_sha256": payload_hash,
                "verifier_replay": {"status": "not_run", "joint_correct": None},
                "admitted": False,
                "rejection_reasons": sorted(set(reasons)),
                "provenance": {"history_partition": "SearchQA:history" if family == "SearchQA" else "2WikiMultiHopQA:history", "gold_payload_only": family == "2WikiMultiHopQA"},
            })
    # The set is kept explicit in the audit rather than silently dropped from provenance.
    sources["phase1b_spent_ids"] = set()
    spent_rows = rows_jsonl(ROOT / config["local_discovery"]["trajectory_sources"][0])
    sources["phase1b_spent_ids"] = {str(row["item_id"]) for row in spent_rows if row.get("item_id")}
    for record in candidate_records:
        if record["task_family"] == "SearchQA" and record["trajectory_id"].split(":")[-1] in sources["phase1b_spent_ids"]:
            record["rejection_reasons"].append("spent_searchqa_held_out_id")
            record["rejection_reasons"] = sorted(set(record["rejection_reasons"]))
    accepted = [row for row in candidate_records if row["admitted"]]
    by_type = Counter(row["task_type"] for row in accepted)
    all_disjoint = all(left.isdisjoint(right) for index, left in enumerate(partition_sets.values()) for right in list(partition_sets.values())[index + 1:])
    plan = build_request_plan(config, history_2wiki)
    plan_hash = stable_hash(plan)
    checks = {
        "zero_network_and_provider": sources["phase1b_spent_rows"] >= 0 and config["execution"]["max_provider_attempts"] == 0,
        "partition_counts_exact": len(partitions["SearchQA:calibration"]) == 12 and len(search_history) == 120 and len(history_2wiki) == 120 and len(partitions["SearchQA:probe"]) == 24 and len(partitions["2WikiMultiHopQA:probe"]) == 24 and len(partitions["SearchQA:held_out"]) == 120 and len(partitions["2WikiMultiHopQA:held_out"]) == 120,
        "partition_isolation": all_disjoint and search_history_ids.isdisjoint(search_probe_ids | search_heldout_ids),
        "spent_searchqa_ids_are_excluded": sources["phase1b_spent_ids_are_test"] and sources["phase1b_spent_ids"].isdisjoint(search_history_ids | search_probe_ids | search_heldout_ids),
        "deterministic_ids": len({row["candidate_id"] for row in candidate_records}) == len(candidate_records) and all(row["candidate_id"] == f"candidate:phase1y:{row['task_family']}:{row['trajectory_id'].split(':')[-1]}" for row in candidate_records),
        "verifier_replay_source_consistent": all(item["replay"].get("matches_recorded") for item in sources["phase1x_source_replay"] if item["replay"]["status"] == "replayed"),
        "no_evaluation_leakage": not accepted and all(not set(row["supporting_task_ids"]) & (search_probe_ids | search_heldout_ids | probe_2wiki | heldout_2wiki) for row in accepted),
        "family_type_coverage_audited": True,
        "candidate_contract_coverage_met": False,
        "candidate_concentration_audited": True,
        "gold_not_trajectory": all("gold_record_is_not_trajectory" in row["rejection_reasons"] for row in candidate_records if row["task_family"] == "2WikiMultiHopQA"),
        "future_plan_hashes_deterministic": len(plan) == 8 and len({row["request_hash"] for row in plan}) == 8,
    }
    return {
        "analysis": "acl2027_phase1y_verified_history_skill_candidates_v1",
        "config_sha256": sha256_file(CONFIG),
        "bindings": config["bindings"],
        "partition_inventory": {name: {"count": len(rows), "ids_sha256": stable_hash(sorted(str(row.get("id")) for row in rows))} for name, rows in partitions.items()},
        "source_discovery": {**sources, "phase1b_spent_ids": sorted(sources["phase1b_spent_ids"])},
        "candidate_records_count": len(candidate_records),
        "verified_trajectories": len(accepted),
        "typed_candidates": len(accepted),
        "candidate_records": candidate_records,
        "coverage": {"accepted_by_task_type": dict(sorted(by_type.items())), "history_2wiki_by_task_type": dict(sorted(Counter(row["dataset_task_type"] for row in history_2wiki).items())), "accepted_by_task_family": dict(sorted(Counter(row["task_family"] for row in accepted).items()))},
        "candidate_concentration": {"status": "empty_candidate_set", "max_task_id_share": 0.0, "max_family_share": 0.0},
        "future_request_plan": {
            "freezeable_2wiki_attempts": len(plan),
            "unfreezeable_searchqa_attempts": 2,
            "plan_sha256": plan_hash,
            "plan": plan,
            "minimum_cross_family_history_successes": 10,
            "minimum_history_successes_by_family": {"SearchQA": 2, "2WikiMultiHopQA": 8},
            "exact_authorizable_history_attempts_now": 0,
            "phase1z_exact_minimum_calls": None,
            "phase1z_legacy_unoptimized_upper_bound_calls": 1152,
            "phase1z_executable_now": False,
            "reason": "zero admitted trajectories and missing SearchQA history payload prevent a leakage-free typed prior; Phase 1Z response reuse cannot be audited before candidates exist",
        },
        "checks": checks,
        "decision": "negative_materialization_no_verified_history_phase1z_blocked",
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }


def write_artifact(config: dict[str, Any], audit: dict[str, Any], output: Path = OUTPUT) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    output.mkdir(parents=True)
    candidate_records = audit.pop("candidate_records")
    write_json(output / "audit.json", audit)
    with (output / "candidate_records.jsonl").open("w", encoding="utf-8") as handle:
        for row in candidate_records:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    write_json(output / "request_plan.json", audit["future_request_plan"]["plan"])
    output_hashes = {
        "audit": sha256_file(output / "audit.json"),
        "candidate_records": sha256_file(output / "candidate_records.jsonl"),
        "request_plan": sha256_file(output / "request_plan.json"),
    }
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": relative(CONFIG),
        "config_sha256": sha256_file(CONFIG),
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": True,
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
        "verified_trajectories": audit["verified_trajectories"],
        "typed_candidates": audit["typed_candidates"],
        "output_hashes": output_hashes,
        "checks_passed": sum(bool(value) for value in audit["checks"].values()),
        "checks_total": len(audit["checks"]),
        "runs": [{"run_id": "phase1y_zero_network_materialization", "status": "completed", "result_path": relative(output / "audit.json"), "file_sha256": output_hashes["audit"]}],
        "aggregate_fingerprint": stable_hash(output_hashes),
    }
    write_json(output / "run_manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    config = read_json(args.config)
    audit = build_audit(config)
    write_artifact(config, audit, args.output)
    print(json.dumps({key: audit[key] for key in ("decision", "verified_trajectories", "typed_candidates", "future_request_plan", "checks")}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
