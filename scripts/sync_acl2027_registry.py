#!/usr/bin/env python3
"""Generate the ACL 2027 immutable-run registry from the JoS artifact manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skillopt.evaluation.artifact_audit import (
    audit_artifact_package,
    file_sha256,
    inspect_formal_run,
)

FIELDS = [
    "run_id", "status", "commit", "config_sha256", "data_sha256", "skill_sha256",
    "task", "domain", "model_family", "model", "method", "library_size",
    "token_budget", "top_k", "declared_seed", "replicate_id", "started_at",
    "finished_at", "result_path", "result_sha256", "result_fingerprint",
    "independent", "notes",
]


def _config_sha256(data: dict[str, Any]) -> str:
    excluded = {
        "results", "per_question", "timestamp", "run_id", "result_fingerprint",
        "source_result", "source_sha256", "accuracy_recomputed", "skill",
        "n", "acc", "avg_rules", "avg_sel_ms", "sel_ms_median",
        "sel_ms_p95", "sel_ms_p99", "sel_ms_max", "api_failures",
    }
    config = {key: value for key, value in data.items() if key not in excluded}
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _common_row(
    *, manifest: dict[str, Any], data: dict[str, Any], path: Path, run_id: str,
    status: str, method: str, seed: int, fingerprint: str, independent: bool,
    notes: str,
) -> dict[str, Any]:
    timestamp = str(data.get("timestamp", ""))
    return {
        "run_id": run_id,
        "status": status,
        "commit": str(data.get("commit", manifest.get("commit", ""))),
        "config_sha256": _config_sha256(data),
        "data_sha256": str(data.get("dataset_sha256", manifest["dataset"]["sha256"])),
        "skill_sha256": str(data.get("skill_sha256", manifest["skill"]["sha256"])),
        "task": "SearchQA",
        "domain": "open-domain QA",
        "model_family": "Qwen",
        "model": str(data.get("target_model", "")),
        "method": method,
        "library_size": int(manifest["skill"]["n_dynamic"]),
        "token_budget": int(data.get("budget", manifest["budget"])),
        "top_k": int(data.get("top_k", manifest["top_k"])),
        "declared_seed": seed,
        "replicate_id": f"seed{seed}",
        "started_at": timestamp,
        "finished_at": timestamp,
        "result_path": path.relative_to(PROJECT_ROOT).as_posix(),
        "result_sha256": file_sha256(path),
        "result_fingerprint": fingerprint,
        "independent": str(bool(independent)).lower(),
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        default=str(PROJECT_ROOT / "artifacts" / "jos_experiment_v1"),
    )
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "paper" / "acl2027" / "experiment_registry.csv"),
    )
    args = parser.parse_args()
    artifact_root = Path(args.artifact_root).resolve()
    manifest = json.loads((artifact_root / "run_manifest.json").read_text(encoding="utf-8"))
    report = audit_artifact_package(artifact_root)
    excluded_formal = set(report["excluded_duplicate_paths"])
    excluded_baselines = set(report["excluded_duplicate_baseline_paths"])
    file_to_id = {str(path): key for key, path in manifest.get("files", {}).items()}

    rows: list[dict[str, Any]] = []
    for record in report["runs"]:
        rel = record["path"]
        path = artifact_root / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        independent = rel not in excluded_formal
        rows.append(_common_row(
            manifest=manifest, data=data, path=path,
            run_id=file_to_id.get(rel, path.stem),
            status="historical-audited" if independent else "historical-excluded-copy",
            method="Core Only+TF-IDF Top-5+MOAR", seed=int(record["seed"]),
            fingerprint=str(record["result_fingerprint"]), independent=independent,
            notes="canonical formal artifact" if independent else "copied output; excluded from statistics",
        ))

    baseline_specs = {spec["path"]: spec for spec in manifest.get("baseline_runs", [])}
    for record in report["baseline_runs"]:
        rel = record["path"]
        spec = baseline_specs[rel]
        path = artifact_root / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        independent = rel not in excluded_baselines
        rows.append(_common_row(
            manifest=manifest, data=data, path=path, run_id=str(spec["id"]),
            status="historical-audited" if independent else "historical-excluded-copy",
            method=str(record["method"]), seed=int(record["seed"]),
            fingerprint=str(record["result_fingerprint"]), independent=independent,
            notes=f"condition={record['condition']}; seed recovered from manifest",
        ))

    for spec in manifest.get("auxiliary_formal_runs", []):
        path = artifact_root / spec["path"]
        record, issues = inspect_formal_run(
            path, expected_seed=int(spec["seed"]), expected_model=str(spec["model"]),
            expected_items=int(manifest["dataset"]["n_items"]),
        )
        if record is None or any(issue.severity == "error" for issue in issues):
            raise RuntimeError(f"Auxiliary run failed audit: {spec['path']}")
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append(_common_row(
            manifest=manifest, data=data, path=path, run_id=str(spec["id"]),
            status="historical-auxiliary", method="Core Only+TF-IDF Top-5+MOAR",
            seed=int(spec["seed"]), fingerprint=record.result_fingerprint,
            independent=True, notes=f"condition={spec['condition']}; excluded from canonical table",
        ))

    rows.sort(key=lambda row: (row["status"], row["model"], row["method"], int(row["declared_seed"])))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} immutable runs to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
