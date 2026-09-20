#!/usr/bin/env python3
"""Run zero-API selector scaling diagnostics on the ACL 2027 nested libraries."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skillopt.evaluation.router_scaling import evaluate_library


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="artifacts/acl2027_scaling_v1/suite_manifest.json")
    parser.add_argument("--data", default="data/searchqa_split/test/items.json")
    parser.add_argument("--utility", default="artifacts/jos_experiment_v1/frozen_utility.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--methods", nargs="+",
        default=["tfidf", "bm25", "greedy-cold", "greedy-utility", "moar"],
    )
    parser.add_argument("--moar-pop-size", type=int, default=30)
    parser.add_argument("--moar-generations", type=int, default=15)
    parser.add_argument("--out", default="paper/acl2027/results/router_scaling_proxy_v1.json")
    parser.add_argument("--csv", default="paper/acl2027/results/router_scaling_proxy_v1.csv")
    return parser.parse_args()


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def main() -> int:
    args = parse_args()
    suite_path = _resolve(args.suite)
    suite_dir = suite_path.parent
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    data_path = _resolve(args.data)
    items = json.loads(data_path.read_text(encoding="utf-8"))
    if args.limit > 0:
        items = items[:args.limit]
    if not items or "question" not in items[0]:
        raise ValueError(f"Dataset must contain materialized question rows: {data_path}")

    summaries = []
    details = {}
    for level in suite["levels"]:
        manifest_path = suite_dir / level["manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        size = int(manifest["n_dynamic_rules"])
        print(f"Evaluating {size} rules...", flush=True)
        level_summaries, level_details = evaluate_library(
            library_path=suite_dir / level["library_path"],
            library_manifest=manifest,
            items=items,
            methods=args.methods,
            utility_path=_resolve(args.utility) if args.utility else None,
            top_k=args.top_k,
            budget=args.budget,
            seed=args.seed,
            moar_pop_size=args.moar_pop_size,
            moar_generations=args.moar_generations,
        )
        summaries.extend(level_summaries)
        details[str(size)] = level_details
        for row in level_summaries:
            print(
                f"  {row['method']:<15} latency={row['selection_ms_mean']:.2f}ms "
                f"tokens={row['avg_selected_tokens']:.1f} "
                f"base_proxy={row['base_selection_precision_proxy']:.3f}",
                flush=True,
            )

    payload = {
        "schema_version": 1,
        "scope": "selector-only offline proxy; no LLM calls and no task-accuracy claim",
        "suite_path": suite_path.relative_to(PROJECT_ROOT).as_posix(),
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "data_path": data_path.relative_to(PROJECT_ROOT).as_posix(),
        "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "utility_path": _resolve(args.utility).relative_to(PROJECT_ROOT).as_posix() if args.utility else "",
        "n_queries": len(items),
        "top_k": args.top_k,
        "budget": args.budget,
        "seed": args.seed,
        "moar_pop_size": args.moar_pop_size,
        "moar_generations": args.moar_generations,
        "methods": args.methods,
        "summaries": summaries,
        "per_query": details,
    }
    out_path = _resolve(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_path = _resolve(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print(f"JSON: {out_path}")
    print(f"CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
