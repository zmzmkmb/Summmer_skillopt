#!/usr/bin/env python3
"""Freeze and audit the zero-network ACL 2027 Phase 1P protocol."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase1p_contribution_aligned_protocol_v1.json"
OUTPUT_DIR = ROOT / "artifacts/acl2027_phase1p_contribution_aligned_protocol_v1"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _item_map(path: Path) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in read_json(path)}


def _stream_checks(
    stream: dict[str, Any],
    available: dict[str, dict[str, Any]],
) -> dict[str, bool]:
    development = [str(item) for item in stream["development_ids"]]
    held_out = [str(item) for item in stream["held_out_ids"]]
    order = [str(item) for item in stream["stream_order"]]
    representative = [str(item) for item in stream["representative_probe_ids"]]
    shifted = [str(item) for item in stream["shifted_probe_ids"]]
    return {
        "all_ids_exist": all(item in available for item in development + held_out),
        "development_unique": len(development) == len(set(development)),
        "held_out_unique": len(held_out) == len(set(held_out)),
        "development_held_out_disjoint": set(development).isdisjoint(held_out),
        "stream_order_exact": len(order) == len(held_out) and set(order) == set(held_out),
        "representative_is_development": set(representative).issubset(development),
        "shifted_is_development": set(shifted).issubset(development),
        "probe_panels_have_four_items": len(representative) == len(shifted) == 4,
    }


def audit(config: dict[str, Any]) -> dict[str, Any]:
    execution = config["execution"]
    source = config["source_contracts"]
    office_items = _item_map(ROOT / source["officeqa_val_items"])
    sheet_items = _item_map(ROOT / source["spreadsheetbench_val_items"])
    sheet_payload = _item_map(ROOT / source["spreadsheetbench_payload"])
    office = config["task_streams"]["OfficeQA"]
    spreadsheet = config["task_streams"]["SpreadsheetBench"]
    office_checks = _stream_checks(office, office_items)
    spreadsheet_checks = _stream_checks(spreadsheet, sheet_items)
    office_dev = set(office["development_ids"])
    office_held = set(office["held_out_ids"])
    sheet_all = spreadsheet["development_ids"] + spreadsheet["held_out_ids"]

    workbook_pairs = {}
    for item_id in sheet_all:
        task_dir = (
            ROOT
            / source["spreadsheetbench_root"]
            / sheet_payload[str(item_id)]["spreadsheet_path"]
        )
        workbook_pairs[str(item_id)] = {
            "initial_count": len(list(task_dir.glob("*_init.xlsx"))),
            "golden_count": len(list(task_dir.glob("*_golden.xlsx"))),
        }

    triage = config["gate_policies"]["candidate_retaining_triage"]
    destructive = config["gate_policies"]["destructive_gate"]
    fairness = config["pairing_and_fairness"]
    prior = config["prior_conditions"]
    phase1o = read_json(ROOT / source["phase1o_results"])
    phase1o_manifest = read_json(ROOT / source["phase1o_manifest"])
    checks = {
        "zero_network_paid_and_scaling": not any(
            execution[key]
            for key in (
                "paid_api_allowed",
                "network_calls_allowed",
                "formal_scaling_allowed",
                "qwen3_8_max_allowed",
                "officeqa_24_batch_allowed",
                "spreadsheetbench_40_batch_allowed",
            )
        )
        and execution["provider_calls"] == 0,
        "officeqa_stream_valid": all(office_checks.values()),
        "officeqa_frozen_8_development_16_held_out": len(office_dev) == 8
        and len(office_held) == 16,
        "officeqa_held_out_near_balanced_difficulty": {
            office_items[item]["category"] for item in office_held
        }
        == {"easy", "hard"}
        and abs(
            sum(office_items[item]["category"] == "easy" for item in office_held)
            - sum(
                office_items[item]["category"] == "hard"
                for item in office_held
            )
        )
        <= 2,
        "officeqa_shift_is_hard_single_document": all(
            office_items[item]["category"] == "hard"
            and len(str(office_items[item]["source_files"]).splitlines()) == 1
            for item in office["shifted_probe_ids"]
        ),
        "spreadsheet_stream_valid": all(spreadsheet_checks.values()),
        "spreadsheet_frozen_8_development_16_held_out": len(
            spreadsheet["development_ids"]
        )
        == 8
        and len(spreadsheet["held_out_ids"]) == 16,
        "spreadsheet_cell_level_only": all(
            sheet_items[str(item)]["instruction_type"] == "Cell-Level Manipulation"
            for item in sheet_all
        ),
        "spreadsheet_payload_rows_exist": all(
            str(item) in sheet_payload for item in sheet_all
        ),
        "spreadsheet_workbook_pairs_exist": all(
            counts == {"initial_count": 1, "golden_count": 1}
            for counts in workbook_pairs.values()
        ),
        "constructors_forbid_reference_access": office["executor_contract"][
            "reference_answer_forbidden_during_construction"
        ]
        and spreadsheet["executor_contract"][
            "golden_workbook_forbidden_during_construction"
        ],
        "score_after_persistence": office["executor_contract"][
            "score_after_persistence"
        ]
        and spreadsheet["executor_contract"]["score_after_persistence"],
        "phase1o_executor_substrate_passed": phase1o_manifest["complete_grid"]
        and phase1o_manifest["network_calls"] == 0
        and phase1o_manifest["paid_api_calls"] == 0
        and {
            item["task_family"]: item["route_decision"] for item in phase1o
        }
        == {
            "OfficeQA": (
                "keep_with_deterministic_executor_and_"
                "abstain_on_evidence_mismatch"
            ),
            "SpreadsheetBench": (
                "redesign_as_constrained_executor_backed_task"
            ),
        },
        "three_distinct_prior_conditions": set(prior)
        >= {"copied-global", "global-only", "contextual", "identity_invariant"}
        and len(
            {
                prior[name]
                for name in ("copied-global", "global-only", "contextual")
            }
        )
        == 3,
        "fair_condition_controls_frozen": all(
            fairness[key]
            for key in (
                "identical_prompt_template",
                "identical_task_order",
                "identical_examples",
                "identical_call_allocation",
                "exact_usage_accounting",
                "no_live_execution_authorized_by_this_config",
            )
        )
        and fairness["request_max_tokens_policy"]
        == "omit_max_tokens_for_every_condition",
        "counterfactual_costs_charge_both_branches": "every gate branch"
        in fairness["counterfactual_branch_accounting"],
        "triage_actions_complete": triage["actions"]
        == ["accept", "reject", "abstain"],
        "triage_retains_rejected_and_abstained": not triage[
            "candidate_state_mutated_on_reject"
        ]
        and not triage["candidate_state_mutated_on_abstain"]
        and not triage["discard_is_action"],
        "destructive_gate_is_comparator": destructive["actions"]
        == ["accept", "discard"]
        and destructive["role"] == "destructive comparator only",
        "representativeness_metrics_complete": set(
            config["probe_protocol"]["predeclared_metrics"]
        )
        >= {
            "probe_to_stream_sign_agreement",
            "probe_to_stream_pearson",
            "probe_to_stream_spearman",
            "false_safe_rate",
            "false_harm_rate",
            "coverage",
            "downstream_regret",
            "reward_per_1k_cumulative_tokens",
        },
        "design_cell_count_is_3x2x2x2": config["expected_design_cells"] == 24,
        "preflight_claim_limit_explicit": config["decision_gate"][
            "preflight_does_not_establish_method_claim"
        ],
    }
    return {
        "analysis": "phase1p_zero_network_contribution_aligned_protocol_preflight",
        "source_hashes": {
            name: sha256_file(ROOT / path)
            for name, path in source.items()
            if name != "spreadsheetbench_root"
        },
        "task_streams": {
            "OfficeQA": {
                "development_count": len(office_dev),
                "held_out_count": len(office_held),
                "checks": office_checks,
            },
            "SpreadsheetBench": {
                "development_count": len(spreadsheet["development_ids"]),
                "held_out_count": len(spreadsheet["held_out_ids"]),
                "checks": spreadsheet_checks,
                "workbook_pair_count": len(workbook_pairs),
            },
        },
        "design": {
            "prior_conditions": ["copied-global", "global-only", "contextual"],
            "probe_strata": config["probe_protocol"]["strata"],
            "gate_policies": list(config["gate_policies"]),
            "task_families": list(config["task_streams"]),
            "expected_cells": config["expected_design_cells"],
        },
        "checks": checks,
        "decision": (
            "protocol_frozen_future_execution_closed"
            if all(checks.values())
            else "protocol_failed_execution_closed"
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
    result_path = output_dir / "protocol_audit.json"
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
                "run_id": "phase1p_zero_network_protocol_preflight",
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
    return (
        0
        if result["decision"] == "protocol_frozen_future_execution_closed"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
