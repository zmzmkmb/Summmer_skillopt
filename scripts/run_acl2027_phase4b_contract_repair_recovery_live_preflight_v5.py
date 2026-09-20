#!/usr/bin/env python3
"""Freeze the zero-network live contract for the Phase 4B-R4 recovery."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts import run_acl2027_phase4b_contract_repair_recovery_preflight_v4 as recovery
from scripts import audit_acl2027_phase4b_contract_repair_live_v3_1 as terminal

VERSION = 5
CALLS = 28
STAGE_CEILING = 0.30
CUMULATIVE_CEILING = 15.00
ORPHAN_RESERVE = 0.011136
KNOWN_CUMULATIVE = 12.328920
PROJECTED_UPPER = round(KNOWN_CUMULATIVE + ORPHAN_RESERVE + STAGE_CEILING, 6)
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"

CONFIG = ROOT / "configs/acl2027/phase4b_contract_repair_recovery_live_preflight_v5.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4b_contract_repair_recovery_live_preflight_v5.py"
SOURCE = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_preflight_v4"
SOURCE_MANIFEST = SOURCE / "run_manifest.json"
SOURCE_SCHEDULE = SOURCE / "recovery_schedule.json"
SOURCE_PLAN = SOURCE / "combined_analysis_plan.json"
SOURCE_AUTH = SOURCE / "authorization_request.json"
R3_LEDGER = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3/ledger.json"
R3_AUDIT = ROOT / "artifacts/acl2027_phase4b_contract_repair_live_v3/terminal_audit_v3_1.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4b_contract_repair_recovery_live_preflight_v5"
REPORT = ROOT / "paper/acl2027/results/phase4b_contract_repair_recovery_live_preflight_v5.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load(CONFIG)
    source_result, source_request, schedule, combined = recovery.validate()
    if source_result["aggregate_fingerprint"] != cfg["source_recovery"]["aggregate_fingerprint"]:
        raise RuntimeError("R4 source fingerprint drift")
    if len(schedule) != CALLS or len(combined) != 100:
        raise RuntimeError("R4 source coverage drift")
    if source_request["cost_treatment_status"] != "unresolved_due_to_unknown_orphan_usage":
        raise RuntimeError("R4 cost provenance drift")
    if load(R3_AUDIT).get("usage", {}).get("orphan_usage_unknown") is not True:
        raise RuntimeError("R3 orphan usage is unexpectedly resolved")
    records = load(R3_LEDGER)
    observed_max = max(float(row["local_cost_cny"]) for row in records)
    if round(observed_max, 6) != ORPHAN_RESERVE:
        raise RuntimeError("orphan reserve no longer matches observed maximum")
    execution = cfg["execution"]
    if any(value is not False for value in execution.values()):
        raise RuntimeError("R5 execution switches must remain closed")
    authorization = cfg["authorization"]
    if any(authorization.get(key) is not False for key in (
        "receipt_created", "authorization_open", "data_egress_authorized",
        "provider_calls_authorized", "paid_api_authorized",
    )):
        raise RuntimeError("R5 authorization must remain closed")
    contract = cfg["execution_contract"]
    expected = {
        "scope": "phase4b_repaired_development_calibration_recovery_only",
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
        "stage_cost_ceiling_cny": STAGE_CEILING,
        "cumulative_cost_ceiling_cny": CUMULATIVE_CEILING,
        "known_cumulative_cost_lower_bound_cny": KNOWN_CUMULATIVE,
        "orphan_usage_reserve_cny": ORPHAN_RESERVE,
        "projected_known_upper_bound_cny": PROJECTED_UPPER,
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise RuntimeError("R5 exact execution contract drift")
    if PROJECTED_UPPER >= CUMULATIVE_CEILING:
        raise RuntimeError("R5 projected upper bound exceeds cumulative ceiling")
    for key in (
        "terminal_stop_on_first_failed_attempt", "authorization_closes_on_completion_or_terminal_stop",
        "usage_accounting_required", "request_start_ledger_required", "response_ledger_required",
        "hash_chain_required", "exact_prefix_resume_only",
    ):
        if contract.get(key) is not True:
            raise RuntimeError(f"R5 accounting or stop contract drift: {key}")
    if cfg["known_transport_equivalence"] != {
        "unique_transport_payloads_in_combined_grid": 80,
        "duplicate_pair_count": 20,
        "paired_conditions": ["global_only", "contextual_typed"],
        "causal_comparison_identifiable": False,
    }:
        raise RuntimeError("R5 transport-equivalence disclosure drift")
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "live-execution-preflight-passed-closed",
        "authorization_status": authorization["status"],
        "source_recovery_fingerprint": source_result["aggregate_fingerprint"],
        "execution_contract": contract,
        "known_transport_equivalence": cfg["known_transport_equivalence"],
        "recovery_schedule_rows": len(schedule),
        "combined_analysis_rows": len(combined),
        "orphan_usage_unknown": True,
        "authorization_receipt_exists": False,
        "authorization_open_exists": False,
        "execution": execution,
        "forbidden_scope": cfg["forbidden_scope"],
        "bindings": {
            "config_sha256": sha256_file(CONFIG),
            "script_sha256": sha256_file(SCRIPT),
            "test_sha256": sha256_file(TEST),
            "source_manifest_sha256": sha256_file(SOURCE_MANIFEST),
            "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE),
            "source_combined_plan_sha256": sha256_file(SOURCE_PLAN),
            "source_authorization_request_sha256": sha256_file(SOURCE_AUTH),
            "r3_ledger_sha256": sha256_file(R3_LEDGER),
            "r3_terminal_audit_sha256": sha256_file(R3_AUDIT),
        },
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "phase4c_calls": 0,
        "replication_calls": 0,
        "cross_domain_scaling_calls": 0,
        "formal_scaling_calls": 0,
    }
    result["aggregate_fingerprint"] = stable(result)
    statement = (
        "我明确授权执行 Phase 4B-R5 恢复 live execution，绑定 R4 预检指纹 "
        f"{source_result['aggregate_fingerprint']} 和本预检指纹 {{preflight_aggregate_fingerprint}}；"
        "仅发送冻结的 28 行恢复计划，使用 Token Plan Beijing qwen3.7-plus，temperature 0，关闭 thinking，"
        "零重试，不设置 max_tokens，JSON object 响应，每次请求间隔 1 秒。"
        f"本阶段费用上限 CNY {STAGE_CEILING:.2f}，累计费用上限 CNY {CUMULATIVE_CEILING:.2f}；"
        f"已知累计下界 CNY {KNOWN_CUMULATIVE:.6f}，孤儿未知用量按最高已观测单次成本 CNY {ORPHAN_RESERVE:.6f} 预留，"
        f"最坏已知上界 CNY {PROJECTED_UPPER:.6f}。首个失败尝试即终止并自动关闭授权。"
        "不授权 Phase 4C、其他模型、复制实验、跨域扩展或正式扩展。"
    ).format(preflight_aggregate_fingerprint=result["aggregate_fingerprint"])
    request = {
        "schema_version": VERSION,
        "status": "awaiting_exact_explicit_user_authorization",
        "preflight_aggregate_fingerprint": result["aggregate_fingerprint"],
        "source_recovery_fingerprint": source_result["aggregate_fingerprint"],
        "authorization_statement_verbatim": statement,
        "execution_contract": contract,
        "known_transport_equivalence": cfg["known_transport_equivalence"],
        "orphan_transport_repeat_disclosure": source_request["orphan_transport_repeat_disclosure"],
        "forbidden_scope": cfg["forbidden_scope"],
        "receipt_path_if_authorized": "configs/acl2027/phase4b_contract_repair_recovery_user_authorization_receipt_v6.json",
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }
    return result, request


def write_artifact(result: dict[str, Any], request: dict[str, Any]) -> None:
    if ARTIFACT.exists():
        raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
    ARTIFACT.mkdir(parents=True)
    write(ARTIFACT / "run_manifest.json", result)
    write(ARTIFACT / "authorization_request.json", request)
    write(ARTIFACT / "completion_manifest.json", {
        "schema_version": VERSION,
        "experiment": result["experiment"],
        "status": "complete",
        "completion_kind": "zero_network_live_execution_preflight",
        "proposed_calls": CALLS,
        "completed_calls": CALLS,
        "rows": CALLS,
        "provider_calls_executed": 0,
        "authorization_status": result["authorization_status"],
        "aggregate_fingerprint": result["aggregate_fingerprint"],
        "authorization_request_sha256": sha256_file(ARTIFACT / "authorization_request.json"),
    })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "# ACL 2027 Phase 4B-R5 recovery live-execution preflight\n\n"
        "This zero-network preflight binds the closed R4 recovery plan and freezes a 28-call live contract. "
        "It reserves the maximum observed completed-response cost (CNY 0.011136) for the unknown orphan usage, "
        "sets a CNY 0.30 recovery-stage ceiling and a CNY 15.00 cumulative ceiling, and keeps authorization closed.\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n",
        encoding="utf-8", newline="\n",
    )


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
