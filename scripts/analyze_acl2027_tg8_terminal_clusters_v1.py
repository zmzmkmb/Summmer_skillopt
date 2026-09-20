"""Task-clustered primary-endpoint analysis of the audited TG8 run; no episodes."""
from __future__ import annotations

from collections import defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import audit_acl2027_tg8_manual_terminal_v1 as audit

OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg8_durable_v2/analysis_20260917_manual_v1"
METRICS = ("completion_by_step_50", "episode_two_cycle_incidence_by_step_50")
CONTRASTS = ("representation", "controller", "interaction")
CONDITIONS = audit.frozen.selector.CONDITIONS
SEED = 20260917


def contrasts(values):
    lexical, lexical_anti, structured, structured_anti = values
    return (
        ((structured - lexical) + (structured_anti - lexical_anti)) / 2,
        ((lexical_anti - lexical) + (structured_anti - structured)) / 2,
        (structured_anti - structured) - (lexical_anti - lexical),
    )


def percentile(values, probability):
    ordered = sorted(values)
    rank = (len(ordered) - 1) * probability
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (rank - lower) * (ordered[upper] - ordered[lower])


def bootstrap(task_vectors, resamples=10000, seed=SEED):
    rng = random.Random(seed)
    count = len(task_vectors)
    width = len(task_vectors[0])
    samples = [[] for _ in range(width)]
    for _ in range(resamples):
        chosen = [task_vectors[rng.randrange(count)] for _ in range(count)]
        for column in range(width):
            samples[column].append(sum(row[column] for row in chosen) / count)
    return [{
        "estimate": sum(row[column] for row in task_vectors) / count,
        "ci95_percentile": [percentile(samples[column], 0.025),
                            percentile(samples[column], 0.975)],
    } for column in range(width)]


def main():
    audit.require(not OUTPUT.exists(), "analysis output exists; overwrite forbidden")
    audit_path = audit.DEFAULT_OUTPUT / "audit.json"
    manifest_path = audit.DEFAULT_OUTPUT / "completion_manifest.json"
    checked = audit.frozen.read_json(audit_path)
    manifest = audit.frozen.read_json(manifest_path)
    audit.require(manifest["audit_sha256"] == audit.digest(audit_path), "audit hash")
    audit.require(checked["status"] == "passed" and checked["full_selector_recomputed"],
                  "full terminal audit required")
    paths = [audit_path, manifest_path, Path(__file__),
             ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_preflight_v4.json"]
    rows = []
    for ordinal in range(360):
        relative = checked["run_directory"] + f"/rows/{ordinal:04d}.json"
        path = ROOT / relative
        audit.require(audit.digest(path) == checked["immutable_input_sha256"][relative],
                      f"audited row changed: {ordinal}")
        paths.append(path)
        rows.append(audit.frozen.read_json(path))
    hashes = {path.relative_to(ROOT).as_posix(): audit.digest(path) for path in paths}
    groups = defaultdict(list)
    for row in rows:
        groups[(row["task_identity"], row["condition"])].append(row)
    tasks = sorted({row["task_identity"] for row in rows},
                   key=lambda task: next(r["task_ordinal"] for r in rows
                                         if r["task_identity"] == task))
    audit.require(len(tasks) == 30 and len(groups) == 120, "cluster cardinality")
    identical = 0
    for group in groups.values():
        audit.require(len(group) == 3 and {r["replicate_index"] for r in group} == {0, 1, 2},
                      "replicate structure")
        signatures = {
            json.dumps([(t["runtime_inputs"], t["terminal_action_decision"],
                         t["success_after_step"]) for t in row["transitions"]],
                       sort_keys=True, ensure_ascii=True)
            for row in group
        }
        identical += len(signatures) == 1
    cluster_records, vectors = [], []
    for task in tasks:
        record, vector = {"task_identity": task}, []
        exemplar = groups[(task, CONDITIONS[0])][0]
        record.update(task_family=exemplar["task_family"], split=exemplar["split"])
        for metric in METRICS:
            means = [sum(float(r["metrics"][metric]) for r in groups[(task, condition)]) / 3
                     for condition in CONDITIONS]
            record.update({f"{metric}:{c}": value for c, value in zip(CONDITIONS, means)})
            vector.extend(contrasts(means))
        cluster_records.append(record)
        vectors.append(vector)
    estimates = bootstrap(vectors)
    results = {}
    for metric_index, metric in enumerate(METRICS):
        results[metric] = dict(zip(CONTRASTS, estimates[metric_index * 3:metric_index * 3 + 3]))
    for path, expected in hashes.items():
        audit.require(audit.digest(ROOT / path) == expected, "analysis input changed")
    OUTPUT.mkdir(exist_ok=False)
    with (OUTPUT / "task_cluster_inputs.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cluster_records[0]))
        writer.writeheader()
        writer.writerows(cluster_records)
    payload = {
        "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "Paired task-cluster bootstrap; retain all four conditions and three replicates",
        "task_count": 30, "rows": 360, "resamples": 10000,
        "computational_seed": SEED,
        "seed_provenance": "Chosen after execution for analysis reproducibility; not a preregistered experimental seed",
        "percentile_rule": "Linear interpolation at (B-1)*p; p=0.025 and 0.975",
        "condition_order": CONDITIONS, "results": results,
        "identical_three_replicate_trajectory_groups": identical,
        "task_condition_groups": len(groups),
        "interval_scope": "Six marginal 95% intervals, not simultaneous; no multiplicity correction",
        "claim_scope": "Frozen development pilot signals only; no confirmatory or cross-domain claim",
        "horizon": "Observed primary step-50 endpoints only; no 75-step sensitivity inference",
        "prior_partial_attempts_pooled": False, "new_episodes": 0, "new_actions": 0,
        "immutable_input_sha256": hashes,
        "task_cluster_inputs_sha256": audit.digest(OUTPUT / "task_cluster_inputs.csv"),
    }
    audit.durable.publish(OUTPUT / "analysis.json", payload)
    audit.durable.publish(OUTPUT / "completion_manifest.json", {
        "status": "complete", "analysis_sha256": audit.digest(OUTPUT / "analysis.json"),
        "script_sha256": audit.digest(Path(__file__)),
        "task_cluster_inputs_sha256": payload["task_cluster_inputs_sha256"],
    })
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
