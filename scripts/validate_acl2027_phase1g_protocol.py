#!/usr/bin/env python3
"""Run the zero-call ACL 2027 Phase 1G protocol preflight."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from skillopt.evaluation.cross_task_protocol import (
    ProtocolError,
    apply_spreadsheet_edits,
    parse_json_object_preserving_raw,
    target_cells,
    validate_officeqa_trace,
    validate_spreadsheet_edits,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase1g_cross_task_protocol_repair_v1.json"
OUTPUT_DIR = ROOT / "artifacts/acl2027_phase1g_cross_task_protocol_repair_v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _golden_edits(task_dir: Path, answer_position: str) -> dict[str, Any]:
    golden = next(task_dir.glob("*_golden.xlsx"))
    workbook = load_workbook(golden, data_only=False, read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    edits = [{"sheet": sheet.title, "cell": cell, "formula": sheet[cell].value} for cell in target_cells(answer_position)]
    workbook.close()
    return {"target_range": answer_position, "edits": edits, "explanation": "development-gold executable trace"}


def audit(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    execution = config["execution"]
    if any(execution[key] for key in ("paid_api_allowed", "formal_scaling_allowed", "network_calls_allowed")):
        raise ProtocolError("Phase 1G must remain no-paid and offline")

    val_items = read_json(ROOT / "data/officeqa_id_split/val/items.json")
    val_by_id = {str(item["id"]): item for item in val_items}
    with (ROOT / config["officeqa"]["payload_csv"]).open(encoding="utf-8-sig", newline="") as handle:
        payload_by_id = {str(row["uid"]): row for row in csv.DictReader(handle)}
    samples = config["officeqa"]["development_samples"]
    selected_ids = [sample["id"] for sample in samples]
    selected_valid = all(item_id in val_by_id and item_id in payload_by_id for item_id in selected_ids)
    difficulty_counts = {level: sum(s["difficulty"] == level for s in samples) for level in ("easy", "hard")}
    scope_counts = {scope: sum(s["document_scope"] == scope for s in samples) for scope in ("single", "multi")}

    correct_trace = {
        "answer": "2602",
        "evidence": [{"source_path": "treasury_bulletin_1941_01.txt", "locator": f"month-{month:02d}", "period": f"1940-{month:02d}", "value": 1} for month in range(1, 13)],
        "calculation": {"operation": "sum", "time_basis": "calendar", "operands": [{"period": f"1940-{month:02d}", "value": 1} for month in range(1, 13)], "result": 2602},
    }
    fiscal_trace = json.loads(json.dumps(correct_trace))
    fiscal_trace["calculation"]["time_basis"] = "fiscal"
    fiscal_trace["calculation"]["operands"] = [{"period": "FY1940", "value": 1580}]
    temporal_ok = validate_officeqa_trace(correct_trace, required_time_basis="calendar", expected_period_count=12)
    temporal_bad = validate_officeqa_trace(fiscal_trace, required_time_basis="calendar", expected_period_count=12)

    phase1f_results = ROOT / "artifacts/acl2027_phase1f_real_cross_task_triage_pilot_v1/bounded_smoke_20260810/results.jsonl"
    raw_records = [json.loads(line) for line in phase1f_results.read_text(encoding="utf-8").splitlines()]
    spreadsheet_raw = next(row["raw_text"] for row in raw_records if row["task_family"] == "SpreadsheetBench")
    normalized = parse_json_object_preserving_raw(spreadsheet_raw)

    dataset = read_json(ROOT / config["spreadsheetbench"]["payload_dataset"])
    item = next(row for row in dataset if str(row["id"]) == config["spreadsheetbench"]["development_ids"][0])
    task_dir = ROOT / "data/spreadsheetbench_verified_400" / item["spreadsheet_path"]
    initial = next(task_dir.glob("*_init.xlsx"))
    spreadsheet_payload = _golden_edits(task_dir, item["answer_position"])
    spreadsheet_check = validate_spreadsheet_edits(spreadsheet_payload, expected_target_range=item["answer_position"])
    output_workbook = output_dir / "preflight_45635.xlsx"
    apply_spreadsheet_edits(initial, output_workbook, spreadsheet_payload)

    checks = {
        "no_paid_network_or_scaling": True,
        "officeqa_selected_ids_are_val": selected_valid,
        "officeqa_development_count": len(samples) == config["officeqa"]["development_count"] == 8,
        "officeqa_balanced_difficulty": difficulty_counts == {"easy": 4, "hard": 4},
        "officeqa_has_single_and_multi_document": all(scope_counts[value] > 0 for value in scope_counts),
        "temporal_correct_trace_eligible": temporal_ok["eligible_for_gate"],
        "fiscal_calendar_mismatch_blocked": not temporal_bad["eligible_for_gate"],
        "phase1f_key_whitespace_normalized_with_provenance": normalized.normalizations == ({"raw_key": " explanation", "normalized_key": "explanation"},),
        "legacy_spreadsheet_shape_still_not_accepted": "edits" not in normalized.value,
        "spreadsheet_exact_per_cell_coverage": spreadsheet_check["exact_coverage"],
        "spreadsheet_workbook_materialized": output_workbook.is_file(),
    }
    return {
        "analysis": "phase1g_zero_call_protocol_preflight",
        "selected_officeqa_ids": selected_ids,
        "officeqa_strata": {"difficulty": difficulty_counts, "document_scope": scope_counts},
        "temporal_diagnostics": {"correct_trace": temporal_ok, "fiscal_trace": temporal_bad},
        "normalization_audit": {"raw_text_sha256": hashlib.sha256(spreadsheet_raw.encode()).hexdigest(), "changes": list(normalized.normalizations)},
        "spreadsheet": {**spreadsheet_check, "output_workbook": (str(output_workbook.relative_to(ROOT)).replace("\\", "/") if output_workbook.is_relative_to(ROOT) else str(output_workbook))},
        "checks": checks,
        "decision": "local_protocol_passed_paid_smoke_still_closed" if all(checks.values()) else "local_protocol_failed_paid_smoke_closed",
        "network_calls": 0,
        "paid_api_calls": 0,
    }


def main() -> int:
    if OUTPUT_DIR.exists():
        raise SystemExit(f"refusing to overwrite immutable artifact: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True)
    config = read_json(CONFIG_PATH)
    result = audit(config, OUTPUT_DIR)
    audit_path = OUTPUT_DIR / "protocol_audit.json"
    audit_path.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256_file(CONFIG_PATH),
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": True,
        "analysis_only": True,
        "network_calls": 0,
        "paid_api_calls": 0,
        "runs": [{"run_id": "phase1g_zero_call_preflight", "status": "completed", "result_path": str(audit_path.relative_to(ROOT)).replace("\\", "/"), "file_sha256": sha256_file(audit_path)}],
        "aggregate_fingerprint": sha256_file(audit_path),
    }
    (OUTPUT_DIR / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["decision"] == "local_protocol_passed_paid_smoke_still_closed" else 1


if __name__ == "__main__":
    raise SystemExit(main())