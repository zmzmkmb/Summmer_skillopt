"""Audit and aggregate immutable experiment artifacts.

Declared seeds are metadata, not proof of independent execution. Every run is
fingerprinted from per-example outputs so copied runs cannot silently enter a
paper table.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


FORMAL_METHODS = {"Core Only", "TF-IDF Top-5", "MOAR"}
BASELINE_METHOD_NAMES = {
    "bm25": "BM25",
    "greedy-cold": "Greedy-Cold",
    "greedy-util": "Greedy-Utility",
    "greedy-utility": "Greedy-Utility",
}


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    path: str = ""


@dataclass
class RunRecord:
    model: str
    seed: int
    path: str
    file_sha256: str
    result_fingerprint: str
    methods: dict[str, dict[str, float | int]]


@dataclass
class BaselineRunRecord:
    condition: str
    model: str
    method: str
    seed: int
    path: str
    file_sha256: str
    result_fingerprint: str
    summary: dict[str, float | int]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _canonical_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": str(item.get("sample_id", "")),
        "hard": item.get("hard"),
        "predicted": item.get("predicted", ""),
        "selected_indices": list(
            item.get("selected_rule_ids", item.get("selected_indices", []))
        ),
    }


def _canonical_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for method, result in sorted(data.get("results", {}).items()):
        rows = [_canonical_item(item) for item in result.get("per_item", [])]
        rows.sort(key=lambda row: row["sample_id"])
        canonical.append({"method": method, "rows": rows})
    return canonical


def result_fingerprint(data: dict[str, Any]) -> str:
    """Hash formal outputs while intentionally excluding seed/file metadata."""
    payload = json.dumps(
        _canonical_results(data), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def baseline_result_fingerprint(data: dict[str, Any]) -> str:
    """Hash a single-method baseline run from its per-question outputs."""
    rows = [_canonical_item(item) for item in data.get("per_question", [])]
    rows.sort(key=lambda row: row["sample_id"])
    payload = json.dumps(
        {"method": normalize_baseline_method(str(data.get("method", ""))), "rows": rows},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def normalize_baseline_method(method: str) -> str:
    key = method.strip().lower().replace("_", "-")
    return BASELINE_METHOD_NAMES.get(key, method.strip())


def _method_summary(items: list[dict[str, Any]]) -> dict[str, float | int]:
    hard = [int(item["hard"]) for item in items if item.get("hard") is not None]
    rules = [float(item.get("n_rules", len(item.get("selected_indices", [])))) for item in items]
    tokens = [float(item.get("selected_tokens", 0)) for item in items]
    return {
        "n_items": len(items),
        "n_scored": len(hard),
        "accuracy": sum(hard) / len(hard) if hard else math.nan,
        "avg_rules": sum(rules) / len(rules) if rules else 0.0,
        "avg_selected_tokens": sum(tokens) / len(tokens) if tokens else 0.0,
        "api_failures": sum(
            1 for item in items
            if item.get("status") == "api_error" or item.get("predicted", "") == ""
        ),
        "budget_violations": sum(1 for item in items if item.get("budget_violated", False)),
    }


def _inspect_items(
    items: Any,
    *,
    path: Path,
    method: str,
    budget: Any,
    expected_items: int | None,
) -> tuple[dict[str, float | int] | None, list[AuditIssue]]:
    issues: list[AuditIssue] = []
    if not isinstance(items, list) or not items:
        issues.append(AuditIssue(
            "error", "missing_items", f"Method {method!r} has no per-example rows.", str(path),
        ))
        return None, issues
    if expected_items is not None and len(items) != expected_items:
        issues.append(AuditIssue(
            "error", "item_count_mismatch",
            f"Method {method!r} has {len(items)} items; expected {expected_items}.", str(path),
        ))

    sample_ids = [str(item.get("sample_id", "")) for item in items]
    missing_indices = sum(1 for item in items if "selected_indices" not in item)
    if missing_indices:
        issues.append(AuditIssue(
            "error", "missing_selected_indices",
            f"Method {method!r} has {missing_indices} rows without selected_indices.", str(path),
        ))
    missing_ids = sum(1 for sample_id in sample_ids if not sample_id)
    if missing_ids:
        issues.append(AuditIssue(
            "error", "missing_sample_id",
            f"Method {method!r} has {missing_ids} rows without sample_id.", str(path),
        ))
    duplicates = len(sample_ids) - len(set(sample_ids))
    if duplicates:
        issues.append(AuditIssue(
            "error", "duplicate_sample_id",
            f"Method {method!r} has {duplicates} duplicate sample_id rows.", str(path),
        ))

    empty = sum(1 for item in items if item.get("predicted", "") == "")
    if empty == len(items):
        issues.append(AuditIssue(
            "error", "all_predictions_empty",
            f"Method {method!r} has no usable predictions.", str(path),
        ))
    elif empty:
        issues.append(AuditIssue(
            "warning", "partial_api_failures",
            f"Method {method!r} has {empty}/{len(items)} empty predictions.", str(path),
        ))

    if isinstance(budget, (int, float)):
        mismatches = 0
        for item in items:
            if "selected_tokens" not in item or "budget_violated" not in item:
                continue
            computed = float(item["selected_tokens"]) > float(budget)
            if bool(item["budget_violated"]) != computed:
                mismatches += 1
        if mismatches:
            issues.append(AuditIssue(
                "error", "budget_flag_mismatch",
                f"Method {method!r} has {mismatches} inconsistent budget flags.", str(path),
            ))
    return _method_summary(items), issues


def inspect_formal_run(
    path: str | Path,
    *,
    expected_seed: int | None = None,
    expected_model: str | None = None,
    expected_items: int | None = None,
) -> tuple[RunRecord | None, list[AuditIssue]]:
    path = Path(path)
    issues: list[AuditIssue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [AuditIssue("error", "invalid_json", str(exc), str(path))]

    seed = data.get("seed")
    model = str(data.get("target_model", ""))
    if not isinstance(seed, int):
        issues.append(AuditIssue("error", "missing_seed", "Run has no integer seed.", str(path)))
        seed = -1
    if expected_seed is not None and seed != expected_seed:
        issues.append(AuditIssue(
            "error", "seed_mismatch",
            f"Manifest seed {expected_seed} does not match file seed {seed}.", str(path),
        ))
    if expected_model and model != expected_model:
        issues.append(AuditIssue(
            "error", "model_mismatch",
            f"Manifest model {expected_model!r} does not match file model {model!r}.", str(path),
        ))

    results = data.get("results")
    if not isinstance(results, dict) or not results:
        issues.append(AuditIssue("error", "missing_results", "Run has no results mapping.", str(path)))
        return None, issues

    summaries: dict[str, dict[str, float | int]] = {}
    for method, result in results.items():
        items = result.get("per_item", []) if isinstance(result, dict) else []
        summary, item_issues = _inspect_items(
            items, path=path, method=method, budget=data.get("budget"),
            expected_items=expected_items,
        )
        issues.extend(item_issues)
        if summary is not None:
            summaries[method] = summary

    record = RunRecord(
        model=model,
        seed=int(seed),
        path=str(path),
        file_sha256=file_sha256(path),
        result_fingerprint=result_fingerprint(data),
        methods=summaries,
    )
    return record, issues


def inspect_baseline_run(
    path: str | Path,
    *,
    expected_seed: int,
    expected_model: str,
    expected_method: str,
    condition: str,
    expected_items: int | None = None,
    seed_source: str | None = None,
) -> tuple[BaselineRunRecord | None, list[AuditIssue]]:
    path = Path(path)
    issues: list[AuditIssue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [AuditIssue("error", "invalid_json", str(exc), str(path))]

    model = str(data.get("target_model", ""))
    method = normalize_baseline_method(str(data.get("method", "")))
    if model != expected_model:
        issues.append(AuditIssue(
            "error", "model_mismatch",
            f"Manifest model {expected_model!r} does not match file model {model!r}.", str(path),
        ))
    if method != expected_method:
        issues.append(AuditIssue(
            "error", "method_mismatch",
            f"Manifest method {expected_method!r} does not match file method {method!r}.", str(path),
        ))
    embedded_seed = data.get("seed")
    if embedded_seed is None:
        if seed_source != "manifest":
            issues.append(AuditIssue(
                "warning", "seed_only_in_manifest",
                f"Historical baseline has no embedded seed; using manifest seed {expected_seed}.", str(path),
            ))
    elif embedded_seed != expected_seed:
        issues.append(AuditIssue(
            "error", "seed_mismatch",
            f"Manifest seed {expected_seed} does not match file seed {embedded_seed}.", str(path),
        ))

    items = data.get("per_question")
    summary, item_issues = _inspect_items(
        items, path=path, method=method, budget=data.get("budget"),
        expected_items=expected_items,
    )
    issues.extend(item_issues)
    if summary is None:
        return None, issues
    declared_n = data.get("n")
    if isinstance(declared_n, int) and declared_n != summary["n_items"]:
        issues.append(AuditIssue(
            "error", "declared_item_count_mismatch",
            f"File declares n={declared_n}, but contains {summary['n_items']} rows.", str(path),
        ))
    declared_acc = data.get("acc")
    if isinstance(declared_acc, (int, float)) and not math.isclose(
        float(declared_acc), float(summary["accuracy"]), abs_tol=1e-12
    ):
        issues.append(AuditIssue(
            "error", "declared_accuracy_mismatch",
            f"File declares acc={declared_acc}, but per-example accuracy is {summary['accuracy']}.", str(path),
        ))

    return BaselineRunRecord(
        condition=condition,
        model=model,
        method=method,
        seed=expected_seed,
        path=str(path),
        file_sha256=file_sha256(path),
        result_fingerprint=baseline_result_fingerprint(data),
        summary=summary,
    ), issues


def _model_name(manifest_value: str) -> str:
    return manifest_value.split(" (", 1)[0].strip()


def _formal_specs(manifest: dict[str, Any]) -> Iterable[tuple[str, int, str, str]]:
    models = manifest.get("models", {})
    for key, relative_path in manifest.get("files", {}).items():
        match = re.fullmatch(r"(target[SL])_seed(\d+)", key)
        if not match:
            continue
        target_key, seed_text = match.groups()
        yield target_key, int(seed_text), _model_name(str(models.get(target_key, ""))), relative_path


def _baseline_specs(manifest: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for spec in manifest.get("baseline_runs", []):
        yield spec


def _declared_paths(manifest: dict[str, Any]) -> set[str]:
    paths = {str(value) for value in manifest.get("files", {}).values() if str(value).endswith(".json")}
    for section in ("baseline_runs", "auxiliary_formal_runs"):
        for spec in manifest.get(section, []):
            if spec.get("path"):
                paths.add(str(spec["path"]))
    return paths


def _audited_rows(records: list[RunRecord], excluded_paths: set[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[RunRecord]] = {}
    for record in records:
        if record.path in excluded_paths:
            continue
        for method in record.methods:
            grouped.setdefault((record.model, method), []).append(record)

    rows: list[dict[str, Any]] = []
    for (model, method), method_records in sorted(grouped.items()):
        method_records.sort(key=lambda record: record.seed)
        stats = [record.methods[method] for record in method_records]
        accuracies = [float(stat["accuracy"]) for stat in stats]
        rows.append({
            "model": model,
            "method": method,
            "independent_runs": len(method_records),
            "seeds": "/".join(str(record.seed) for record in method_records),
            "accuracy_mean": statistics.mean(accuracies),
            "accuracy_std": statistics.stdev(accuracies) if len(accuracies) > 1 else 0.0,
            "items_per_run": "/".join(str(int(stat["n_items"])) for stat in stats),
            "avg_rules": statistics.mean(float(stat["avg_rules"]) for stat in stats),
            "avg_selected_tokens": statistics.mean(float(stat["avg_selected_tokens"]) for stat in stats),
            "api_failures": sum(int(stat["api_failures"]) for stat in stats),
            "budget_violations": sum(int(stat["budget_violations"]) for stat in stats),
        })
    return rows


def _audited_baseline_rows(
    records: list[BaselineRunRecord], excluded_paths: set[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[BaselineRunRecord]] = {}
    for record in records:
        if record.path in excluded_paths:
            continue
        grouped.setdefault((record.condition, record.model, record.method), []).append(record)

    rows: list[dict[str, Any]] = []
    for (condition, model, method), method_records in sorted(grouped.items()):
        method_records.sort(key=lambda record: record.seed)
        stats = [record.summary for record in method_records]
        accuracies = [float(stat["accuracy"]) for stat in stats]
        rows.append({
            "condition": condition,
            "model": model,
            "method": method,
            "independent_runs": len(method_records),
            "seeds": "/".join(str(record.seed) for record in method_records),
            "accuracy_mean": statistics.mean(accuracies),
            "accuracy_std": statistics.stdev(accuracies) if len(accuracies) > 1 else 0.0,
            "items_per_run": "/".join(str(int(stat["n_items"])) for stat in stats),
            "avg_rules": statistics.mean(float(stat["avg_rules"]) for stat in stats),
            "avg_selected_tokens": statistics.mean(float(stat["avg_selected_tokens"]) for stat in stats),
            "api_failures": sum(int(stat["api_failures"]) for stat in stats),
            "budget_violations": sum(int(stat["budget_violations"]) for stat in stats),
        })
    return rows


def audit_artifact_package(artifact_root: str | Path) -> dict[str, Any]:
    artifact_root = Path(artifact_root)
    manifest_path = artifact_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_items = int(manifest.get("dataset", {}).get("n_items", 0)) or None
    root_resolved = artifact_root.resolve()

    def portable_path(value: str) -> str:
        try:
            return str(Path(value).resolve().relative_to(root_resolved)).replace("\\", "/")
        except ValueError:
            return str(value)

    issues: list[AuditIssue] = []
    records: list[RunRecord] = []
    baseline_records: list[BaselineRunRecord] = []
    declared_relative_paths = _declared_paths(manifest)
    declared_result_paths = {str((artifact_root / path).resolve()) for path in declared_relative_paths}

    for relative_path in sorted(declared_relative_paths):
        path = artifact_root / relative_path
        if not path.exists():
            issues.append(AuditIssue(
                "error", "missing_manifest_file",
                f"Manifest references missing file {relative_path}.", str(path),
            ))

    for _target, seed, model, relative_path in _formal_specs(manifest):
        path = artifact_root / relative_path
        if not path.exists():
            continue
        record, run_issues = inspect_formal_run(
            path, expected_seed=seed, expected_model=model, expected_items=expected_items,
        )
        issues.extend(run_issues)
        if record is not None:
            records.append(record)

    for spec in _baseline_specs(manifest):
        relative_path = str(spec.get("path", ""))
        path = artifact_root / relative_path
        if not relative_path or not path.exists():
            continue
        record, run_issues = inspect_baseline_run(
            path,
            expected_seed=int(spec["seed"]),
            expected_model=str(spec["model"]),
            expected_method=str(spec["method"]),
            condition=str(spec.get("condition", "default")),
            expected_items=expected_items,
            seed_source=str(spec.get("seed_source", "")) or None,
        )
        issues.extend(run_issues)
        if record is not None:
            baseline_records.append(record)

    for path in artifact_root.rglob("*.json"):
        if path.name in {"run_manifest.json", "audit_report.json", "frozen_utility.json", "moar_utility.json"}:
            continue
        if "formal" in path.name and str(path.resolve()) not in declared_result_paths:
            issues.append(AuditIssue(
                "warning", "unmanifested_result_file",
                "Result file is present but is not declared in run_manifest.json.", str(path),
            ))

    formal_path_by_id = {
        key: str((artifact_root / relative_path).resolve())
        for key, relative_path in manifest.get("files", {}).items()
        if re.fullmatch(r"target[SL]_seed\d+", key)
    }
    records_by_path = {str(Path(record.path).resolve()): record for record in records}
    declared_excluded_paths: set[str] = set()
    for run_id, declaration in manifest.get("excluded_runs", {}).items():
        duplicate_of = str(declaration.get("duplicate_of", ""))
        run_path = formal_path_by_id.get(str(run_id))
        source_path = formal_path_by_id.get(duplicate_of)
        run_record = records_by_path.get(run_path or "")
        source_record = records_by_path.get(source_path or "")
        if run_record is None or source_record is None:
            issues.append(AuditIssue(
                "error", "invalid_excluded_run_declaration",
                f"Excluded run {run_id!r} or duplicate_of {duplicate_of!r} is not a canonical formal run.",
                run_path or str(manifest_path),
            ))
            continue
        if run_record.path == source_record.path or (
            run_record.model != source_record.model
            or run_record.result_fingerprint != source_record.result_fingerprint
        ):
            issues.append(AuditIssue(
                "error", "invalid_excluded_run_declaration",
                f"Excluded run {run_id!r} is not an output-identical copy of {duplicate_of!r}.",
                run_record.path,
            ))
            continue
        declared_excluded_paths.add(run_record.path)
        reason = str(declaration.get("reason", "")).strip()
        suffix = f" Reason: {reason}" if reason else ""
        issues.append(AuditIssue(
            "warning", "declared_duplicate_exclusion",
            f"Excluded {run_id!r} as an explicitly declared copy of {duplicate_of!r}.{suffix}",
            run_record.path,
        ))

    excluded_paths: set[str] = set(declared_excluded_paths)
    by_fingerprint: dict[tuple[str, str], list[RunRecord]] = {}
    for record in records:
        by_fingerprint.setdefault((record.model, record.result_fingerprint), []).append(record)
    for (_model, _fingerprint), duplicates in by_fingerprint.items():
        seeds = sorted({record.seed for record in duplicates})
        if len(seeds) <= 1:
            continue
        duplicates.sort(key=lambda record: record.seed)
        unresolved = [record for record in duplicates if record.path not in declared_excluded_paths]
        if len({record.seed for record in unresolved}) <= 1:
            continue
        for record in unresolved[1:]:
            excluded_paths.add(record.path)
        issues.append(AuditIssue(
            "error", "duplicate_run_content",
            "Runs declared with different seeds have identical per-example outputs without a complete "
            "manifest exclusion: "
            + ", ".join(
                f"seed={record.seed} ({portable_path(record.path)})" for record in duplicates
            ),
            unresolved[-1].path,
        ))

    excluded_baseline_paths: set[str] = set()
    baseline_by_fingerprint: dict[tuple[str, str, str, str], list[BaselineRunRecord]] = {}
    for record in baseline_records:
        key = (record.condition, record.model, record.method, record.result_fingerprint)
        baseline_by_fingerprint.setdefault(key, []).append(record)
    for (_condition, _model, _method, _fingerprint), duplicates in baseline_by_fingerprint.items():
        seeds = sorted({record.seed for record in duplicates})
        if len(seeds) <= 1:
            continue
        duplicates.sort(key=lambda record: record.seed)
        for record in duplicates[1:]:
            excluded_baseline_paths.add(record.path)
        issues.append(AuditIssue(
            "error", "duplicate_baseline_content",
            "Baseline runs declared with different seeds have identical per-example outputs: "
            + ", ".join(
                f"seed={record.seed} ({portable_path(record.path)})" for record in duplicates
            ),
            duplicates[-1].path,
        ))

    audited_rows = _audited_rows(records, excluded_paths)
    audited_baselines = _audited_baseline_rows(baseline_records, excluded_baseline_paths)
    trusted_counts: dict[str, int] = {}
    for record in records:
        if record.path not in excluded_paths:
            trusted_counts[record.model] = trusted_counts.get(record.model, 0) + 1

    aggregate_path = artifact_root / "aggregate_results.csv"
    if aggregate_path.exists():
        aggregate_policy = manifest.get("historical_outputs", {}).get(
            "aggregate_results.csv", {}
        )
        if aggregate_policy.get("status") == "superseded":
            replacements = ", ".join(aggregate_policy.get("replacements", []))
            replacement_note = f" Use {replacements}." if replacements else ""
            issues.append(AuditIssue(
                "warning", "historical_aggregate_ignored",
                "aggregate_results.csv is explicitly marked superseded and is excluded from "
                f"canonical evidence.{replacement_note}",
                str(aggregate_path),
            ))
        else:
            with aggregate_path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("method") not in FORMAL_METHODS:
                        continue
                    model = row.get("model", "")
                    try:
                        reported = int(row.get("n_seeds", "0"))
                    except ValueError:
                        continue
                    trusted = trusted_counts.get(model, 0)
                    if reported > trusted:
                        issues.append(AuditIssue(
                            "error", "aggregate_seed_overcount",
                            f"aggregate_results.csv reports {reported} seeds for {model}/{row.get('method')}, "
                            f"but only {trusted} independent manifested runs are available.",
                            str(aggregate_path),
                        ))

    issue_dicts = []
    for issue in issues:
        item = asdict(issue)
        if item["path"]:
            item["path"] = portable_path(item["path"])
        issue_dicts.append(item)

    run_dicts = []
    for record in records:
        item = asdict(record)
        item["path"] = portable_path(record.path)
        run_dicts.append(item)

    baseline_run_dicts = []
    for record in baseline_records:
        item = asdict(record)
        item["path"] = portable_path(record.path)
        baseline_run_dicts.append(item)

    return {
        "artifact_root": ".",
        "manifest": "run_manifest.json",
        "summary": {
            "records": len(records),
            "independent_records": len(records) - len(excluded_paths),
            "baseline_records": len(baseline_records),
            "independent_baseline_records": len(baseline_records) - len(excluded_baseline_paths),
            "errors": sum(issue.severity == "error" for issue in issues),
            "warnings": sum(issue.severity == "warning" for issue in issues),
            "resolved_historical_issues": sum(
                issue.code in {"declared_duplicate_exclusion", "historical_aggregate_ignored"}
                for issue in issues
            ),
            "independent_runs_by_model": trusted_counts,
        },
        "issues": issue_dicts,
        "runs": run_dicts,
        "baseline_runs": baseline_run_dicts,
        "excluded_duplicate_paths": sorted(portable_path(path) for path in excluded_paths),
        "excluded_duplicate_baseline_paths": sorted(
            portable_path(path) for path in excluded_baseline_paths
        ),
        "audited_results": audited_rows,
        "audited_baselines": audited_baselines,
    }


def _write_rows(rows: list[dict[str, Any]], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_audit_outputs(
    report: dict[str, Any],
    *,
    report_path: str | Path,
    csv_path: str | Path,
    baseline_csv_path: str | Path | None = None,
) -> None:
    report_path = Path(report_path)
    csv_path = Path(csv_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    result_fields = [
        "model", "method", "independent_runs", "seeds", "accuracy_mean",
        "accuracy_std", "items_per_run", "avg_rules", "avg_selected_tokens",
        "api_failures", "budget_violations",
    ]
    _write_rows(report["audited_results"], csv_path, result_fields)

    if baseline_csv_path is not None:
        baseline_fields = [
            "condition", "model", "method", "independent_runs", "seeds",
            "accuracy_mean", "accuracy_std", "items_per_run", "avg_rules",
            "avg_selected_tokens", "api_failures", "budget_violations",
        ]
        _write_rows(report["audited_baselines"], Path(baseline_csv_path), baseline_fields)
