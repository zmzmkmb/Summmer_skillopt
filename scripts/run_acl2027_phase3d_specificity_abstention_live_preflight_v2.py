#!/usr/bin/env python3
"""Freeze the zero-network Phase 3D live-execution preflight v2."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

VERSION = 2
CALLS = 240
DESIGN_FINGERPRINT = "59143bd2c63bf73c4f747121d547216a2665c7bd722fb7c672b0e12e9db2e5b0"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"
CONDITIONS = (
    "cold",
    "global_only",
    "contextual_single",
    "irrelevant_single",
    "dual_contextual_first",
    "dual_irrelevant_first",
)

CONFIG = ROOT / "configs/acl2027/phase3d_specificity_abstention_live_preflight_v2.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3d_specificity_abstention_live_preflight_v2.py"
TEST = ROOT / "tests/test_acl2027_phase3d_specificity_abstention_live_preflight_v2.py"
SOURCE = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_preflight_v1"
SOURCE_MANIFEST = SOURCE / "run_manifest.json"
SOURCE_SCHEDULE = SOURCE / "specificity_schedule.json"
SOURCE_GOLD = SOURCE / "specificity_private_gold.json"
SOURCE_ANALYSIS = SOURCE / "analysis_plan.json"
SOURCE_COMPLETION = SOURCE / "completion_manifest.json"
RECEIPT = ROOT / "configs/acl2027/phase3d_specificity_abstention_user_authorization_receipt_v3.json"
LIVE_ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_v3"
AUTH_OPEN = LIVE_ARTIFACT / "authorization_open.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase3d_specificity_abstention_live_preflight_v2"
REPORT = ROOT / "paper/acl2027/results/phase3d_specificity_abstention_live_preflight_v2.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def schedule_rows() -> list[dict[str, Any]]:
    document = load(SOURCE_SCHEDULE)
    rows = document.get("schedule")
    if not isinstance(rows, list):
        raise RuntimeError("Phase 3D v1 schedule is not a list")
    return rows


def validate_schedule(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != CALLS:
        raise RuntimeError("Phase 3D v1 schedule row-count drift")
    sequences = [row.get("sequence") for row in rows]
    if sequences != list(range(1, CALLS + 1)):
        raise RuntimeError("Phase 3D v1 sequence drift")
    logical_ids = [str(row.get("logical_call_id")) for row in rows]
    request_hashes = [str(row.get("request_hash")) for row in rows]
    if len(set(logical_ids)) != CALLS or len(set(request_hashes)) != CALLS:
        raise RuntimeError("Phase 3D v1 request identities are not unique")
    for row in rows:
        body = row.get("canonical_request_body")
        if not isinstance(body, dict) or stable(body) != row.get("request_hash"):
            raise RuntimeError(f"canonical request hash drift at sequence {row.get('sequence')}")
        expected = {
            "model_id": MODEL,
            "temperature": 0,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
        }
        if any(body.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"canonical request contract drift at sequence {row.get('sequence')}")
        if "max_tokens" in body:
            raise RuntimeError(f"max_tokens unexpectedly present at sequence {row.get('sequence')}")
    task_ids = {str(row["task_id"]) for row in rows}
    condition_counts = Counter(str(row["condition"]) for row in rows)
    if len(task_ids) != 40 or condition_counts != Counter({condition: 40 for condition in CONDITIONS}):
        raise RuntimeError("Phase 3D v1 task-grid balance drift")
    return {
        "rows": len(rows),
        "tasks": len(task_ids),
        "unique_logical_call_ids": len(set(logical_ids)),
        "unique_request_hashes": len(set(request_hashes)),
        "condition_counts": dict(sorted(condition_counts.items())),
        "canonical_schedule_sha256": stable(rows),
    }


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load(CONFIG)
    source_manifest = load(SOURCE_MANIFEST)
    source_completion = load(SOURCE_COMPLETION)
    if source_manifest.get("aggregate_fingerprint") != DESIGN_FINGERPRINT:
        raise RuntimeError("Phase 3D design fingerprint drift")
    if source_completion.get("aggregate_fingerprint") != DESIGN_FINGERPRINT:
        raise RuntimeError("Phase 3D completion fingerprint drift")
    if source_manifest.get("status") != "design-preflight-passed-closed":
        raise RuntimeError("Phase 3D design is not closed and complete")
    if source_completion.get("provider_calls_executed") != 0:
        raise RuntimeError("Phase 3D source unexpectedly contains provider execution")
    if cfg.get("status") != "zero_network_live_execution_preflight_closed":
        raise RuntimeError("v2 preflight status drift")
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("v2 execution switches must remain closed")
    authorization = cfg["authorization"]
    if authorization.get("receipt_created") is not False or authorization.get("authorization_open") is not False:
        raise RuntimeError("v2 authorization must remain closed")
    if any(authorization.get(key) is not False for key in (
        "data_egress_authorized", "provider_calls_authorized", "paid_api_authorized"
    )):
        raise RuntimeError("v2 authorization permissions must remain false")
    if RECEIPT.exists() or AUTH_OPEN.exists():
        raise RuntimeError("Phase 3D v3 authorization receipt or open authorization already exists")

    contract = cfg["execution_contract"]
    expected_contract = {
        "scope": "phase3d_specificity_abstention_only",
        "endpoint": ENDPOINT,
        "model_id": MODEL,
        "authorized_calls": CALLS,
        "max_provider_attempts": CALLS,
        "temperature": 0,
        "enable_thinking": False,
        "retries": 0,
        "max_tokens_present": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "stage_cost_ceiling_cny": 3.0,
        "cumulative_cost_ceiling_cny": 15.0,
        "known_cumulative_cost_lower_bound_cny": 7.218738,
    }
    if any(contract.get(key) != value for key, value in expected_contract.items()):
        raise RuntimeError("v2 exact execution contract drift")
    if contract.get("payload_classes") != [
        "frozen_task_prompts",
        "frozen_task_contexts",
        "frozen_historical_skill_candidate_bundles",
    ]:
        raise RuntimeError("v2 payload egress classes drift")
    if any(contract.get(key) is not True for key in (
        "terminal_stop_on_first_failed_attempt",
        "authorization_closes_on_completion_or_terminal_stop",
        "usage_accounting_required",
        "request_start_ledger_required",
        "response_ledger_required",
        "hash_chain_required",
        "exact_prefix_resume_only",
    )):
        raise RuntimeError("v2 safety or accounting contract drift")

    audit = validate_schedule(schedule_rows())
    bindings = {
        "config_sha256": sha256_file(CONFIG),
        "script_sha256": sha256_file(SCRIPT),
        "test_sha256": sha256_file(TEST),
        "source_manifest_sha256": sha256_file(SOURCE_MANIFEST),
        "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE),
        "source_private_gold_sha256": sha256_file(SOURCE_GOLD),
        "source_analysis_plan_sha256": sha256_file(SOURCE_ANALYSIS),
        "source_completion_manifest_sha256": sha256_file(SOURCE_COMPLETION),
        "source_schedule_canonical_sha256": audit["canonical_schedule_sha256"],
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "live-execution-preflight-passed-closed",
        "authorization_status": "fresh-explicit-user-authorization-required",
        "phase3d_design_fingerprint": DESIGN_FINGERPRINT,
        "schedule_audit": audit,
        "execution_contract": contract,
        "forbidden_scope": cfg["forbidden_scope"],
        "bindings": bindings,
        "authorization_receipt_exists": False,
        "authorization_open_exists": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "later_stage_calls": 0,
        "cross_domain_scaling_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    statement = authorization["authorization_statement_template"].format(
        preflight_aggregate_fingerprint=result["aggregate_fingerprint"]
    )
    request = {
        "schema_version": VERSION,
        "status": "awaiting_exact_explicit_user_authorization",
        "phase3d_design_fingerprint": DESIGN_FINGERPRINT,
        "preflight_aggregate_fingerprint": result["aggregate_fingerprint"],
        "authorization_statement_verbatim": statement,
        "execution_contract": contract,
        "forbidden_scope": cfg["forbidden_scope"],
        "receipt_path_if_authorized": str(RECEIPT.relative_to(ROOT)).replace("\\", "/"),
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }
    return result, request


def report_text(result: dict[str, Any], request: dict[str, Any]) -> str:
    return f"""# ACL 2027 Phase 3D live-execution preflight v2

