#!/usr/bin/env python3
"""Prepare the Phase 1M Plus preflight without network or client output caps."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase1m_plus_capability_preflight_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1m_plus_capability_preflight_v1"


class PreflightError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return digest_bytes(payload.encode())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        value = path.relative_to(ROOT)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


def build_plan() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    execution = config["execution"]
    if execution["network_calls_allowed"] or execution["provider_calls"]:
        raise PreflightError("Phase 1M must remain zero-network")
    if execution.get("omit_max_tokens") is not True:
        raise PreflightError("Phase 1M must omit the client output cap")

    source_path = ROOT / config["source"]["request_plan"]
    if digest_file(source_path) != config["source"]["request_plan_sha256"]:
        raise PreflightError("frozen Phase 1K request plan hash mismatch")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    indices = config["source"]["selected_request_indices"]
    if indices != [1, 2] or len(source) != 4:
        raise PreflightError("frozen Flash request selection changed")
    selected = [source[index - 1] for index in indices]

    plan = []
    for source_item in selected:
        request = deepcopy(source_item["request"])
        source_had_max_tokens = "max_tokens" in request
        request.pop("max_tokens", None)
        request["model"] = execution["model_id"]
        request["temperature"] = execution["temperature"]
        request["enable_thinking"] = execution["enable_thinking"]
        plan.append({
            "model": execution["model_id"],
            "task_family": source_item["task_family"],
            "task_id": source_item["task_id"],
            "request": request,
            "request_hash": stable_hash(request),
            "message_hash": stable_hash(request["messages"]),
            "source_message_hash": stable_hash(source_item["request"]["messages"]),
            "source_had_max_tokens": source_had_max_tokens,
            "max_tokens_omitted": "max_tokens" not in request,
        })

    serialized = json.dumps(plan, ensure_ascii=True)
    golden = "=IF(B1=MAX(B$1:B$3),6/COUNTIF(B$1:B$3,MAX(B$1:B$3)),0)"
    audit = {
        "planned_calls": len(plan),
        "network_calls": 0,
        "paid_api_calls": 0,
        "model": execution["model_id"],
        "task_order": [item["task_family"] for item in plan],
        "unique_request_hashes": len({item["request_hash"] for item in plan}),
        "messages_identical_to_phase1k": all(item["message_hash"] == item["source_message_hash"] for item in plan),
        "source_caps_detected": all(item["source_had_max_tokens"] for item in plan),
        "max_tokens_omitted": all(item["max_tokens_omitted"] and "max_tokens" not in item["request"] for item in plan),
        "office_operand_schema_explicit": "12 objects" in plan[0]["request"]["messages"][0]["content"],
        "spreadsheet_semantics_explicit": "same column" in plan[1]["request"]["messages"][0]["content"],
        "reference_answer_leaked": "2602" in serialized,
        "golden_formula_leaked": golden in serialized,
    }
    audit["preflight_pass"] = (
        audit["planned_calls"] == 2
        and audit["unique_request_hashes"] == 2
        and audit["messages_identical_to_phase1k"]
        and audit["source_caps_detected"]
        and audit["max_tokens_omitted"]
        and audit["office_operand_schema_explicit"]
        and audit["spreadsheet_semantics_explicit"]
        and not audit["reference_answer_leaked"]
        and not audit["golden_formula_leaked"]
    )
    return config, plan, audit


def run_preflight(output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise PreflightError(f"refusing to overwrite immutable artifact: {output}")
    _, plan, audit = build_plan()
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
            "run_id": f'phase1m_plus_{index:02d}_{item["task_family"].lower()}',
            "result_path": relative(request_path),
            "file_sha256": digest_file(request_path),
        })
    manifest = {
        "schema_version": 1,
        "phase": "1M",
        "status": "completed",
        "config_path": relative(CONFIG),
        "config_sha256": digest_file(CONFIG),
        "expected_runs": 2,
        "available_runs": 2,
        "complete_grid": True,
        "network_calls": 0,
        "paid_api_calls": 0,
        "decision": "plus_no_client_cap_preflight_passed_paid_calls_closed",
        "aggregate_fingerprint": digest_file(plan_path),
        "runs": runs,
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(run_preflight(), indent=2))