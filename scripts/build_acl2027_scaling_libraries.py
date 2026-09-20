#!/usr/bin/env python3
"""Build deterministic 8/16/32/64-rule libraries for ACL 2027 scaling tests."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skillopt.evaluation.scaling_library import write_scaling_suite


DEFAULT_DISTRACTOR_SOURCES = [
    "outputs/ablation_law_fastonly/best_skill.md",
    "outputs/ablation_law_fastslow/best_skill.md",
    "outputs/ablation_math_fastonly/best_skill.md",
    "outputs/ablation_philosophy_fastonly/best_skill.md",
    "outputs/livemath_baseline/best_skill.md",
    "outputs/livemath_meta/best_skill.md",
    "outputs/livemath_v2/best_skill.md",
    "outputs/mmlu_elem_baseline/best_skill.md",
    "outputs/mmlupro_history/best_skill.md",
    "outputs/mmlupro_law/best_skill.md",
    "outputs/mmlupro_law_true/best_skill.md",
    "outputs/mmlupro_math/best_skill.md",
    "outputs/mmlupro_math_true/best_skill.md",
    "outputs/mmlupro_math_v2/best_skill.md",
    "outputs/mmlupro_philosophy/best_skill.md",
    "outputs/mmlupro_philosophy_true/best_skill.md",
    "outputs/verify_law_small/best_skill.md",
    "outputs/verify_philosophy_small/best_skill.md",
    "skillopt/envs/alfworld/skills/initial.md",
    "skillopt/envs/spreadsheetbench/skills/initial.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-skill", default="outputs/searchqa_rag/best_skill.md")
    parser.add_argument("--targets", type=int, nargs="+", default=[8, 16, 32, 64])
    parser.add_argument(
        "--out-dir",
        default="artifacts/acl2027_scaling_v1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    suite = write_scaling_suite(
        project_root=PROJECT_ROOT,
        base_skill_relative_path=args.base_skill,
        distractor_source_paths=DEFAULT_DISTRACTOR_SOURCES,
        targets=args.targets,
        output_dir=out_dir,
    )
    for level in suite["levels"]:
        print(
            f"{level['library_path']}: "
            f"{level['target_dynamic_rules']} dynamic rules, "
            f"fingerprint={level['rule_set_fingerprint'][:12]}"
        )
    print(f"Available unique distractors: {suite['available_unique_distractors']}")
    print(f"Suite manifest: {out_dir / 'suite_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
