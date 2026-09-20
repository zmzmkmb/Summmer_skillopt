#!/usr/bin/env python3
"""Verification-corrected Phase 3H preflight; v1 remains immutable provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1 as base
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

VERSION = 2
EXPERIMENT = "acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v2"
CONFIG = ROOT / "configs/acl2027/phase3h_counterfactual_answer_sensitivity_preflight_v2.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v2.py"
TEST = ROOT / "tests/test_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v2.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v2"
REPORT = ROOT / "paper/acl2027/results/phase3h_counterfactual_answer_sensitivity_preflight_v2.md"
V1_SCRIPT = ROOT / "scripts/run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1.py"
V1_MANIFEST = ROOT / "artifacts/acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1/run_manifest.json"

_base_build_schedule = base.build_schedule
_base_candidate_payloads = base.candidate_payloads


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase3h-v2:counterfactual-answer:{family}:{task_id}".encode()).hexdigest()


def candidate_payloads(family: str) -> tuple[dict[str, Any], dict[str, Any]]:
    target, control = _base_candidate_payloads(family)
    for candidate in (target, control):
        candidate["candidate_id"] = str(candidate["candidate_id"]).replace("phase3h-target", "phase3h-v2-target").replace("phase3h-inverse-control", "phase3h-v2-inverse-control")
    return target, control


def build_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schedule, private_gold = _base_build_schedule(tasks)
    for row in schedule:
        body = row["canonical_request_body"]
        body["candidate_version"] = "phase3h-v2-design-only"
        body["prompt_template_version"] = "phase3h-counterfactual-grounding-native-mapping-v2"
        row["logical_call_id"] = str(row["logical_call_id"]).replace("phase3h-v1:", "phase3h-v2:")
        row["request_hash"] = stable(body)
    return schedule, private_gold


def source_paths() -> dict[str, Path]:
    return {
        "base_preflight_source_sha256": V1_SCRIPT,
        "candidate_source_module_sha256": base.CANDIDATE_SOURCE,
        "phase3f_diagnostic_sha256": base.PHASE3F_DIAGNOSTIC,
        "phase3f_strict_sha256": base.PHASE3F_STRICT,
        "phase3g_report_sha256": base.PHASE3G_REPORT,
        "preflight_source_sha256": SCRIPT,
        "preflight_test_sha256": TEST,
        "source_2wiki_dev_sha256": base.SOURCE_2WIKI,
        "v1_unaccepted_manifest_sha256": V1_MANIFEST,
        "v17_prior_bundles_sha256": base.V17_PRIORS,
    }


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def _configure_base() -> None:
    base.VERSION = VERSION
    base.EXPERIMENT = EXPERIMENT
    base.CONFIG = CONFIG
    base.SCRIPT = SCRIPT
    base.TEST = TEST
    base.ARTIFACT = ARTIFACT
    base.REPORT = REPORT
    base.selector_hash = selector_hash
    base.candidate_payloads = candidate_payloads
    base.build_schedule = build_schedule
    base.source_paths = source_paths
    base.source_bindings = source_bindings


_configure_base()
CONDITIONS = base.CONDITIONS
normalize = base.normalize
select_tasks = base.select_tasks
validate = base.validate
write_artifact = base.write_artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-bindings", action="store_true")
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    if args.print_bindings:
        print(json.dumps(source_bindings(), indent=2, sort_keys=True))
        raise SystemExit(0)
    validation = validate()
    if args.write_artifact:
        write_artifact(validation)
    print(json.dumps(validation, indent=2, sort_keys=True))
