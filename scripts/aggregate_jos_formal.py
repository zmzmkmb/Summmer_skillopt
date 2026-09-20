#!/usr/bin/env python3
"""Print the canonical JoS formal table from audited artifacts.

This script intentionally does not read the historical aggregate_results.csv,
because that file double-counts copied runs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skillopt.evaluation.artifact_audit import audit_artifact_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        default=str(PROJECT_ROOT / "artifacts" / "jos_experiment_v1"),
    )
    args = parser.parse_args()
    report = audit_artifact_package(args.artifact_root)

    print("Canonical JoS formal results (independent runs only)")
    print("=" * 88)
    for row in report["audited_results"]:
        print(
            f"{row['model']:<18} {row['method']:<18} "
            f"n={row['independent_runs']} seeds={row['seeds']:<8} "
            f"acc={row['accuracy_mean']:.4f} +/- {row['accuracy_std']:.4f} "
            f"tokens={row['avg_selected_tokens']:.0f}"
        )

    duplicates = [
        issue for issue in report["issues"]
        if issue["code"] in {"duplicate_run_content", "aggregate_seed_overcount"}
    ]
    if duplicates:
        print("\nAudit exclusions/warnings:")
        for issue in duplicates:
            print(f"- {issue['code']}: {issue['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
