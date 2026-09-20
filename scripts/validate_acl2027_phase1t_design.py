#!/usr/bin/env python3
"""Freeze and audit the zero-network ACL 2027 Phase 1T design."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs/acl2027/phase1t_heldout_deployment_identifiability_v1.json"
)
OUTPUT_DIR = (
    ROOT / "artifacts/acl2027_phase1t_heldout_deployment_identifiability_v1"
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_select(
    ids: list[str],
    *,
    seed: str,
    count: int,
    excluded: set[str] | None = None,
) -> list[str]:
    excluded = excluded or set()
    available = [item for item in ids if item not in excluded]
    ranked = sorted(
        available,
        key=lambda item: hashlib.sha256(
            f"{seed}:{item}".encode("utf-8")
        ).hexdigest(),
    )
    if len(ranked) < count:
        raise ValueError(f"need {count} IDs, found {len(ranked)}")
    return ranked[:count]


def substrate_eligible(
    stats: dict[str, Any],
    gate: dict[str, Any],
) -> bool:
    successes = int(stats["successes"])
    task_success_counts = {
        str(key): int(value)
        for key, value in stats.get("successes_by_task_id", {}).items()
    }
    max_share = max(task_success_counts.values(), default=0) / max(successes, 1)
    return all(
        (
            int(stats["tasks"]) == int(gate["calibration_tasks"]),
            float(stats["contract_valid_rate"])
            >= float(gate["contract_valid_rate_min"]),
            float(gate["baseline_accuracy_min"])
            <= float(stats["baseline_accuracy"])
            <= float(gate["baseline_accuracy_max"]),
            successes >= int(gate["minimum_successes"]),
            len(set(stats["successful_task_types"]))
            >= int(gate["minimum_success_task_types"]),
            max_share <= float(gate["maximum_success_share_per_task_id"]),
            bool(stats["automatic_verifier"]),
            bool(stats["reusable_skill_families"]),
        )
    )


def triage_decision(
    candidate_exact: list[int],
    fallback_exact: list[int],
    contract_valid: list[int],
    triage: dict[str, Any],
) -> dict[str, Any]:
    if not (
        len(candidate_exact) == len(fallback_exact) == len(contract_valid)
    ):
        raise ValueError("paired probe arrays must have equal length")
    valid_rate = sum(contract_valid) / len(contract_valid)
    if (
        len(candidate_exact) < int(triage["minimum_paired_probe_tasks"])
        or valid_rate < float(triage["probe_contract_valid_rate_min"])
    ):
        return {"decision": "abstain", "valid_rate": valid_rate}
    margins = [
        int(candidate) - int(fallback)
        for candidate, fallback in zip(candidate_exact, fallback_exact)
    ]
    mean_margin = sum(margins) / len(margins)
    helpful = sum(margin > 0 for margin in margins)
    harmful = sum(margin < 0 for margin in margins)
    accept = triage["accept"]
    reject = triage["reject"]
    if (
        mean_margin >= float(accept["mean_margin_min"])
        and helpful >= int(accept["helpful_pair_count_min"])
        and harmful <= int(accept["harmful_pair_count_max"])
    ):
        decision = "accept"
    elif (
        mean_margin <= float(reject["mean_margin_max"])
        or harmful >= int(reject["harmful_pair_count_min"])
    ):
        decision = "reject"
    else:
        decision = "abstain"
    return {
        "decision": decision,
        "valid_rate": valid_rate,
        "mean_margin": mean_margin,
        "helpful_pairs": helpful,
        "harmful_pairs": harmful,
    }


def apply_initial_transition(policy: dict[str, Any], decision: str) -> str:
    if decision not in {"accept", "reject", "abstain"}:
        raise ValueError(f"unsupported decision: {decision}")
    return str(policy[decision])


def apply_recovery(
    state: str,
    windows: list[dict[str, list[int]]],
    policy: dict[str, Any],
) -> str:
    if not policy.get("recovery_allowed", True):
        return state
    gate = policy["recovery_gate"]
    if state not in gate["eligible_from"]:
        return state
    qualifying = 0
    for window in windows:
        margins = [
            int(candidate) - int(fallback)
            for candidate, fallback in zip(
                window["candidate_exact"], window["fallback_exact"]
            )
        ]
        mean_margin = sum(margins) / len(margins)
        helpful = sum(margin > 0 for margin in margins)
        harmful = sum(margin < 0 for margin in margins)
        if (
            mean_margin >= float(gate["window_mean_margin_min"])
            and helpful >= int(gate["helpful_pair_count_min_per_window"])
            and harmful <= int(gate["harmful_pair_count_max_per_window"])
        ):
            qualifying += 1
        else:
            qualifying = 0
        if qualifying >= int(gate["consecutive_windows"]):
            return str(gate["success_state"])
    return state


def _ids(path: Path) -> list[str]:
    return [str(item["id"]) for item in read_json(path)]


def audit(config: dict[str, Any]) -> dict[str, Any]:
    execution = config["execution"]
    source = config["source_contracts"]
    gate = config["substrate_eligibility_gate"]
    searchqa = config["substrates"]["SearchQA"]
    two_wiki = config["substrates"]["2WikiMultiHopQA"]
    train = _ids(ROOT / source["searchqa_train_ids"])
    val = _ids(ROOT / source["searchqa_val_ids"])
    test = _ids(ROOT / source["searchqa_test_ids"])
    spent_rows = read_jsonl(ROOT / source["searchqa_spent_calls"])
    spent_test = {str(row["item_id"]) for row in spent_rows}

    calibration = stable_select(
        val,
        seed=searchqa["calibration_selector"]["seed"],
        count=searchqa["calibration_selector"]["count"],
    )
    streams = searchqa["stream_design"]
    history = stable_select(
        train,
        seed=streams["history"]["seed"],
        count=streams["history"]["count"],
    )
    probe = stable_select(
        val,
        seed=streams["development_probe"]["seed"],
        count=streams["development_probe"]["count"],
        excluded=set(calibration),
    )
    downstream = stable_select(
        test,
        seed=streams["held_out_downstream"]["seed"],
        count=streams["held_out_downstream"]["count"],
        excluded=spent_test,
    )

    scenario_results = {
        scenario["id"]: triage_decision(
            scenario["candidate_exact"],
            scenario["fallback_exact"],
            scenario["contract_valid"],
            config["numerical_triage"],
        )
        for scenario in config["identifiability_scenarios"]
    }
    retaining = config["policy_state_transitions"]["candidate_retaining_triage"]
    destructive = config["policy_state_transitions"]["destructive_gate"]
    recovery = config["recovery_scenario"]
    retained_initial = apply_initial_transition(
        retaining, recovery["initial_decision"]
    )
    destructive_initial = apply_initial_transition(
        destructive, recovery["initial_decision"]
    )
    retained_final = apply_recovery(
        retained_initial, recovery["later_windows"], retaining
    )
    destructive_final = apply_recovery(
        destructive_initial, recovery["later_windows"], destructive
    )

    eligible_fixture = {
        "tasks": 12,
        "contract_valid_rate": 11 / 12,
        "baseline_accuracy": 0.5,
        "successes": 6,
        "successful_task_types": ["bridge", "comparison", "temporal"],
        "successes_by_task_id": {
            "a": 1,
            "b": 1,
            "c": 1,
            "d": 1,
            "e": 1,
            "f": 1,
        },
        "automatic_verifier": True,
        "reusable_skill_families": True,
    }
    floor_fixture = deepcopy(eligible_fixture)
    floor_fixture["baseline_accuracy"] = 1 / 12
    concentrated_fixture = deepcopy(eligible_fixture)
    concentrated_fixture["successes_by_task_id"] = {"one-task": 6}
    token_total = sum(
        int(row["candidate_tokens"]) + int(row["fallback_tokens"])
        for row in config["token_accounting_fixture"]
    )

    phase1s_analysis = read_json(ROOT / source["phase1s_analysis_manifest"])
    phase1s_audit = read_json(ROOT / source["phase1s_design_audit"])
    manifest = read_json(ROOT / source["searchqa_split_manifest"])
    expected_scenarios = {
        scenario["id"]: scenario["expected_decision"]
        for scenario in config["identifiability_scenarios"]
    }
    checks = {
        "zero_network_paid_and_scaling": not any(
            execution[key]
            for key in (
                "paid_api_allowed",
                "network_calls_allowed",
                "formal_scaling_allowed",
                "qwen3_8_max_allowed",
                "legacy_officeqa_spreadsheetbench_batch_allowed",
                "dataset_download_allowed",
            )
        )
        and execution["provider_calls"] == 0,
        "eligibility_gate_exact": gate["calibration_tasks"] == 12
        and gate["contract_valid_rate_min"] == 0.9
        and gate["baseline_accuracy_min"] == 0.25
        and gate["baseline_accuracy_max"] == 0.75
        and gate["minimum_success_task_types"] == 3
        and gate["automatic_verifier_required"]
        and gate["reusable_skill_families_required"]
        and gate["all_criteria_required"],
        "eligibility_fixture_passes": substrate_eligible(eligible_fixture, gate),
        "floor_fixture_fails": not substrate_eligible(floor_fixture, gate),
        "concentration_fixture_fails": not substrate_eligible(
            concentrated_fixture, gate
        ),
        "searchqa_manifest_counts_match": manifest["counts"]
        == {"train": len(train), "val": len(val), "test": len(test)},
        "searchqa_spent_ids_visible": len(spent_rows) == 2448
        and len(spent_test) == 360
        and spent_test.issubset(test),
        "searchqa_streams_are_disjoint": set(calibration).isdisjoint(probe)
        and set(history).isdisjoint(calibration)
        and set(history).isdisjoint(probe)
        and set(history).isdisjoint(downstream)
        and set(calibration).isdisjoint(downstream)
        and set(probe).isdisjoint(downstream),
        "searchqa_downstream_excludes_spent": set(downstream).isdisjoint(
            spent_test
        ),
        "searchqa_capacities_exact": (
            len(calibration),
            len(history),
            len(probe),
            len(downstream),
        )
        == (12, 120, 24, 120),
        "searchqa_anchor_requires_fresh_gate": searchqa["role"]
        == "proven_non_floor_anchor_requiring_fresh_gate"
        and gate["historical_results_do_not_auto_qualify"]
        and searchqa["historical_no_skill_em"] > gate["baseline_accuracy_max"],
        "two_wiki_is_frozen_but_unmaterialized": two_wiki["role"]
        == "preferred_new_candidate"
        and two_wiki["local_payload_status"] == "not_materialized"
        and two_wiki["download_forbidden_by_this_phase"]
        and two_wiki["partition_selector"]["pairwise_disjoint"]
        and two_wiki["partition_selector"]["calibration_count"] == 12,
        "history_contract_is_verified_and_typed": set(
            config["historical_experience_contract"]["trajectory_requires"]
        )
        >= {
            "contract_valid_output",
            "automatic_verifier_success",
            "immutable_task_id",
            "prompt_and_response_provenance",
            "exact_token_usage",
        }
        and config["historical_experience_contract"][
            "skill_candidate_requires"
        ]["typed_scope_required"]
        and config["historical_experience_contract"][
            "skill_candidate_requires"
        ]["held_out_outputs_forbidden"],
        "triage_scenarios_identified": all(
            scenario_results[name]["decision"] == expected
            for name, expected in expected_scenarios.items()
        ),
        "policy_transitions_are_distinct": retaining["reject"]
        != destructive["reject"]
        and retaining["abstain"] != destructive["abstain"]
        and not retaining["negative_decision_mutates_candidate"]
        and destructive["discard_is_irreversible"],
        "retained_candidate_recovers": retained_final
        == recovery["retaining_expected_state"],
        "destructive_candidate_cannot_recover": destructive_final
        == recovery["destructive_expected_state"],
        "metrics_cover_required_outcomes": set(config["metrics"])
        >= {
            "false_safe",
            "false_harm",
            "helpful_deployment",
            "harmful_deployment",
            "abstention_rate",
            "retained_candidate_recovery",
            "probe_to_stream_sign_agreement",
            "exact_token_accounting",
            "reward_per_1k_cumulative_tokens",
        },
        "counterfactual_token_fixture_exact": token_total == 1000,
        "phase1s_nonidentifiability_bound": phase1s_analysis["scored_calls"]
        == 192
        and not phase1s_audit["downstream_tasks_executed"]
        and phase1s_audit["gate_labels_are_metadata_only_in_this_run"]
        and not phase1s_audit[
            "numerical_gate_thresholds_implemented"
        ],
        "preflight_claim_limit_explicit": config["decision_gate"][
            "preflight_does_not_establish_method_claim"
        ],
    }
    return {
        "analysis": "phase1t_zero_network_heldout_deployment_identifiability",
        "source_hashes": {
            name: sha256_file(ROOT / path)
            for name, path in source.items()
        },
        "searchqa_design": {
            "calibration_ids": calibration,
            "history_ids": history,
            "development_probe_ids": probe,
            "held_out_downstream_ids": downstream,
            "spent_test_ids_excluded": len(spent_test),
        },
        "eligibility_floor_tests": {
            "eligible_fixture": substrate_eligible(eligible_fixture, gate),
            "floor_fixture": substrate_eligible(floor_fixture, gate),
            "concentrated_fixture": substrate_eligible(
                concentrated_fixture, gate
            ),
        },
        "triage_scenarios": scenario_results,
        "state_transition_test": {
            "retaining_initial": retained_initial,
            "retaining_final": retained_final,
            "destructive_initial": destructive_initial,
            "destructive_final": destructive_final,
        },
        "counterfactual_token_total": token_total,
        "checks": checks,
        "decision": (
            "design_frozen_execution_closed"
            if all(checks.values())
            else "design_failed_execution_closed"
        ),
        "network_calls": 0,
        "paid_api_calls": 0,
    }


def write_artifact(
    config: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(
            f"refusing to overwrite immutable artifact: {output_dir}"
        )
    result = audit(deepcopy(config))
    output_dir.mkdir(parents=True)
    result_path = output_dir / "design_audit.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256_file(CONFIG_PATH),
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": all(result["checks"].values()),
        "analysis_only": True,
        "network_calls": 0,
        "paid_api_calls": 0,
        "runs": [
            {
                "run_id": "phase1t_zero_network_design_audit",
                "status": "completed",
                "result_path": str(result_path.relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "file_sha256": sha256_file(result_path),
            }
        ],
        "aggregate_fingerprint": sha256_file(result_path),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = write_artifact(read_json(CONFIG_PATH), OUTPUT_DIR)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["decision"] == "design_frozen_execution_closed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