This zero-network preflight binds the completed Phase 3D v1 specificity schedule without changing any of its 240 canonical request identities. It freezes the Token Plan endpoint, `qwen3.7-plus`, temperature 0, thinking disabled, zero retries, absent `max_tokens`, JSON-object responses, one-second pacing, CNY 3.00 stage ceiling, and CNY 15.00 cumulative ceiling.

The authorization receipt and live authorization do not exist. All network, provider, model, paid, later-stage, cross-domain, and formal-scaling counters remain zero. A first failed provider attempt must terminate the stage and close authorization automatically.

Preflight aggregate fingerprint: `{result['aggregate_fingerprint']}`.

## Exact authorization required

{request['authorization_statement_verbatim']}
"""


def write_artifact(result: dict[str, Any], request: dict[str, Any]) -> None:
    if ARTIFACT.exists():
        raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
    ARTIFACT.mkdir(parents=True)
    write(ARTIFACT / "schedule_binding_audit.json", result["schedule_audit"])
    write(ARTIFACT / "authorization_request.json", request)
    write(ARTIFACT / "run_manifest.json", result)
    write(ARTIFACT / "completion_manifest.json", {
        "schema_version": VERSION,
        "experiment": result["experiment"],
        "status": "complete",
        "completion_kind": "zero_network_live_execution_preflight",
        "schedule_rows_bound": CALLS,
        "provider_calls_executed": 0,
        "authorization_status": result["authorization_status"],
        "aggregate_fingerprint": result["aggregate_fingerprint"],
        "authorization_request_sha256": sha256_file(ARTIFACT / "authorization_request.json"),
    })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(result, request), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result, request = validate()
    if args.write_artifact:
        write_artifact(result, request)
    print(render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
