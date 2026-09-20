#!/usr/bin/env python3
"""Run ACL 2027 synthetic continual-routing experiment grids."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skillopt.evaluation.continual_routing import (
    MethodSpec,
    generate_contextual_synthetic_stream,
    generate_synthetic_stream,
    evaluate_prior_representativeness,
    run_continual_experiment,
    stream_fingerprint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/acl2027/offline_continual_v1.json")
    parser.add_argument("--out", default="artifacts/acl2027_continual_v1")
    parser.add_argument("--force", action="store_true", help="Recompute completed run files.")
    parser.add_argument("--limit-runs", type=int, default=0, help="Stop after N grid runs; 0 means all.")
    return parser.parse_args()


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "-" for char in value)


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["method"]), str(row["condition"]), str(row.get("corruption_name", "none")))
        groups.setdefault(key, []).append(row)
    metrics = [
        "mean_reward", "final_window_reward", "cumulative_regret", "mean_regret",
        "total_tokens", "inference_tokens", "credit_update_tokens", "probe_tokens",
        "gate_validation_tokens", "guard_validation_tokens", "guard_amortized_validation_tokens",
        "amortized_total_tokens", "prior_guard_triggered", "prior_guard_state_mutated",
        "prior_guard_reset_magnitude",
        "prior_guard_rounds_used", "prior_guard_paired_samples", "search_overhead_ratio",
        "reward_per_1k_tokens",
        "amortized_reward_per_1k_tokens",
        "utility_calibration_mae", "utility_rank_correlation", "average_forgetting",
        "worst_domain_forgetting", "gate_evaluations", "gate_accepts", "gate_rejects",
        "update_acceptance_rate", "mean_new_domain_plasticity", "worst_old_domain_delta",
        "safety_violations", "worst_accepted_regression", "routing_ms_mean",
        "harmful_rule_selection_rate", "malicious_rule_selection_rate",
        "conflict_rule_selection_rate", "duplicate_coselection_rate",
    ]
    nullable_metrics = [
        "tokens_to_target", "utility_recovery_tokens", "corruption_recovery_tokens",
        "post_drift_recovery_tokens", "prior_guard_learned_score",
        "prior_guard_relevance_score", "prior_guard_reference_score",
        "prior_guard_margin", "prior_guard_recovery_slope", "amortized_tokens_to_target",
    ]
    aggregated = []
    for (method, condition, corruption_name), members in sorted(groups.items()):
        item: dict[str, Any] = {
            "method": method,
            "condition": condition,
            "corruption_name": corruption_name,
            "corruption_mode": members[0].get("corruption_mode", "none"),
            "corruption_block": members[0].get("corruption_block"),
            "policy": members[0]["policy"],
            "credit": members[0]["credit"],
            "estimator": members[0].get("estimator", "global"),
            "prior_identity": members[0].get("prior_identity", "copied-global"),
            "gate": members[0].get("gate", "none"),
            "effective_policy": members[0].get("effective_policy", members[0]["policy"]),
            "effective_credit": members[0].get("effective_credit", members[0]["credit"]),
            "effective_gate": members[0].get("effective_gate", members[0].get("gate", "none")),
            "prior_guard": members[0].get("prior_guard", "none"),
            "prior_guard_tolerance": members[0].get("prior_guard_tolerance", 0.0),
            "prior_guard_probe_domains": members[0].get("prior_guard_probe_domains", "all"),
            "prior_guard_max_probes_per_domain": members[0].get("prior_guard_max_probes_per_domain", 0),
            "prior_guard_sequential": members[0].get("prior_guard_sequential", False),
            "prior_guard_confidence_z": members[0].get("prior_guard_confidence_z", 1.96),
            "prior_guard_min_samples": members[0].get("prior_guard_min_samples", 3),
            "prior_guard_min_accept_rounds": members[0].get("prior_guard_min_accept_rounds", 0),
            "prior_guard_min_reset_rounds": members[0].get("prior_guard_min_reset_rounds", 0),
            "prior_guard_min_harm_margin": members[0].get("prior_guard_min_harm_margin", 0.0),
            "prior_guard_recovery_window": members[0].get("prior_guard_recovery_window", 0),
            "prior_guard_max_recovery_slope": members[0].get("prior_guard_max_recovery_slope"),
            "prior_guard_relevance_cost_share": members[0].get("prior_guard_relevance_cost_share", 1.0),
            "prior_guard_probe_order": members[0].get("prior_guard_probe_order", "stream"),
            "prior_guard_reference": members[0].get("prior_guard_reference", "relevance"),
            "prior_guard_evaluation": members[0].get("prior_guard_evaluation", "frozen"),
            "prior_guard_actions": ",".join(sorted({
                str(member.get("prior_guard_action", "none")) for member in members
            })),
            "prior_guard_decisions": ",".join(sorted({
                str(member.get("prior_guard_decision", "none")) for member in members
            })),
            "prior_guard_stop_reasons": ",".join(sorted({
                str(member.get("prior_guard_stop_reason", "none")) for member in members
            })),
            "context_weight": members[0].get("context_weight", 0.75),
            "context_weight_mode": members[0].get("context_weight_mode", "fixed"),
            "context_evidence_scale": members[0].get("context_evidence_scale", 8.0),
            "context_min_weight": members[0].get("context_min_weight", 0.0),
            "context_max_weight": members[0].get("context_max_weight", 0.9),
            "n_runs": len(members),
            "seeds": ",".join(str(row["seed"]) for row in sorted(members, key=lambda row: row["seed"])),
        }
        for metric in metrics:
            values = [float(row.get(metric, 0.0)) for row in members]
            item[f"{metric}_mean"] = statistics.mean(values)
            item[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        for metric in nullable_metrics:
            values = [float(row[metric]) for row in members if row.get(metric) is not None]
            item[f"{metric}_successes"] = len(values)
            item[f"{metric}_mean"] = statistics.mean(values) if values else None
            item[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0 if values else None
        aggregated.append(item)
    return aggregated


def _make_stream(config: dict[str, Any], seed: int):
    generator = (
        generate_contextual_synthetic_stream
        if config.get("stream_type", "legacy") == "contextual"
        else generate_synthetic_stream
    )
    return generator(
        seed=seed,
        n_rules=int(config["n_rules"]),
        domains=config["domains"],
        block_order=config["block_order"],
        tasks_per_block=int(config["tasks_per_block"]),
        probe_tasks_per_domain=int(config["probe_tasks_per_domain"]),
    )



def _rank_values(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    for rank, index in enumerate(order):
        ranks[index] = float(rank)
    return ranks


def _safe_correlation(left: list[float], right: list[float]) -> float:
    if len(left) < 2 or len(set(left)) < 2 or len(set(right)) < 2:
        return 0.0
    return float(statistics.correlation(left, right))


def _aggregate_prior_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row["condition"]), []).append(row)
    metrics = [
        "global_prior_pearson", "global_prior_spearman",
        "domain_prior_spearman_mean", "domain_prior_spearman_min",
        "guard_margin", "guard_triggered", "guard_rounds_used",
        "prefix_probe_margin", "all_probe_margin", "phase0_stream_margin",
        "prefix_probe_stream_sign_agreement", "all_probe_stream_sign_agreement",
        "all_probe_learned_selected_domain_utility_mean",
        "all_probe_learned_selected_harmful_fraction",
        "phase0_stream_learned_selected_domain_utility_mean",
        "phase0_stream_learned_selected_harmful_fraction",
    ]
    aggregated: list[dict[str, Any]] = []
    for condition, members in sorted(groups.items()):
        ordered = sorted(members, key=lambda row: int(row["seed"]))
        item: dict[str, Any] = {
            "condition": condition,
            "base_condition": ordered[0]["base_condition"],
            "prior_identity": ordered[0]["prior_identity"],
            "n_runs": len(ordered),
            "seeds": ",".join(str(row["seed"]) for row in ordered),
            "guard_stop_reasons": ",".join(sorted({str(row["guard_stop_reason"]) for row in ordered})),
        }
        for metric in metrics:
            values = [float(row[metric]) for row in ordered]
            item[f"{metric}_mean"] = statistics.mean(values)
            item[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
            item[f"{metric}_min"] = min(values)
            item[f"{metric}_max"] = max(values)
        prefix = [float(row["prefix_probe_margin"]) for row in ordered]
        all_probe = [float(row["all_probe_margin"]) for row in ordered]
        stream = [float(row["phase0_stream_margin"]) for row in ordered]
        item["prefix_probe_to_stream_pearson"] = _safe_correlation(prefix, stream)
        item["prefix_probe_to_stream_spearman"] = _safe_correlation(
            _rank_values(prefix), _rank_values(stream)
        )
        item["all_probe_to_stream_pearson"] = _safe_correlation(all_probe, stream)
        item["all_probe_to_stream_spearman"] = _safe_correlation(
            _rank_values(all_probe), _rank_values(stream)
        )
        item["positive_phase0_stream_runs"] = sum(
            float(row["phase0_stream_margin"]) > 0.0 for row in ordered
        )
        item["negative_phase0_stream_runs"] = sum(
            float(row["phase0_stream_margin"]) < 0.0 for row in ordered
        )
        item["guard_triggered_runs"] = sum(bool(row["guard_triggered"]) for row in ordered)
        item["prefix_probe_stream_sign_agreement_runs"] = sum(
            bool(row["prefix_probe_stream_sign_agreement"]) for row in ordered
        )
        item["all_probe_stream_sign_agreement_runs"] = sum(
            bool(row["all_probe_stream_sign_agreement"]) for row in ordered
        )
        aggregated.append(item)
    return aggregated


def _run_prior_diagnostic(
    *, args: argparse.Namespace, config: dict[str, Any], config_path: Path,
    config_hash: str, out_dir: Path,
) -> int:
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(item) for item in config["seeds"]]
    conditions = list(config["prior_identity_conditions"])
    expected_runs = len(seeds) * len(conditions)
    if int(config.get("expected_runs", expected_runs)) != expected_runs:
        raise ValueError("Phase 0L expected_runs does not match seeds x prior identities")
    method = MethodSpec(**config["guard_method"])
    summaries: list[dict[str, Any]] = []
    run_entries: list[dict[str, Any]] = []
    processed = 0
    for seed in seeds:
        stream = _make_stream(config, seed)
        stream_hash = stream_fingerprint(stream)
        for condition_spec in conditions:
            if args.limit_runs and processed >= args.limit_runs:
                break
            condition_name = str(condition_spec["name"])
            base_condition = str(condition_spec["base_condition"])
            identity = str(condition_spec["identity"])
            run_id = f"prior-diagnostic-{config_hash[:10]}-{_safe_name(condition_name)}-seed{seed}"
            result_path = runs_dir / f"{run_id}.json"
            if result_path.exists() and not args.force:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                if payload.get("config_sha256") != config_hash:
                    raise RuntimeError(f"Existing run has a different config hash: {result_path}")
                status = "resumed"
            else:
                payload = evaluate_prior_representativeness(
                    stream=stream, method=method, condition=base_condition,
                    identity=identity, seed=seed, top_k=int(config["top_k"]),
                    budget=int(config["budget"]), prior_strength=float(config["prior_strength"]),
                    prefix_probe_rounds=int(config["prefix_probe_rounds"]),
                    phase0_blocks=int(config["phase0_blocks"]),
                )
                payload.update({
                    "run_id": run_id,
                    "condition_name": condition_name,
                    "base_condition": base_condition,
                    "prior_identity": identity,
                    "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
                    "config_sha256": config_hash,
                    "stream_fingerprint": stream_hash,
                })
                result_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                status = "executed"
            summary = dict(payload["summary"])
            summary.update({
                "condition": condition_name,
                "base_condition": base_condition,
                "prior_identity": identity,
                "run_id": run_id,
                "run_fingerprint": payload["diagnostic_fingerprint"],
                "stream_fingerprint": stream_hash,
                "result_path": result_path.relative_to(PROJECT_ROOT).as_posix(),
            })
            summaries.append(summary)
            run_entries.append({
                "run_id": run_id,
                "status": status,
                "seed": seed,
                "condition": condition_name,
                "base_condition": base_condition,
                "prior_identity": identity,
                "result_path": result_path.relative_to(PROJECT_ROOT).as_posix(),
                "file_sha256": _sha256_bytes(result_path.read_bytes()),
                "run_fingerprint": payload["diagnostic_fingerprint"],
                "stream_fingerprint": stream_hash,
            })
            processed += 1
            print(
                f"[{processed:03d}/{expected_runs:03d}] {status:<8} seed={seed} "
                f"condition={condition_name:<23} guard={summary['guard_margin']:+.3f} "
                f"all-probe={summary['all_probe_margin']:+.3f} "
                f"stream={summary['phase0_stream_margin']:+.3f}",
                flush=True,
            )
        if args.limit_runs and processed >= args.limit_runs:
            break

    aggregated = _aggregate_prior_diagnostics(summaries)
    complete_grid = processed == expected_runs
    result_payload = {
        "schema_version": int(config.get("schema_version", 7)),
        "scope": config["scope"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
        "config_sha256": config_hash,
        "complete_grid": complete_grid,
        "expected_runs": expected_runs,
        "available_runs": len(summaries),
        "summaries": summaries,
        "aggregated": aggregated,
    }
    result_payload["aggregate_fingerprint"] = _canonical_hash({
        "config_sha256": config_hash,
        "summaries": summaries,
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if summaries:
        with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows(summaries)
    if aggregated:
        with (out_dir / "aggregate.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(aggregated[0]))
            writer.writeheader()
            writer.writerows(aggregated)
    manifest = {
        "schema_version": int(config.get("schema_version", 7)),
        "experiment": config["experiment"],
        "scope": config["scope"],
        "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
        "config_sha256": config_hash,
        "complete_grid": complete_grid,
        "expected_runs": expected_runs,
        "available_runs": len(run_entries),
        "aggregate_fingerprint": result_payload["aggregate_fingerprint"],
        "runs": run_entries,
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Results: {out_dir / 'results.json'}")
    print(f"Manifest: {out_dir / 'run_manifest.json'}")
    return 0

def main() -> int:
    args = parse_args()
    config_path = _resolve(args.config)
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes.decode("utf-8-sig"))
    config_hash = _sha256_bytes(config_bytes)
    out_dir = _resolve(args.out)
    if config.get("experiment_mode") == "prior-representativeness-diagnostic":
        return _run_prior_diagnostic(
            args=args, config=config, config_path=config_path,
            config_hash=config_hash, out_dir=out_dir,
        )
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    methods = [MethodSpec(**item) for item in config["methods"]]
    conditions = [str(item) for item in config["utility_conditions"]]
    corruptions = config.get("corruptions", [{"name": "none", "mode": "none", "block": None}])
    seeds = [int(item) for item in config["seeds"]]
    summaries: list[dict[str, Any]] = []
    run_entries: list[dict[str, Any]] = []
    processed = 0
    expected_runs = len(seeds) * len(conditions) * len(corruptions) * len(methods)
    if int(config.get("expected_runs", expected_runs)) != expected_runs:
        raise ValueError("expected_runs does not match seeds x conditions x corruptions x methods")

    for seed in seeds:
        stream = _make_stream(config, seed)
        stream_hash = stream_fingerprint(stream)
        for condition in conditions:
            for corruption in corruptions:
                corruption_name = str(corruption.get("name", corruption.get("mode", "none")))
                corruption_mode = str(corruption.get("mode", "none"))
                corruption_block = corruption.get("block")
                corruption_block = int(corruption_block) if corruption_block is not None else None
                for method in methods:
                    if args.limit_runs and processed >= args.limit_runs:
                        break
                    run_id = (
                        f"continual-{config_hash[:10]}-{_safe_name(condition)}-"
                        f"{_safe_name(corruption_name)}-{_safe_name(method.name)}-seed{seed}"
                    )
                    result_path = runs_dir / f"{run_id}.json"
                    if result_path.exists() and not args.force:
                        payload = json.loads(result_path.read_text(encoding="utf-8"))
                        if payload.get("config_sha256") != config_hash:
                            raise RuntimeError(f"Existing run has a different config hash: {result_path}")
                        status = "resumed"
                    else:
                        payload = run_continual_experiment(
                            stream=stream,
                            method=method,
                            condition=condition,
                            seed=seed,
                            top_k=int(config["top_k"]),
                            budget=int(config["budget"]),
                            token_target=float(config["token_target"]),
                            target_window=int(config["target_window"]),
                            target_sustain=int(config["target_sustain"]),
                            prior_strength=float(config["prior_strength"]),
                            corruption_mode=corruption_mode,
                            corruption_block=corruption_block,
                            recovery_correlation_target=float(config.get("recovery_correlation_target", 0.25)),
                            recovery_sustain=int(config.get("recovery_sustain", 5)),
                        )
                        payload.update({
                            "run_id": run_id,
                            "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
                            "config_sha256": config_hash,
                            "stream_fingerprint": stream_hash,
                            "corruption_name": corruption_name,
                        })
                        result_path.write_text(
                            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                        )
                        status = "executed"
                    summary = dict(payload["summary"])
                    summary.update({
                        "run_id": run_id,
                        "run_fingerprint": payload["run_fingerprint"],
                        "stream_fingerprint": stream_hash,
                        "result_path": result_path.relative_to(PROJECT_ROOT).as_posix(),
                        "corruption_name": corruption_name,
                        "corruption_mode": corruption_mode,
                        "corruption_block": corruption_block,
                    })
                    summaries.append(summary)
                    run_entries.append({
                        "run_id": run_id,
                        "status": status,
                        "seed": seed,
                        "condition": condition,
                        "corruption_name": corruption_name,
                        "corruption_mode": corruption_mode,
                        "corruption_block": corruption_block,
                        "method": method.name,
                        "result_path": result_path.relative_to(PROJECT_ROOT).as_posix(),
                        "file_sha256": _sha256_bytes(result_path.read_bytes()),
                        "run_fingerprint": payload["run_fingerprint"],
                        "stream_fingerprint": stream_hash,
                    })
                    processed += 1
                    print(
                        f"[{processed:03d}/{expected_runs:03d}] {status:<8} seed={seed} "
                        f"condition={condition:<11} corruption={corruption_name:<18} "
                        f"method={method.name:<34} reward={summary['mean_reward']:.3f} "
                        f"tokens={summary['total_tokens']}",
                        flush=True,
                    )
                if args.limit_runs and processed >= args.limit_runs:
                    break
            if args.limit_runs and processed >= args.limit_runs:
                break
        if args.limit_runs and processed >= args.limit_runs:
            break

    aggregated = _aggregate(summaries)
    result_payload = {
        "schema_version": int(config.get("schema_version", 2)),
        "scope": config["scope"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
        "config_sha256": config_hash,
        "complete_grid": processed == expected_runs,
        "expected_runs": expected_runs,
        "available_runs": len(summaries),
        "summaries": summaries,
        "aggregated": aggregated,
    }
    result_payload["aggregate_fingerprint"] = _canonical_hash({
        "config_sha256": config_hash,
        "summaries": [{k: v for k, v in row.items() if k != "routing_ms_mean"} for row in summaries],
    })
    (out_dir / "results.json").write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if summaries:
        with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows(summaries)
    if aggregated:
        with (out_dir / "aggregate.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(aggregated[0]))
            writer.writeheader()
            writer.writerows(aggregated)

    manifest = {
        "schema_version": int(config.get("schema_version", 1)),
        "experiment": config["experiment"],
        "scope": config["scope"],
        "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
        "config_sha256": config_hash,
        "complete_grid": result_payload["complete_grid"],
        "expected_runs": result_payload["expected_runs"],
        "available_runs": len(run_entries),
        "aggregate_fingerprint": result_payload["aggregate_fingerprint"],
        "runs": run_entries,
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Results: {out_dir / 'results.json'}")
    print(f"Manifest: {out_dir / 'run_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
