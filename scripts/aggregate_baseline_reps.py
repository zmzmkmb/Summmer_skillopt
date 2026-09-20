#!/usr/bin/env python3
"""Print canonical baseline summaries from manifested, fingerprinted artifacts."""
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

    print("Canonical JoS baseline results (independent runs only)")
    print("=" * 104)
    for row in report["audited_baselines"]:
        completeness = "" if row["independent_runs"] >= 3 else " [INCOMPLETE]"
        print(
            f"{row['condition']:<20} {row['model']:<18} {row['method']:<18} "
            f"n={row['independent_runs']} seeds={row['seeds']:<8} "
            f"acc={row['accuracy_mean']:.4f} +/- {row['accuracy_std']:.4f} "
            f"tokens={row['avg_selected_tokens']:.0f} "
            f"budget_viol={row['budget_violations']}{completeness}"
        )

    duplicates = [
        issue for issue in report["issues"] if issue["code"] == "duplicate_baseline_content"
    ]
    if duplicates:
        print("\nDuplicate baseline runs excluded:")
        for issue in duplicates:
            print(f"- {issue['message']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
