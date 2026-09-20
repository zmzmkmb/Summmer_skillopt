#!/usr/bin/env python3
"""Prepare the Phase 1K four-request paired-model preflight without network access."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase1k_paired_model_capability_preflight_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1k_paired_model_capability_preflight_v1"
SOURCE_HASH = "5e20d5e6be71cc1bd5c796cbbd26c6e720f3eeed77fe31bf41c0413d06e679d9"
CONTRACT_HASH = "02949d5d30c9ceedbba50bbec7cd4acd073a8dbf42ce39235b1d1778406b98bb"


class PreflightError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def stable_hash(value: Any) -> str:
    return digest_bytes(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def manifest_path(path: Path) -> str:
    try:
        value = path.relative_to(ROOT)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


def build_plan() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["execution"]["network_calls_allowed"] or config["execution"]["provider_calls"]:
        raise PreflightError("Phase 1K must remain zero-network")
    source_path = ROOT / config["source_preflight"]["request_plan"]
    contract_path = ROOT / config["source_preflight"]["phase1j_contracts"]
    if digest_file(source_path) != SOURCE_HASH or digest_file(contract_path) != CONTRACT_HASH:
        raise PreflightError("frozen source hash mismatch")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    by_family = {item["task_family"]: item for item in source}
    office = deepcopy(by_family["OfficeQA"]["request"])
    office["messages"][0]["content"] = (
        "Answer only from the supplied source excerpt. Return JSON only with exactly answer, evidence, and calculation. "
        "evidence must contain exactly 12 items with source_path, locator, period, and value. calculation must contain "
        "operation, time_basis, operands, and result. operands must contain exactly 12 objects, each with only period "
        "and value, and must match evidence one-to-one. Use calendar time_basis. Independently verify the sum. The "
        "answer, calculation result, and evidence sum must agree. No markdown."
    )
    office["max_tokens"] = config["tasks"]["OfficeQA"]["max_output_tokens"]
    sheet = deepcopy(by_family["SpreadsheetBench"]["request"])
    sheet["messages"][0]["content"] = (
        "Return JSON only with exactly target_range, edits, and explanation. target_range must be B5:E7. edits must "
        "contain exactly one compact object with sheet, cell, and formula for each of the 12 cells, no duplicates. "
        "For each output column independently, compare the three people in that same column; never use a maximum "
        "over the full B1:D3 block. explanation must be at most 160 characters. No markdown or extra keys."
    )
    sheet["max_tokens"] = config["tasks"]["SpreadsheetBench"]["max_output_tokens"]
    plan = []
    for model in config["models"]:
        for family, base in (("OfficeQA", office), ("SpreadsheetBench", sheet)):
            request = deepcopy(base)
            request["model"] = model
            request["temperature"] = 0
            request["enable_thinking"] = False
            task_id = config["tasks"][family]["task_id"]
            content_only = {key: value for key, value in request.items() if key != "model"}
            plan.append({
                "model": model,
                "task_family": family,
                "task_id": task_id,
                "request": request,
                "request_hash": stable_hash(request),
                "content_hash_excluding_model": stable_hash(content_only),
            })
    golden = "=IF(B1=MAX(B$1:B$3),6/COUNTIF(B$1:B$3,MAX(B$1:B$3)),0)"
    serialized = json.dumps(plan, ensure_ascii=True)
    audit = {
        "planned_calls": len(plan),
        "network_calls": 0,
        "paid_api_calls": 0,
        "models": config["models"],
        "task_order": [f'{item["model"]}/{item["task_family"]}' for item in plan],
        "unique_request_hashes": len({item["request_hash"] for item in plan}),
        "office_content_fair": plan[0]["content_hash_excluding_model"] == plan[2]["content_hash_excluding_model"],
        "spreadsheet_content_fair": plan[1]["content_hash_excluding_model"] == plan[3]["content_hash_excluding_model"],
        "office_operand_schema_explicit": all("12 objects" in item["request"]["messages"][0]["content"] for item in (plan[0], plan[2])),
        "spreadsheet_semantics_explicit": all("same column" in item["request"]["messages"][0]["content"] for item in (plan[1], plan[3])),
        "reference_answer_leaked": "2602" in serialized,
        "golden_formula_leaked": golden in serialized,
    }
    audit["preflight_pass"] = (
        audit["planned_calls"] == 4
        and audit["unique_request_hashes"] == 4
        and audit["office_content_fair"]
        and audit["spreadsheet_content_fair"]
        and audit["office_operand_schema_explicit"]
        and audit["spreadsheet_semantics_explicit"]
        and not audit["reference_answer_leaked"]
        and not audit["golden_formula_leaked"]
    )
    return config, plan, audit


def run_preflight(output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise PreflightError(f"refusing to overwrite immutable artifact: {output}")
    config, plan, audit = build_plan()
    if not audit["preflight_pass"]:
        raise PreflightError(f"preflight audit failed: {audit}")
    output.mkdir(parents=True)
    plan_path = output / "request_plan.json"
    audit_path = output / "audit.json"
    write_json(plan_path, plan)
    write_json(audit_path, audit)
    runs = []
    for index, item in enumerate(plan, 1):
        request_path = output / f"request_{index:02d}.json"
        write_json(request_path, item)
        runs.append({
            "run_id": f'phase1k_{item["model"].replace(".", "_")}_{item["task_family"].lower()}',
            "result_path": manifest_path(request_path),
            "file_sha256": digest_file(request_path),
        })
    manifest = {
        "schema_version": 1, "phase": "1K", "status": "completed",
        "config_path": str(CONFIG.relative_to(ROOT)).replace("\\", "/"), "config_sha256": digest_file(CONFIG),
        "expected_runs": 4, "available_runs": 4, "complete_grid": True,
        "network_calls": 0, "paid_api_calls": 0, "decision": "paired_model_preflight_passed_paid_confirmation_closed",
        "aggregate_fingerprint": digest_file(plan_path),
        "runs": runs,
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(run_preflight(), indent=2))
