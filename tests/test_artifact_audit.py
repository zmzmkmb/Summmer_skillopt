"""Tests for immutable experiment artifact auditing."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from skillopt.evaluation.artifact_audit import (
    audit_artifact_package,
    baseline_result_fingerprint,
    inspect_formal_run,
    result_fingerprint,
)

PROJECT = Path(__file__).resolve().parents[1]


def _formal(seed: int, *, prediction: str = "A") -> dict:
    item = {
        "sample_id": "q1",
        "hard": 1,
        "predicted": prediction,
        "selected_indices": [0],
        "n_rules": 1,
        "selected_tokens": 10,
        "budget_violated": False,
    }
    return {
        "seed": seed,
        "target_model": "model-x",
        "budget": 20,
        "results": {"MOAR": {"per_item": [item]}},
    }


def test_result_fingerprint_ignores_declared_seed():
    assert result_fingerprint(_formal(42)) == result_fingerprint(_formal(44))
    assert result_fingerprint(_formal(42)) != result_fingerprint(_formal(44, prediction="B"))


def test_inspect_formal_run_detects_duplicate_sample_ids(tmp_path: Path):
    data = _formal(42)
    data["results"]["MOAR"]["per_item"].append(
        dict(data["results"]["MOAR"]["per_item"][0])
    )
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    _record, issues = inspect_formal_run(path, expected_items=2)
    assert "duplicate_sample_id" in {issue.code for issue in issues}


def test_package_audit_excludes_copied_seed(tmp_path: Path):
    root = tmp_path / "artifact"
    (root / "runs").mkdir(parents=True)
    for seed in (42, 43, 44):
        prediction = "B" if seed == 43 else "A"
        (root / "runs" / f"seed{seed}.json").write_text(
            json.dumps(_formal(seed, prediction=prediction)), encoding="utf-8"
        )
    manifest = {
        "models": {"targetS": "model-x"},
        "dataset": {"n_items": 1},
        "files": {
            "targetS_seed42": "runs/seed42.json",
            "targetS_seed43": "runs/seed43.json",
            "targetS_seed44": "runs/seed44.json",
        },
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = audit_artifact_package(root)
    assert report["summary"]["independent_runs_by_model"] == {"model-x": 2}
    assert "duplicate_run_content" in {issue["code"] for issue in report["issues"]}
    row = report["audited_results"][0]
    assert row["independent_runs"] == 2
    assert row["seeds"] == "42/43"


def test_declared_duplicate_is_resolved_but_excluded(tmp_path: Path):
    root = tmp_path / "artifact"
    (root / "runs").mkdir(parents=True)
    for seed in (42, 44):
        (root / "runs" / f"seed{seed}.json").write_text(
            json.dumps(_formal(seed)), encoding="utf-8"
        )
    manifest = {
        "models": {"targetL": "model-x"},
        "dataset": {"n_items": 1},
        "files": {
            "targetL_seed42": "runs/seed42.json",
            "targetL_seed44": "runs/seed44.json",
        },
        "excluded_runs": {
            "targetL_seed44": {
                "duplicate_of": "targetL_seed42",
                "reason": "synthetic copied output",
            }
        },
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = audit_artifact_package(root)

    assert report["summary"]["errors"] == 0
    assert report["summary"]["independent_runs_by_model"] == {"model-x": 1}
    assert report["excluded_duplicate_paths"] == ["runs/seed44.json"]
    assert "declared_duplicate_exclusion" in {
        issue["code"] for issue in report["issues"]
    }


def test_current_artifact_audit_resolves_declared_historical_issues():
    report = audit_artifact_package(PROJECT / "artifacts" / "jos_experiment_v1")
    counts = report["summary"]["independent_runs_by_model"]
    assert counts["qwen-flash"] == 3
    assert counts["qwen3.6-flash"] == 2
    assert report["summary"]["errors"] == 0
    assert report["summary"]["resolved_historical_issues"] == 2
    codes = {issue["code"] for issue in report["issues"]}
    assert "declared_duplicate_exclusion" in codes
    assert "historical_aggregate_ignored" in codes
    assert "duplicate_run_content" not in codes
    assert "aggregate_seed_overcount" not in codes
    assert "seed_only_in_manifest" not in codes



def _baseline(*, prediction: str = "A") -> dict:
    return {
        "method": "bm25",
        "target_model": "model-x",
        "n": 1,
        "acc": 1.0,
        "budget": 20,
        "per_question": [{
            "sample_id": "q1",
            "hard": 1,
            "predicted": prediction,
            "selected_indices": [0],
            "n_rules": 1,
            "selected_tokens": 10,
            "budget_violated": False,
        }],
    }


def test_baseline_fingerprint_uses_per_question_outputs():
    assert baseline_result_fingerprint(_baseline()) != baseline_result_fingerprint(
        _baseline(prediction="B")
    )


def test_package_audit_excludes_copied_baseline(tmp_path: Path):
    root = tmp_path / "artifact"
    (root / "runs").mkdir(parents=True)
    for seed in (42, 43):
        (root / "runs" / f"bm25_{seed}.json").write_text(
            json.dumps(_baseline()), encoding="utf-8"
        )
    manifest = {
        "dataset": {"n_items": 1},
        "files": {},
        "baseline_runs": [
            {
                "id": f"bm25_{seed}",
                "condition": "test",
                "model": "model-x",
                "method": "BM25",
                "seed": seed,
                "path": f"runs/bm25_{seed}.json",
            }
            for seed in (42, 43)
        ],
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = audit_artifact_package(root)
    assert report["summary"]["baseline_records"] == 2
    assert report["summary"]["independent_baseline_records"] == 1
    assert "duplicate_baseline_content" in {issue["code"] for issue in report["issues"]}
    assert report["audited_baselines"][0]["independent_runs"] == 1


def test_current_artifact_has_complete_target_s_baselines():
    report = audit_artifact_package(PROJECT / "artifacts" / "jos_experiment_v1")
    rows = {
        (row["condition"], row["method"]): row
        for row in report["audited_baselines"]
    }
    for method in ("BM25", "Greedy-Cold", "Greedy-Utility"):
        assert rows[("targetS", method)]["independent_runs"] == 3
        assert rows[("targetS", method)]["seeds"] == "42/43/44"
    assert "unmanifested_result_file" not in {issue["code"] for issue in report["issues"]}
