#!/usr/bin/env python3
"""Phase 2 v8 exact-JSON calibration-only runner."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT_HINT = Path(__file__).resolve().parents[1]
if str(ROOT_HINT) not in sys.path:
    sys.path.insert(0, str(ROOT_HINT))

from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import (
    HardStop,
    _seal_record,
    atomic_write_ledger,
    cost,
    load,
    sha256_file,
    stable,
    usage,
)
from scripts.run_acl2027_phase2_calibration_prompt_repair_preflight_v8 import (
    ARTIFACT,
    CONFIG,
    SCHEDULE,
    build_manifest,
    validate_config,
)

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_MANIFEST = ARTIFACT / "run_manifest.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
TOKEN_PLAN_ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"


def schedule_rows() -> list[dict[str, Any]]:
    return load(SCHEDULE)["schedule"]


def required_bindings() -> dict[str, str]:
    manifest = load(PREFLIGHT_MANIFEST)
    return {
        "prompt_preflight_config_sha256": sha256_file(CONFIG),
        "prompt_preflight_manifest_sha256": sha256_file(PREFLIGHT_MANIFEST),
        "parent_v6_route_manifest_sha256": manifest["v6_route_manifest_sha256"],
        "schedule_sha256": sha256_file(SCHEDULE),
        "adapter_sha256": manifest["adapter_sha256"],
        "runner_sha256": manifest["runner_sha256"],
    }


def validate_execution_preflight() -> dict[str, Any]:
    config = validate_config()
    manifest = load(PREFLIGHT_MANIFEST)
    if manifest != build_manifest():
        raise HardStop("v8 prompt preflight manifest drift")
    if manifest["status"] != "preflight-passed-closed" or any(manifest["counters"].values()):
        raise HardStop("v8 prompt preflight not closed")
    return config


def validate_authorization(auth: dict[str, Any], auth_sha: str) -> None:
    if auth.get("bindings") != required_bindings():
        raise HardStop("v6 authorization binding drift")
    exact = {
        "authorized_stage": "calibration",
        "authorized_calls": 60,
        "stage_call_ceiling": 60,
        "max_provider_attempts": 60,
        "stage_cost_ceiling_cny": 0.5,
        "cumulative_cost_ceiling_cny": 0.5,
        "model_id": "qwen3.7-plus",
        "endpoint": TOKEN_PLAN_ENDPOINT,
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "retries": 0,
        "max_tokens_present": False,
        "formal_scaling_allowed": False,
    }
    if any(auth.get(key) != value for key, value in exact.items()):
        raise HardStop("v6 authorization boundary drift")
    if set(auth.get("forbidden_stages", [])) != {"development_acquisition", "formal_history", "probe", "held_out", "formal_scaling"}:
        raise HardStop("v6 authorization scope drift")
    if auth.get("status") != "open" or not all(auth.get(key) is True for key in (
        "paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open"
    )):
        raise HardStop("v6 authorization is not open")
    if not isinstance(auth_sha, str) or len(auth_sha) != 64:
        raise HardStop("v6 authorization hash drift")


def resolve_registry(registry_path: Path) -> dict[str, tuple[dict[str, Any], str]]:
    resolved: dict[str, tuple[dict[str, Any], str]] = {}
    for auth_id, item in load(registry_path).get("authorizations", {}).items():
        path = (registry_path.parent / item["path"]).resolve()
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise HardStop("v6 authorization registry drift")
        auth = load(path)
        if auth.get("authorization_id") != auth_id:
            raise HardStop("v6 authorization identity drift")
        validate_authorization(auth, item["sha256"])
        resolved[auth_id] = (auth, item["sha256"])
    return resolved


def validate_prefix(records: list[dict[str, Any]], registry_path: Path) -> dict[str, tuple[dict[str, Any], str]]:
    calibration = schedule_rows()[:60]
    if len(records) > 60:
        raise HardStop("v6 calibration prefix too long", records)
    registry = resolve_registry(registry_path)
    previous = None
    seen: set[str] = set()
    for expected, record in zip(calibration, records):
        for key in ("logical_call_id", "request_hash", "partition", "original_call_index", "staged_execution_index"):
            if record.get(key) != expected.get(key):
                raise HardStop("v6 non-prefix resume", records)
        if record["logical_call_id"] in seen:
            raise HardStop("v6 duplicate logical request", records)
        seen.add(record["logical_call_id"])
        auth_id = record.get("authorization_id")
        if auth_id not in registry or record.get("authorization_sha256") != registry[auth_id][1]:
            raise HardStop("v6 ledger authorization drift", records)
        if record.get("previous_ledger_entry_sha256") != previous:
            raise HardStop("v6 ledger hash chain drift", records)
        entry_hash = record.get("ledger_entry_sha256")
        if entry_hash != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("v6 ledger hash chain drift", records)
        previous = entry_hash
        if record.get("terminal"):
            raise HardStop("v6 terminal ledger is not resumable", records)
        usage(record)
    return registry


def execute_calibration(
    registry_path: Path,
    authorization_id: str,
    ledger_path: Path,
    provider: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    interrupt_after: int | None = None,
) -> list[dict[str, Any]]:
    validate_execution_preflight()
    records = load(ledger_path) if ledger_path.exists() else []
    registry = validate_prefix(records, registry_path)
    if authorization_id not in registry:
        raise HardStop("v6 current authorization missing", records)
    auth, auth_sha = registry[authorization_id]
    calibration = schedule_rows()[:60]
    config = load(V4_CONFIG)
    while len(records) < 60:
        row = calibration[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if (
            "max_tokens" in body
            or body.get("model_id") != "qwen3.7-plus"
            or body.get("temperature") != 0
            or body.get("response_format") != {"type": "json_object"}
            or body.get("prompt_template_version") != "phase2-prompt-v8-exact-json"
        ):
            raise HardStop("v8 request boundary drift", records)
        base = {key: row[key] for key in (
            "logical_call_id", "request_hash", "partition", "task_id", "skill_family", "condition", "payload_hash", "original_call_index", "staged_execution_index"
        )}
        base.update(
            authorization_id=authorization_id,
            authorization_sha256=auth_sha,
            authorized_stage="calibration",
            request_id=None,
            retries=0,
            max_tokens_present=False,
            previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None,
        )
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            raw = response.get("content")
            if not isinstance(raw, str):
                raise HardStop("provider response missing raw content")
            provider_response = response.get("raw_provider_response", response)
            record = {
                **base,
                "raw_response": raw,
                "raw_response_sha256": stable(raw),
                "raw_provider_response": provider_response,
                "raw_provider_response_sha256": stable(provider_response),
                "usage": exact,
                "terminal": False,
                "status": "completed",
                "error": None,
            }
            if response.get("request_id") is not None:
                record["request_id"] = response["request_id"]
        except Exception as exc:
            provider_response = response.get("raw_provider_response", response) if isinstance(response, dict) else None
            record = {
                **base,
                "raw_response": response.get("content") if isinstance(response, dict) else None,
                "raw_response_sha256": stable(response.get("content") if isinstance(response, dict) else None),
                "raw_provider_response": provider_response,
                "raw_provider_response_sha256": stable(provider_response),
                "usage": response.get("usage") if isinstance(response, dict) else None,
                "terminal": True,
                "status": "hard_stop",
                "error": f"{type(exc).__name__}: {exc}",
            }
        _seal_record(record)
        records.append(record)
        atomic_write_ledger(ledger_path, records)
        if interrupt_after is not None and len(records) == interrupt_after:
            raise KeyboardInterrupt("simulated interruption after durable append")
        if record["terminal"]:
            raise HardStop(record["error"], records)
        if cost(config, records) > auth["stage_cost_ceiling_cny"] or cost(config, records) > auth["cumulative_cost_ceiling_cny"]:
            records[-1]["terminal"] = True
            records[-1]["status"] = "hard_stop"
            records[-1]["error"] = "v8 cost ceiling exceeded"
            _seal_record(records[-1])
            atomic_write_ledger(ledger_path, records)
            raise HardStop(records[-1]["error"], records)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("preflight")
    live = sub.add_parser("execute")
    live.add_argument("--registry", type=Path, required=True)
    live.add_argument("--authorization-id", required=True)
    live.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    if args.command in (None, "preflight"):
        validate_execution_preflight()
        print(json.dumps({"status": "preflight-passed-closed", "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}, indent=2))
        return 0
    registry = resolve_registry(args.registry)
    if args.authorization_id not in registry:
        raise HardStop("v6 current authorization missing")
    provider = QwenTokenPlanProviderAdapter(registry[args.authorization_id][0])
    records = execute_calibration(args.registry, args.authorization_id, args.ledger, provider)
    print(json.dumps({"status": "calibration-complete", "rows": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
