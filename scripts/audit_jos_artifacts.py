#!/usr/bin/env python3
"""Audit the JoS formal artifact package without calling any model API."""
from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skillopt.evaluation.artifact_audit import audit_artifact_package, write_audit_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        default=os.path.join(PROJECT_ROOT, "artifacts", "jos_experiment_v1"),
    )
    parser.add_argument("--report", default="")
    parser.add_argument("--csv", default="")
    parser.add_argument("--baseline-csv", default="")
    parser.add_argument(
        "--strict", action="store_true",
        help="Return a non-zero status when audit errors are found.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = args.report or os.path.join(args.artifact_root, "audit_report.json")
    csv_path = args.csv or os.path.join(args.artifact_root, "audited_results.csv")
    baseline_csv_path = args.baseline_csv or os.path.join(
        args.artifact_root, "audited_baselines.csv"
    )
    report = audit_artifact_package(args.artifact_root)
    write_audit_outputs(
        report, report_path=report_path, csv_path=csv_path,
        baseline_csv_path=baseline_csv_path,
    )

    summary = report["summary"]
    print("JoS artifact audit")
    print(f"  records: {summary['records']}")
    print(f"  independent records: {summary['independent_records']}")
    print(f"  baseline records: {summary['baseline_records']}")
    print(f"  independent baseline records: {summary['independent_baseline_records']}")
    print(f"  errors: {summary['errors']}")
    print(f"  warnings: {summary['warnings']}")
    for model, count in summary["independent_runs_by_model"].items():
        print(f"  {model}: {count} independent runs")
    for issue in report["issues"]:
        print(f"[{issue['severity'].upper()}] {issue['code']}: {issue['message']}")
    print(f"Report: {report_path}")
    print(f"Audited table: {csv_path}")
    print(f"Audited baselines: {baseline_csv_path}")
    return 1 if args.strict and summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
