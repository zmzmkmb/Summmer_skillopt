#!/usr/bin/env python3
"""Analyze a completed TG9 2x2 run at the task-identity level."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


CONDITIONS = (
    "type_level_current_coverage",
    "instance_bound_current_coverage",
    "type_level_open_close_coverage",
    "instance_bound_open_close_coverage",
)
CONTRASTS = ("object_binding", "open_close_coverage", "interaction")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * probability
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (rank - lower) * (ordered[upper] - ordered[lower])


def effects(values: list[float]) -> tuple[float, float, float]:
    y00, y10, y01, y11 = values
    return (
        ((y10 - y00) + (y11 - y01)) / 2,
        ((y01 - y00) + (y11 - y10)) / 2,
        y11 - y10 - y01 + y00,
    )


def paired_bootstrap(
    vectors: list[list[float]],
    resamples: int = 10_000,
    seed: int = 20260918,
) -> list[dict[str, Any]]:
    if not vectors:
        raise ValueError("bootstrap requires task vectors")
    rng = random.Random(seed)
    samples = [[] for _ in range(3)]
    for _ in range(resamples):
        chosen = [vectors[rng.randrange(len(vectors))] for _ in vectors]
        estimates = effects([
            sum(row[column] for row in chosen) / len(chosen)
            for column in range(4)
        ])
        for index, estimate in enumerate(estimates):
            samples[index].append(estimate)
    point = effects([
        sum(row[column] for row in vectors) / len(vectors)
        for column in range(4)
    ])
    return [
        {
            "estimate": point[index],
            "ci95_percentile": [
                percentile(samples[index], 0.025),
                percentile(samples[index], 0.975),
            ],
        }
        for index in range(3)
    ]


def cluster_bootstrap(
    task_rows: list[dict[str, Any]],
    cluster_key: str,
    resamples: int = 10_000,
    seed: int = 20260918,
) -> list[dict[str, Any]]:
    groups: dict[str, list[list[float]]] = defaultdict(list)
    for row in task_rows:
        groups[str(row[cluster_key])].append(list(row["condition_vector"]))
    clusters = sorted(groups)
    if not clusters:
        raise ValueError("cluster bootstrap requires clusters")
    rng = random.Random(seed)
    samples = [[] for _ in range(3)]
    for _ in range(resamples):
        chosen_clusters = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        chosen = [vector for key in chosen_clusters for vector in groups[key]]
        estimate = effects([
            sum(row[column] for row in chosen) / len(chosen)
            for column in range(4)
        ])
        for index, value in enumerate(estimate):
            samples[index].append(value)
    vectors = [list(row["condition_vector"]) for row in task_rows]
    point = effects([
        sum(row[column] for row in vectors) / len(vectors)
        for column in range(4)
    ])
    return [
        {
            "estimate": point[index],
            "ci95_percentile": [
                percentile(samples[index], 0.025),
                percentile(samples[index], 0.975),
            ],
            "cluster_count": len(clusters),
        }
        for index in range(3)
    ]


def exact_sign_test(values: list[float]) -> dict[str, Any]:
    nonzero = [value for value in values if value != 0]
    positives = sum(value > 0 for value in nonzero)
    n = len(nonzero)
    if n == 0:
        return {"nonzero_tasks": 0, "positive_tasks": 0, "p_two_sided": 1.0}
    tail = sum(math.comb(n, k) for k in range(positives, n + 1)) / (2**n)
    opposite = sum(math.comb(n, k) for k in range(0, positives + 1)) / (2**n)
    return {
        "nonzero_tasks": n,
        "positive_tasks": positives,
        "p_two_sided": min(1.0, 2 * min(tail, opposite)),
    }


def exact_sign_flip(values: list[float]) -> float:
    nonzero = [value for value in values if value != 0]
    if not nonzero:
        return 1.0
    observed = abs(sum(nonzero) / len(nonzero))
    exceed = 0
    total = 2 ** len(nonzero)
    for signs in itertools.product((-1, 1), repeat=len(nonzero)):
        candidate = abs(sum(sign * value for sign, value in zip(signs, nonzero)) / len(nonzero))
        exceed += candidate >= observed - 1e-12
    return exceed / total


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues, key=pvalues.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * pvalues[key]))
        adjusted[key] = running
    return adjusted


def task_level_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    if result.get("hard_invariant_violation") is not None:
        raise ValueError("factorial run is invalid after a hard invariant violation")
    rows = list(result.get("rows") or [])
    if len(rows) != 180:
        raise ValueError("completed TG9 result must contain exactly 180 rows")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("hard_invariant_violation") is not None:
            raise ValueError("row contains a hard invariant violation")
        if row.get("condition") not in CONDITIONS:
            raise ValueError("unknown TG9 condition")
        groups[(str(row["task_identity"]), str(row["condition"]))].append(row)
    tasks = sorted({key[0] for key in groups})
    if len(tasks) != 15 or len(groups) != 60:
        raise ValueError("TG9 analysis requires 15 tasks x 4 conditions")
    output = []
    for task in tasks:
        vectors = []
        signatures = {}
        exemplar = groups[(task, CONDITIONS[0])][0]
        for condition in CONDITIONS:
            replicates = groups[(task, condition)]
            if len(replicates) != 3 or {row.get("replicate_index") for row in replicates} != {0, 1, 2}:
                raise ValueError("each task-condition cell requires three replicates")
            values = [float(bool(row.get("success"))) for row in replicates]
            vectors.append(sum(values) / len(values))
            signatures[condition] = len({
                json.dumps(row.get("transitions", []), sort_keys=True, ensure_ascii=True)
                for row in replicates
            })
        output.append({
            "task_identity": task,
            "template_key": str(exemplar["template_key"]),
            "split": str(exemplar["split"]),
            "condition_vector": vectors,
            "replicate_trajectory_signature_counts": signatures,
        })
    return output


def analyze(result: dict[str, Any], resamples: int = 10_000) -> dict[str, Any]:
    tasks = task_level_rows(result)
    vectors = [list(row["condition_vector"]) for row in tasks]
    task_ci = paired_bootstrap(vectors, resamples=resamples)
    template_ci = cluster_bootstrap(tasks, "template_key", resamples=resamples, seed=20260919)
    per_task_effects = [effects(vector) for vector in vectors]
    tests = {}
    raw_p = {}
    for index, contrast in enumerate(CONTRASTS):
        values = [row[index] for row in per_task_effects]
        sign = exact_sign_test(values)
        flip = exact_sign_flip(values)
        tests[contrast] = {"task_effects": values, "exact_sign_test": sign, "exact_sign_flip_p": flip}
        raw_p[contrast] = flip
    adjusted = holm(raw_p)
    for contrast in CONTRASTS:
        tests[contrast]["holm_adjusted_sign_flip_p"] = adjusted[contrast]
    return {
        "schema_version": "tg9-factorial-analysis-v1",
        "status": "complete",
        "independent_unit": "task_identity",
        "task_count": len(tasks),
        "row_count": 180,
        "condition_order": list(CONDITIONS),
        "primary_endpoint": "completion_by_step_50",
        "step_75_endpoint_status": result.get(
            "step_75_endpoint_status",
            "unavailable_unless_readiness_proved_environment_support",
        ),
        "bootstrap_resamples": resamples,
        "task_cluster_results": dict(zip(CONTRASTS, task_ci)),
        "template_cluster_sensitivity": dict(zip(CONTRASTS, template_ci)),
        "paired_evidence_tests": tests,
        "holm_family": list(CONTRASTS),
        "task_level_rows": tasks,
        "claim_scope": "internal mechanism validation; not blind confirmatory",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=10_000)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    result = json.loads(args.result.read_text(encoding="utf-8"))
    payload = analyze(result, args.resamples)
    payload["result_sha256"] = sha256(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["task_cluster_results"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
