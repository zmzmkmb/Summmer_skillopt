#!/usr/bin/env python3
"""Freeze and audit the zero-network Phase 1H repaired smoke payloads."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

try:
    from scripts.run_acl2027_phase1f_smoke import (
        _office_context,
        _workbook_snapshot,
        canonical_hash,
        read_json,
        sha256_file,
        write_json,
    )
except ModuleNotFoundError:
    from run_acl2027_phase1f_smoke import (
        _office_context,
        _workbook_snapshot,
        canonical_hash,
        read_json,
        sha256_file,
        write_json,
    )

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/acl2027/phase1h_repaired_cross_task_smoke_preflight_v1.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_phase1h_repaired_cross_task_smoke_preflight_v1"


class PreflightError(RuntimeError):
    """Raised when a frozen Phase 1H payload violates its contract."""


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def validate_config(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = read_json(config_path)
    execution = config.get("execution", {})
    if config.get("phase") != "1H":
        raise PreflightError("config phase must be 1H")
    required_false = (
        "paid_api_allowed",
        "formal_scaling_allowed",
        "network_calls_allowed",
        "live_execution_from_this_config",
    )
    if any(execution.get(key) is not False for key in required_false):
        raise PreflightError("Phase 1H preflight must disable paid, network, live, and scaling execution")
    pairing = config.get("pairing", {})
    if pairing.get("logical_calls") != 2:
        raise PreflightError("Phase 1H must freeze exactly two logical calls")
    if pairing.get("task_order") != ["OfficeQA", "SpreadsheetBench"]:
        raise PreflightError("Phase 1H task order changed")

    for family, task in config["data"].items():
        manifest = ROOT / task["source_manifest"]
        if sha256_file(manifest) != task["source_manifest_sha256"]:
            raise PreflightError(f"{family} split manifest hash mismatch")
        payload_key = "payload_csv" if family == "OfficeQA" else "payload_dataset"
        if sha256_file(ROOT / task[payload_key]) != task[f"{payload_key}_sha256"]:
            raise PreflightError(f"{family} payload hash mismatch")

    phase1g = ROOT / config["contracts"]["phase1g_config"]
    if sha256_file(phase1g) != config["contracts"]["phase1g_config_sha256"]:
        raise PreflightError("Phase 1G contract hash mismatch")
    return config


def _split_ids(task: dict[str, Any]) -> list[str]:
    manifest_path = ROOT / task["source_manifest"]
    items_path = manifest_path.parent / task["split"] / "items.json"
    values = read_json(items_path)
    ids: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("id", value.get("uid"))
        ids.append(str(value))
    return ids


def _office_row(config: dict[str, Any]) -> dict[str, str]:
    task = config["data"]["OfficeQA"]
    target = str(task["smoke_id"])
    with (ROOT / task["payload_csv"]).open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if str(row.get("uid", row.get("UID", ""))) == target]
    if len(rows) != 1:
        raise PreflightError(f"OfficeQA smoke UID {target} did not resolve uniquely")
    if target not in _split_ids(task):
        raise PreflightError(f"OfficeQA smoke UID {target} is not in the frozen {task['split']} split")
    return rows[0]


def _spreadsheet_item(config: dict[str, Any]) -> dict[str, Any]:
    task = config["data"]["SpreadsheetBench"]
    target = str(task["smoke_id"])
    rows = [row for row in read_json(ROOT / task["payload_dataset"]) if str(row.get("id")) == target]
    if len(rows) != 1:
        raise PreflightError(f"SpreadsheetBench smoke ID {target} did not resolve uniquely")
    if target not in _split_ids(task):
        raise PreflightError(f"SpreadsheetBench smoke ID {target} is not in the frozen {task['split']} split")
    return rows[0]


def build_request_plan(config: dict[str, Any]) -> list[dict[str, Any]]:
    office_task = config["data"]["OfficeQA"]
    office = _office_row(config)
    source_path, context = _office_context(str(office["source_files"]))
    office_system = (
        "Answer only from the supplied source excerpt. Return one JSON object with exactly the top-level "
        "keys answer, evidence, and calculation; no markdown. evidence must be a non-empty list whose "
        "items each contain source_path, locator, period, and value. calculation must contain operation, "
        "time_basis, operands, and result. Use calendar as time_basis and include every one of the 12 "
        "monthly operands required by the question. Do not substitute a fiscal-year total for a calendar-year "
        "aggregation. The answer and calculation result must agree."
    )
    office_messages = [
        {"role": "system", "content": office_system},
        {
            "role": "user",
            "content": (
                f"Question: {office['question']}\n\n"
                f"Source path: {_relative(source_path)}\n\nSource excerpt:\n{context}"
            ),
        },
    ]

    sheet_task = config["data"]["SpreadsheetBench"]
    sheet = _spreadsheet_item(config)
    if str(sheet["answer_position"]) != str(sheet_task["expected_target_range"]):
        raise PreflightError("SpreadsheetBench target range differs from the frozen contract")
    task_dir = ROOT / "data/spreadsheetbench_verified_400" / str(sheet["spreadsheet_path"])
    workbook_path, snapshot = _workbook_snapshot(task_dir)
    sheet_system = (
        "Solve the spreadsheet formula task from the instruction and workbook snapshot. Return one JSON object "
        "with exactly the top-level keys target_range, edits, and explanation; no markdown. target_range must be "
        "B5:E7. edits must contain exactly one object with sheet, cell, and formula for every cell in B5:E7: "
        "12 edits total, with no duplicate, missing, or out-of-range cells. Each formula must be directly "
        "executable in its specified cell. Do not claim the workbook was executed."
    )
    sheet_messages = [
        {"role": "system", "content": sheet_system},
        {
            "role": "user",
            "content": (
                f"Instruction: {sheet['instruction']}\n\n"
                f"Initial workbook: {_relative(workbook_path)}\n\n"
                f"Workbook snapshot: {json.dumps(snapshot, ensure_ascii=True, sort_keys=True)}"
            ),
        },
    ]

    common = {
        "model": config["execution"]["model_id"],
        "temperature": config["execution"]["temperature"],
        "enable_thinking": config["execution"]["enable_thinking"],
    }
    plan = [
        {
            "task_family": "OfficeQA",
            "task_id": str(office_task["smoke_id"]),
            "source_paths": [_relative(ROOT / office_task["payload_csv"]), _relative(source_path)],
            "request": {**common, "max_tokens": office_task["max_output_tokens"], "messages": office_messages},
        },
        {
            "task_family": "SpreadsheetBench",
            "task_id": str(sheet_task["smoke_id"]),
            "source_paths": [_relative(ROOT / sheet_task["payload_dataset"]), _relative(workbook_path)],
            "request": {**common, "max_tokens": sheet_task["max_output_tokens"], "messages": sheet_messages},
        },
    ]
    for row in plan:
        row["request_hash"] = canonical_hash(row["request"])
    return plan


def audit_plan(config: dict[str, Any], plan: list[dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(plan, ensure_ascii=True, sort_keys=True)
    office_prompt = json.dumps(plan[0]["request"]["messages"], ensure_ascii=True, sort_keys=True)
    sheet_prompt = json.dumps(plan[1]["request"]["messages"], ensure_ascii=True, sort_keys=True)
    office_answer = _office_row(config).get("answer", "")
    sheet_item = _spreadsheet_item(config)
    checks = {
        "exactly_two_requests": len(plan) == 2,
        "exact_task_order": [row["task_family"] for row in plan] == config["pairing"]["task_order"],
        "exact_task_ids": [row["task_id"] for row in plan] == ["UID0001", "45635"],
        "same_model_and_temperature": len({(row["request"]["model"], row["request"]["temperature"]) for row in plan}) == 1,
        "stable_request_hashes": all(len(row["request_hash"]) == 64 for row in plan),
        "office_repaired_schema_present": all(token in office_prompt for token in ("answer", "evidence", "calculation", "source_path", "locator", "period", "operands")),
        "office_calendar_guard_present": all(token in office_prompt for token in ("calendar", "fiscal-year", "12 monthly operands")),
        "office_reference_answer_not_injected": bool(office_answer) and office_answer not in office_prompt,
        "spreadsheet_repaired_schema_present": all(token in sheet_prompt for token in ("target_range", "edits", "explanation", "sheet", "cell", "formula")),
        "spreadsheet_exact_coverage_present": all(token in sheet_prompt for token in ("B5:E7", "12 edits", "no duplicate", "missing")),
        "spreadsheet_golden_not_injected": "answer" not in sheet_item and "golden_formula" not in serialized,
        "network_and_paid_calls_zero": config["execution"]["network_calls_allowed"] is False,
        "live_execution_impossible": config["execution"]["live_execution_from_this_config"] is False,
        "batch_remains_closed": config["execution"]["batch_closed"] is True,
    }
    return {
        "analysis": "phase1h_repaired_cross_task_smoke_preflight",
        "checks": checks,
        "request_count": len(plan),
        "request_hashes": {row["task_family"]: row["request_hash"] for row in plan},
        "network_calls": 0,
        "paid_api_calls": 0,
        "decision": "preflight_passed_paid_successor_still_closed" if all(checks.values()) else "preflight_failed_paid_successor_closed",
        "scientific_claim_effect": "measurement_protocol_strengthened; overall_main_claim_unchanged_and_not_established",
    }


def prepare(config_path: Path = DEFAULT_CONFIG) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = validate_config(config_path)
    plan = build_request_plan(config)
    return audit_plan(config, plan), plan


def main() -> int:
    if DEFAULT_OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite immutable artifact: {DEFAULT_OUTPUT}")
    config = validate_config()
    audit, plan = prepare()
    DEFAULT_OUTPUT.mkdir(parents=True)
    review_path = DEFAULT_OUTPUT / "payload_review.json"
    write_json(review_path, {"requests": plan, **audit})
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": _relative(DEFAULT_CONFIG),
        "config_sha256": sha256_file(DEFAULT_CONFIG),
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": True,
        "analysis_only": True,
        "network_calls": 0,
        "paid_api_calls": 0,
        "runs": [{"run_id": "phase1h_zero_call_payload_review", "status": "completed", "result_path": _relative(review_path), "file_sha256": sha256_file(review_path)}],
        "aggregate_fingerprint": sha256_file(review_path),
    }
    write_json(DEFAULT_OUTPUT / "run_manifest.json", manifest)
    print(json.dumps(audit, indent=2, ensure_ascii=True))
    return 0 if audit["decision"] == "preflight_passed_paid_successor_still_closed" else 1


if __name__ == "__main__":
    raise SystemExit(main())