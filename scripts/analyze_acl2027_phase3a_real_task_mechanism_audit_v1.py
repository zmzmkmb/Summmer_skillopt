#!/usr/bin/env python3
"""Zero-network Phase 3A audit of observable prior uptake in the v31 grid."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase3a_real_task_mechanism_audit_v1.json"
SOURCE_AUDIT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_second_recovery_live_v31/combined_failure_analysis_audit.json"
SCRIPT = ROOT / "scripts/analyze_acl2027_phase3a_real_task_mechanism_audit_v1.py"
TEST = ROOT / "tests/test_acl2027_phase3a_real_task_mechanism_audit_v1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3a_real_task_mechanism_audit_v1"
AUDIT = ARTIFACT / "mechanism_audit.json"
DIAGNOSTICS = ARTIFACT / "task_diagnostics.json"
PILOT = ARTIFACT / "activation_pilot_design.json"
MANIFEST = ARTIFACT / "run_manifest.json"
REPORT = ROOT / "paper/acl2027/results/phase3a_real_task_mechanism_audit_v1.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def classify(rows: dict[str, dict[str, Any]], priority: list[str]) -> str:
    typed = rows["contextual_typed_prior"]
    global_only = rows["global_only"]
    predicates = {
        "typed_benefit": typed["alias_tolerant_correct"] and not global_only["alias_tolerant_correct"],
        "typed_harm": global_only["alias_tolerant_correct"] and not typed["alias_tolerant_correct"],
        "no_observable_uptake": len({row["response_sha256"] for row in rows.values()}) == 1,
        "response_change_without_alias_outcome_change": len({row["alias_tolerant_correct"] for row in rows.values()}) == 1,
        "other_outcome_heterogeneity": True,
    }
    return next(label for label in priority if predicates[label])


def analyze() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    cfg = load(CONFIG)
    source = load(SOURCE_AUDIT)
    if any(cfg["execution"].values()):
        raise RuntimeError("Phase 3A execution switches must remain closed")
    if source.get("aggregate_fingerprint") != cfg["source"]["aggregate_fingerprint"]:
        raise RuntimeError("Phase 3A source fingerprint drift")
    if source.get("decision_gate") != cfg["diagnostic_rules"]["preserve_phase2_gate"]:
        raise RuntimeError("Phase 3A must preserve the Phase 2 gate")

    conditions = cfg["source"]["conditions"]
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in source["outcomes"]:
        grouped[str(row["task_id"])][str(row["condition"])] = row
    if len(grouped) != cfg["source"]["tasks"] or any(set(rows) != set(conditions) for rows in grouped.values()):
        raise RuntimeError("Phase 3A requires the complete 400-task four-condition grid")

    taxonomy = Counter()
    family_taxonomy: dict[str, Counter[str]] = defaultdict(Counter)
    capability = Counter()
    uptake = Counter()
    mechanism = Counter()
    diagnostics: list[dict[str, Any]] = []

    for task_id, rows in sorted(grouped.items()):
        ordered = [rows[condition] for condition in conditions]
        label = classify(rows, cfg["taxonomy"]["priority"])
        family = str(ordered[0]["skill_family"])
        taxonomy[label] += 1
        family_taxonomy[family][label] += 1

        response_hashes = {row["response_sha256"] for row in ordered}
        answers = {normalize_answer(str(row["answer"])) for row in ordered}
        strict_values = {bool(row["strict_correct"]) for row in ordered}
        alias_values = {bool(row["alias_tolerant_correct"]) for row in ordered}
        uptake["all_response_hashes_identical"] += int(len(response_hashes) == 1)
        uptake["all_normalized_answers_identical"] += int(len(answers) == 1)
        uptake["all_strict_outcomes_equal"] += int(len(strict_values) == 1)
        uptake["all_alias_outcomes_equal"] += int(len(alias_values) == 1)
        uptake["typed_global_response_differs"] += int(
            rows["contextual_typed_prior"]["response_sha256"] != rows["global_only"]["response_sha256"]
        )
        uptake["typed_global_answer_differs"] += int(
            normalize_answer(str(rows["contextual_typed_prior"]["answer"]))
            != normalize_answer(str(rows["global_only"]["answer"]))
        )

        alias_correct_count = sum(bool(row["alias_tolerant_correct"]) for row in ordered)
        capability["universally_correct"] += int(alias_correct_count == len(conditions))
        capability["universally_wrong"] += int(alias_correct_count == 0)
        capability["condition_sensitive"] += int(0 < alias_correct_count < len(conditions))

        cold = rows["cold"]
        copied = rows["copied_global"]
        global_only = rows["global_only"]
        typed = rows["contextual_typed_prior"]
        degradation = cold["alias_tolerant_correct"] and not global_only["alias_tolerant_correct"]
        mechanism["global_degradation_tasks"] += int(degradation)
        mechanism["typed_recovers_global_degradation"] += int(degradation and typed["alias_tolerant_correct"])
        mechanism["copied_recovers_global_degradation"] += int(degradation and copied["alias_tolerant_correct"])
        mechanism["typed_rescues_cold_failure"] += int(not cold["alias_tolerant_correct"] and typed["alias_tolerant_correct"])
        mechanism["typed_unique_success"] += int(
            typed["alias_tolerant_correct"]
            and not any(rows[name]["alias_tolerant_correct"] for name in conditions if name != "contextual_typed_prior")
        )
        mechanism["typed_unique_failure"] += int(
            not typed["alias_tolerant_correct"]
            and all(rows[name]["alias_tolerant_correct"] for name in conditions if name != "contextual_typed_prior")
        )

        diagnostics.append({
            "task_id": task_id,
            "skill_family": family,
            "taxonomy": label,
            "unique_response_hashes": len(response_hashes),
            "unique_normalized_answers": len(answers),
            "strict_outcomes": {name: bool(rows[name]["strict_correct"]) for name in conditions},
            "alias_tolerant_outcomes": {name: bool(rows[name]["alias_tolerant_correct"]) for name in conditions},
            "answers": {name: str(rows[name]["answer"]) for name in conditions},
            "source_runs": {name: str(rows[name]["source_run"]) for name in conditions},
        })

    tasks = len(grouped)
    rates = {key + "_rate": value / tasks for key, value in sorted(uptake.items())}
    rules = cfg["diagnostic_rules"]
    random_scale_up = (
        "reject_random_scale_up"
        if rates["all_alias_outcomes_equal_rate"] >= rules["reject_random_scale_up_if_all_alias_outcomes_equal_rate_at_least"]
        else "random_scale_up_not_rejected"
    )
    mechanism_bridge = (
        rates["all_response_hashes_identical_rate"]
        >= rules["require_mechanism_bridge_if_all_response_hashes_equal_rate_at_least"]
    )
    pilot = dict(cfg["future_activation_pilot"])
    pilot.update({
        "phase": "3B",
        "decision_from_phase3a": "materialize_zero_network_preflight" if mechanism_bridge else "reassess_need",
        "must_preserve_phase2_artifacts": True,
        "fresh_explicit_authorization_required_after_preflight": True,
    })
    result = {
        "schema_version": 1,
        "status": "complete",
        "experiment": cfg["experiment"],
        "rows": tasks,
        "completed_calls": tasks,
        "analyzed_phase2_response_rows": len(source["outcomes"]),
        "phase2_gate_preserved": source["decision_gate"],
        "taxonomy_counts": dict(taxonomy),
        "family_taxonomy": {family: dict(counts) for family, counts in sorted(family_taxonomy.items())},
        "capability_counts": dict(capability),
        "uptake_counts": dict(uptake),
        "uptake_rates": rates,
        "mechanism_counts": dict(mechanism),
        "random_scale_up_decision": random_scale_up,
        "mechanism_bridge_required": mechanism_bridge,
        "next_stage": "phase3b_activation_preflight_design_only",
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "formal_scaling_calls": 0,
        "authorization_artifact_created": False,
        "source_bindings": {
            "config_sha256": sha256_file(CONFIG),
            "source_audit_sha256": sha256_file(SOURCE_AUDIT),
            "source_aggregate_fingerprint": source["aggregate_fingerprint"],
            "analyzer_sha256": sha256_file(SCRIPT),
            "test_sha256": sha256_file(TEST),
        },
        "document_hashes": {
            "task_diagnostics": rendered_sha256(diagnostics),
            "activation_pilot_design": rendered_sha256(pilot),
        },
    }
    result["aggregate_fingerprint"] = stable(result)
    return result, diagnostics, pilot


def report_text(result: dict[str, Any]) -> str:
    counts = result["uptake_counts"]
    taxonomy = result["taxonomy_counts"]
    mechanism = result["mechanism_counts"]
    return (
        "# ACL 2027 Phase 3A real-task mechanism audit v1\n\n"
        "## Scope\n\n"
        "This is a zero-network descriptive audit of the completed Phase 2 v31 grid. It does not rescore or re-gate Phase 2, create an authorization, or make provider/model/paid calls.\n\n"
        "## Observable uptake\n\n"
        f"Among 400 tasks, all four raw responses were identical for `{counts['all_response_hashes_identical']}` tasks and all normalized answers were identical for `{counts['all_normalized_answers_identical']}`. Alias-tolerant outcomes were equal across all conditions for `{counts['all_alias_outcomes_equal']}` tasks. Typed and global-only raw responses differed for only `{counts['typed_global_response_differs']}` tasks.\n\n"
        f"The frozen taxonomy counts are `{taxonomy}`. The alias-tolerant global-degradation stratum contains `{mechanism['global_degradation_tasks']}` tasks; typed recovered `{mechanism['typed_recovers_global_degradation']}` and copied-global recovered `{mechanism['copied_recovers_global_degradation']}`.\n\n"
        "## Decision\n\n"
        f"Random same-distribution scale-up decision: **{result['random_scale_up_decision']}**. A mechanism-bridge experiment is required: `{str(result['mechanism_bridge_required']).lower()}`. The next admissible stage is a zero-network Phase 3B activation preflight for 60 new tasks and five conditions (300 proposed calls), with structured applicability, skill-ID, intermediate-operation, and final-answer observations. That proposal is not materialized and not authorized.\n\n"
        "## Integrity\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`. Phase 2 gate remains `{result['phase2_gate_preserved']}`. Network/provider/model/paid/formal-scaling counters: `0/0/0/0/0`.\n"
    )


def write_artifact(result: dict[str, Any], diagnostics: list[dict[str, Any]], pilot: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    AUDIT.write_text(render(result), encoding="utf-8", newline="\n")
    DIAGNOSTICS.write_text(render(diagnostics), encoding="utf-8", newline="\n")
    PILOT.write_text(render(pilot), encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": 1,
        "status": "completed_zero_network",
        "expected_runs": result["rows"],
        "available_runs": result["rows"],
        "complete_grid": True,
        "aggregate_fingerprint": result["aggregate_fingerprint"],
        "config_path": str(CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256_file(CONFIG),
        "runs": [],
        "mechanism_audit_sha256": rendered_sha256(result),
    }
    MANIFEST.write_text(render(manifest), encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    audit, diagnostics, pilot = analyze()
    if args.write_artifact:
        write_artifact(audit, diagnostics, pilot)
    print(json.dumps(audit, indent=2, sort_keys=True))
