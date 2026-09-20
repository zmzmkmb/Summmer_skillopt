#!/usr/bin/env python3
"""No-paid Phase 1C proxy-to-real reconciliation analysis."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/searchqa_phase1c_proxy_reconciliation_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def paired_metrics(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    indexed = {(row["seed"], row["item_id"], row["method"]): row for row in rows}
    pairs = []
    for (seed, item_id, method), row in indexed.items():
        if method != left:
            continue
        other = indexed.get((seed, item_id, right))
        if other is None:
            continue
        pairs.append({
            "seed": seed,
            "item_id": item_id,
            "left_em": float(row["em"]),
            "right_em": float(other["em"]),
            "delta_em": float(row["em"]) - float(other["em"]),
            "left_f1": float(row["f1"]),
            "right_f1": float(other["f1"]),
            "delta_f1": float(row["f1"]) - float(other["f1"]),
            "left_sub_em": float(row["sub_em"]),
            "right_sub_em": float(other["sub_em"]),
            "delta_sub_em": float(row["sub_em"]) - float(other["sub_em"]),
            "left_tokens": int(row["total_tokens"]),
            "right_tokens": int(other["total_tokens"]),
            "delta_tokens": int(row["total_tokens"]) - int(other["total_tokens"]),
        })
    result: dict[str, Any] = {"left": left, "right": right, "n_pairs": len(pairs), "pairs": pairs}
    for metric in ("em", "f1", "sub_em", "tokens"):
        deltas = [float(pair[f"delta_{metric}"]) for pair in pairs]
        result[f"delta_{metric}"] = {
            "mean": mean(deltas),
            "median": statistics.median(deltas) if deltas else None,
            "wins": sum(value > 0 for value in deltas),
            "ties": sum(value == 0 for value in deltas),
            "losses": sum(value < 0 for value in deltas),
        }
    by_seed = {}
    for seed in sorted({pair["seed"] for pair in pairs}):
        seed_pairs = [pair for pair in pairs if pair["seed"] == seed]
        by_seed[str(seed)] = {
            "n_pairs": len(seed_pairs),
        }
        for metric in ("em", "f1", "sub_em", "tokens"):
            by_seed[str(seed)][metric] = mean(
                [float(pair[f"delta_{metric}"]) for pair in seed_pairs]
            )
    result["by_seed"] = by_seed
    return result


def load_inputs(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    inputs = config["inputs"]
    phase1b_rows = [json.loads(line) for line in (ROOT / inputs["phase1b_calls"]).read_text(encoding="utf-8").splitlines() if line]
    with (ROOT / inputs["phase0n_summary"]).open(encoding="utf-8", newline="") as handle:
        phase0n_rows = list(csv.DictReader(handle))
    phase1b_summary = json.loads((ROOT / inputs["phase1b_summary"]).read_text(encoding="utf-8"))
    return phase1b_rows, phase0n_rows, phase1b_summary


def analyze(config: dict[str, Any]) -> dict[str, Any]:
    phase1b, phase0n, summary = load_inputs(config)
    evaluation = [row for row in phase1b if row.get("stage") == "evaluation" and row.get("status") == "completed"]
    probes = [row for row in phase1b if row.get("stage") == "guard_probe"]
    methods = sorted({row["method"] for row in evaluation})
    method_summary = {}
    for method in methods:
        rows = [row for row in evaluation if row["method"] == method]
        method_summary[method] = {
            "n": len(rows),
            "seeds": sorted({int(row["seed"]) for row in rows}),
            "em": mean([float(row["em"]) for row in rows]),
            "f1": mean([float(row["f1"]) for row in rows]),
            "sub_em": mean([float(row["sub_em"]) for row in rows]),
            "total_tokens": sum(int(row["total_tokens"]) for row in rows),
            "provider_attempts": sum(int(row["provider_attempts"]) for row in rows),
        }
    phase0n_methods = ["copied_global_reset_phase0k", "global_only_reset_phase0k", "global_only_selective_full_confirmation"]
    offline_summary = {}
    for method in phase0n_methods:
        rows = [row for row in phase0n if row.get("method") == method]
        offline_summary[method] = {
            "n": len(rows),
            "conditions": sorted({row.get("condition", "") for row in rows}),
            "mean_reward": mean([float(row["mean_reward"]) for row in rows]),
            "mean_final_window_reward": mean([float(row["final_window_reward"]) for row in rows]),
            "mean_total_tokens": mean([float(row["total_tokens"]) for row in rows]),
            "mean_amortized_total_tokens": mean([float(row["amortized_total_tokens"]) for row in rows]),
            "triggered": sum(row.get("prior_guard_triggered", "False") == "True" for row in rows),
            "accepted": sum(row.get("prior_guard_decision") == "acceptable" for row in rows),
            "rejected": sum(row.get("prior_guard_decision") == "harmful" for row in rows),
            "abstained": sum(row.get("prior_guard_decision") == "uncertain" for row in rows),
        }
    offline_pairs = {}
    for left, right in (("global_only_selective_full_confirmation", "global_only_reset_phase0k"),
                        ("global_only_selective_full_confirmation", "copied_global_reset_phase0k")):
        left_rows = {(row["condition"], row["seed"]): row for row in phase0n if row.get("method") == left}
        right_rows = {(row["condition"], row["seed"]): row for row in phase0n if row.get("method") == right}
        deltas = [float(left_rows[key]["mean_reward"]) - float(row["mean_reward"])
                  for key, row in right_rows.items() if key in left_rows]
        offline_pairs[f"{left}_vs_{right}"] = {
            "n_pairs": len(deltas),
            "mean_reward_delta": mean(deltas),
            "wins": sum(value > 0 for value in deltas),
            "ties": sum(value == 0 for value in deltas),
            "losses": sum(value < 0 for value in deltas),
        }
    attempts = [attempt for row in phase1b for attempt in row.get("attempts", [])]
    errors = Counter(attempt.get("provider_error_code") or attempt.get("status") for attempt in attempts if attempt.get("status") != "success")
    comparisons = [paired_metrics(evaluation, left, right) for left, right in config["diagnostics"]["primary_comparisons"]]
    guard_decisions = summary.get("guard_metrics", {})
    return {
        "analysis": "descriptive_only_held_out_and_immutable_summary",
        "phase1b": {
            "total_calls": len(phase1b),
            "evaluation_calls": len(evaluation),
            "guard_probe_calls": len(probes),
            "methods": method_summary,
            "comparisons": comparisons,
            "guard_metrics": guard_decisions,
            "non_success_attempts": dict(errors),
            "attempt_count": len(attempts),
        },
        "phase0n": {"rows": len(phase0n), "methods": offline_summary, "paired_comparisons": offline_pairs},
        "interpretation": {
            "held_out_tuning": False,
            "development_eligible_evidence": [],
            "next_decision": "stop_selective_guard_superiority_claim unless fresh development evidence localizes and fixes the mismatch",
        },
    }


def write_outputs(result: dict[str, Any], config: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    inputs = config["inputs"]
    fingerprints = {name: sha256_file(ROOT / path) for name, path in inputs.items() if (ROOT / path).is_file()}
    payload = {"config": config, "input_sha256": fingerprints, "result": result}
    (output_dir / "analysis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    result_path = output_dir / "analysis.json"
    (output_dir / "run_manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": "configs/acl2027/searchqa_phase1c_proxy_reconciliation_v1.json",
        "config_sha256": sha256_file(CONFIG_PATH),
        "complete_grid": True,
        "expected_runs": 1,
        "available_runs": 1,
        "runs": [{
            "run_id": "phase1c_proxy_reconciliation",
            "status": "completed",
            "result_path": "artifacts/acl2027_searchqa_phase1c_proxy_reconciliation_v1/analysis.json",
            "file_sha256": sha256_file(result_path),
        }],
        "analysis_only": True,
        "network_calls": 0,
        "input_sha256": fingerprints,
        "result_sha256": sha256_file(output_dir / "analysis.json"),
        "aggregate_fingerprint": sha256_file(output_dir / "analysis.json"),
    }, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--output", default="artifacts/acl2027_searchqa_phase1c_proxy_reconciliation_v1")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config["execution"]["paid_api_allowed"] or config["execution"]["network_calls_allowed"]:
        raise SystemExit("Phase 1C requires paid_api_allowed=false and network_calls_allowed=false")
    result = analyze(config)
    write_outputs(result, config, ROOT / args.output)
    print(json.dumps({
        "experiment": config["experiment"],
        "output": str(ROOT / args.output),
        "phase1b_evaluation_calls": result["phase1b"]["evaluation_calls"],
        "phase0n_rows": result["phase0n"]["rows"],
        "comparisons": [{"left": row["left"], "right": row["right"], "n_pairs": row["n_pairs"]} for row in result["phase1b"]["comparisons"]],
        "network_calls": 0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
