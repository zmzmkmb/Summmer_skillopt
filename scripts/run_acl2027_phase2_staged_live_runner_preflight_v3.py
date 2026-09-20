#!/usr/bin/env python3
"""Phase 2 v3 closed preflight and crash-durable staged runner.

The default command is local preflight. Provider execution is deliberately an
explicit API used by tests or a separately authorized operator process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from scripts.analyze_acl2027_phase2_probe_v3 import ProbeAnalysisError, build_probe_audit
from scripts.materialize_acl2027_phase2_candidates_v3 import MaterializationError, build_candidate_artifact

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v3.json"
AUTH = ROOT / "configs/acl2027/phase2_staged_live_runner_authorization_closed_v3.json"
SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
LEDGER_NAME = "ledger.json"
STAGES = ("calibration", "development_acquisition", "formal_history", "probe", "held_out")
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")


class HardStop(RuntimeError):
    def __init__(self, message: str, ledger: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.ledger = ledger or []


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def stable(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schedule_rows() -> list[dict[str, Any]]:
    return load(SCHEDULE)["schedule"]


def usage(response: Any) -> dict[str, int]:
    value = response.get("usage") if isinstance(response, dict) else None
    keys = ("input_tokens", "output_tokens", "total_tokens")
    if not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] < 0 for k in keys):
        raise HardStop("unknown/missing/invalid usage")
    if value["input_tokens"] + value["output_tokens"] != value["total_tokens"]:
        raise HardStop("unknown/missing/invalid usage")
    return {k: value[k] for k in keys}


def cost(config: dict[str, Any], records: list[dict[str, Any]]) -> float:
    rate = config["cost_control"]
    return sum(r["usage"]["input_tokens"] * rate["input_cny_per_million"] + r["usage"]["output_tokens"] * rate["output_cny_per_million"] for r in records) / 1_000_000


def atomic_write_ledger(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(records, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _auth_registry(registry_path: Path) -> dict[str, tuple[dict[str, Any], str]]:
    doc = load(registry_path)
    resolved = {}
    for auth_id, item in doc.get("authorizations", {}).items():
        path = (registry_path.parent / item["path"]).resolve()
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise HardStop("authorization registry cannot resolve historical authorization")
        auth = load(path)
        if auth.get("authorization_id") != auth_id:
            raise HardStop("authorization registry identity drift")
        resolved[auth_id] = (auth, item["sha256"])
    return resolved


def validate_config(config: dict[str, Any]) -> None:
    if config != load(CONFIG):
        raise HardStop("preflight config hash drift")
    if any(config["execution"].get(k) is not False for k in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("v3 execution switches must remain closed")
    if config["model_route"] != {"model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False, "endpoint_route": "dashscope-compatible-mode-chat-completions"}:
        raise HardStop("model/temperature/route drift")
    if sha256_file(SCHEDULE) != config["schedule_binding"]["sha256"]:
        raise HardStop("schedule hash drift")
    for binding in config["frozen_bindings"].values():
        path = ROOT / binding["path"]
        if sha256_file(path) != binding["sha256"]:
            raise HardStop("freeze/config/plan/partition hash drift")


def validate_authorization(config: dict[str, Any], auth: dict[str, Any], auth_sha: str, stage: str | None = None) -> None:
    required_bindings = {
        "preflight_config_sha256": sha256_file(CONFIG),
        "schedule_sha256": config["schedule_binding"]["sha256"],
        "freeze_config_sha256": config["frozen_bindings"]["freeze_config"]["sha256"],
        "request_plan_sha256": config["frozen_bindings"]["request_plan"]["sha256"],
        "partition_audit_sha256": config["frozen_bindings"]["partition_audit"]["sha256"],
    }
    if auth.get("bindings") != required_bindings:
        raise HardStop("authorization hash binding drift")
    route = config["model_route"]
    for key in ("model_id", "temperature", "retries", "max_tokens_present", "endpoint_route"):
        if auth.get(key) != route[key]:
            raise HardStop("authorization model/temperature/route drift")
    if auth.get("formal_scaling_allowed") is not False:
        raise HardStop("formal scaling authorization drift")
    authorized_stage = auth.get("authorized_stage")
    if stage is not None and authorized_stage != stage:
        raise HardStop("stage not authorized")
    calls = auth.get("authorized_calls")
    stage_calls = auth.get("stage_call_ceiling")
    stage_cost = auth.get("stage_cost_ceiling_cny")
    cumulative = auth.get("cumulative_cost_ceiling_cny")
    if type(calls) is not int or type(stage_calls) is not int or calls < 0 or stage_calls < 0:
        raise HardStop("invalid authorization call ceiling")
    if authorized_stage is not None:
        if authorized_stage not in STAGES or calls > stage_calls or stage_calls > config["stages"][authorized_stage]:
            raise HardStop("invalid authorization call ceiling")
        if not isinstance(stage_cost, (int, float)) or stage_cost < 0 or stage_cost > config["cost_control"]["stage_ceilings_cny"][authorized_stage]:
            raise HardStop("invalid stage cost ceiling")
    if not isinstance(cumulative, (int, float)) or cumulative < 0 or cumulative > config["cost_control"]["cumulative_ceiling_cny"]:
        raise HardStop("invalid cumulative cost ceiling")
    if auth.get("status") == "closed_preflight":
        if authorized_stage is not None or calls or stage_calls or stage_cost or cumulative or any(
            auth.get(key) is not False for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")
        ):
            raise HardStop("closed authorization drift")
    elif auth.get("status") != "open":
        raise HardStop("authorization lifecycle status invalid")
    if not isinstance(auth_sha, str) or len(auth_sha) != 64:
        raise HardStop("authorization hash drift")


def _seal_record(record: dict[str, Any]) -> None:
    record["ledger_entry_sha256"] = stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"})


def validate_prefix(schedule: list[dict[str, Any]], records: list[dict[str, Any]], registry_path: Path) -> dict[str, tuple[dict[str, Any], str]]:
    if len(records) > len(schedule):
        raise HardStop("non staged exact-prefix resume", records)
    registry = _auth_registry(registry_path)
    seen = set()
    previous_hash = None
    for expected, record in zip(schedule, records):
        for key in ("logical_call_id", "request_hash", "partition", "original_call_index", "staged_execution_index"):
            if record.get(key) != expected.get(key):
                raise HardStop("non staged exact-prefix resume", records)
        if record["logical_call_id"] in seen:
            raise HardStop("duplicate logical ID/request/response", records)
        seen.add(record["logical_call_id"])
        aid = record.get("authorization_id")
        if aid not in registry or registry[aid][1] != record.get("authorization_sha256"):
            raise HardStop("authorization registry cannot resolve historical authorization", records)
        validate_authorization(load(CONFIG), registry[aid][0], registry[aid][1], record["partition"])
        if record.get("authorized_stage") != record["partition"]:
            raise HardStop("stage not authorized", records)
        if record.get("previous_ledger_entry_sha256") != previous_hash:
            raise HardStop("ledger hash chain drift", records)
        entry_hash = record.get("ledger_entry_sha256")
        if entry_hash != stable({key: value for key, value in record.items() if key != "ledger_entry_sha256"}):
            raise HardStop("ledger hash chain drift", records)
        previous_hash = entry_hash
        if record.get("terminal"):
            raise HardStop("terminal ledger is not resumable", records)
        usage(record)
    return registry


def _verify_coverage(config: dict[str, Any], records: list[dict[str, Any]], artifact_path: Path, schedule: list[dict[str, Any]]) -> dict[str, Any]:
    supplied = load(artifact_path)
    expected = build_candidate_artifact(records, schedule, config)
    if supplied != expected:
        raise HardStop("coverage artifact/verifier/ledger binding drift")
    return expected


def _verify_probe(config: dict[str, Any], records: list[dict[str, Any]], coverage: dict[str, Any], coverage_sha: str, audit_path: Path, schedule: list[dict[str, Any]]) -> dict[str, Any]:
    supplied = load(audit_path)
    expected = build_probe_audit(records, schedule, coverage, coverage_sha, config)
    if supplied != expected:
        raise HardStop("probe audit hash/analyzer binding drift")
    return expected


def execute_stage(config: dict[str, Any], registry_path: Path, auth_id: str, ledger_path: Path, provider: Callable[[dict[str, Any]], dict[str, Any]], stage: str, *, coverage_path: Path | None = None, probe_audit_path: Path | None = None, interrupt_after: int | None = None) -> list[dict[str, Any]]:
    validate_config(config)
    records = load(ledger_path) if ledger_path.exists() else []
    schedule = schedule_rows()
    registry = validate_prefix(schedule, records, registry_path)
    if len(records) >= len(schedule) or schedule[len(records)]["partition"] != stage:
        raise HardStop("stage skipped or order drift", records)
    if auth_id not in registry:
        raise HardStop("authorization registry cannot resolve current authorization", records)
    auth, auth_sha = registry[auth_id]
    validate_authorization(config, auth, auth_sha, stage)
    if auth.get("authorized_stage") != stage or not all(auth.get(k) is True for k in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        raise HardStop("stage not authorized or execution switches closed", records)
    if auth.get("formal_scaling_allowed") is not False or auth.get("model_id") != "qwen3.7-plus" or auth.get("temperature") != 0 or auth.get("retries") != 0 or auth.get("max_tokens_present") is not False:
        raise HardStop("authorization model/retry/max_tokens drift", records)
    if stage in ("probe", "held_out"):
        if not coverage_path:
            raise HardStop("coverage not passed before probe or held-out", records)
        coverage = _verify_coverage(config, records, coverage_path, schedule)
        if not coverage["passed"]:
            raise HardStop("coverage not passed before probe or held-out", records)
    if stage == "held_out":
        if not probe_audit_path:
            raise HardStop("probe not completely audited before held-out", records)
        coverage = load(coverage_path)
        _verify_probe(config, records, coverage, sha256_file(coverage_path), probe_audit_path, schedule)
    current_auth_calls = sum(r.get("authorization_id") == auth_id for r in records)
    stage_calls = sum(r.get("authorization_id") == auth_id and r.get("partition") == stage for r in records)
    while len(records) < len(schedule) and schedule[len(records)]["partition"] == stage:
        if current_auth_calls >= auth["authorized_calls"] or stage_calls >= auth["stage_call_ceiling"]:
            raise HardStop("current authorization call ceiling", records)
        row = schedule[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0:
            raise HardStop("request model/temperature/max_tokens drift", records)
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "partition", "task_id", "skill_family", "condition", "payload_hash", "original_call_index", "staged_execution_index")}
        base.update(authorization_id=auth_id, authorization_sha256=auth_sha, authorized_stage=stage, request_id=None, retries=0, max_tokens_present=False, previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None)
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            raw = response.get("content")
            if not isinstance(raw, str):
                raise HardStop("provider response missing raw content")
            provider_response = response.get("raw_provider_response", response)
            record = {**base, "raw_response": raw, "raw_response_sha256": stable(raw), "raw_provider_response": provider_response, "raw_provider_response_sha256": stable(provider_response), "usage": exact, "terminal": False, "status": "completed", "error": None}
            if response.get("request_id") is not None:
                record["request_id"] = response["request_id"]
        except Exception as exc:
            raw = response.get("content") if isinstance(response, dict) else None
            exact_usage = response.get("usage") if isinstance(response, dict) else None
            provider_response = response.get("raw_provider_response", response) if isinstance(response, dict) else None
            record = {**base, "raw_response": raw, "raw_response_sha256": stable(raw), "raw_provider_response": provider_response, "raw_provider_response_sha256": stable(provider_response), "usage": exact_usage, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        _seal_record(record)
        records.append(record)
        atomic_write_ledger(ledger_path, records)
        if interrupt_after is not None and len(records) == interrupt_after:
            raise KeyboardInterrupt("simulated process termination after durable append")
        if record["terminal"]:
            raise HardStop(record["error"], records)
        current_auth_calls += 1
        stage_calls += 1
        stage_rows = [r for r in records if r["partition"] == stage]
        if cost(config, stage_rows) > auth["stage_cost_ceiling_cny"]:
            records[-1]["terminal"] = True; records[-1]["status"] = "hard_stop"; records[-1]["error"] = "stage cost ceiling exceeded"; _seal_record(records[-1]); atomic_write_ledger(ledger_path, records); raise HardStop(records[-1]["error"], records)
        if cost(config, records) > auth["cumulative_cost_ceiling_cny"]:
            records[-1]["terminal"] = True; records[-1]["status"] = "hard_stop"; records[-1]["error"] = "global cumulative cost ceiling exceeded"; _seal_record(records[-1]); atomic_write_ledger(ledger_path, records); raise HardStop(records[-1]["error"], records)
    return records


def run_local(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load(CONFIG)
    validate_config(config)
    auth = load(AUTH)
    validate_authorization(config, auth, sha256_file(AUTH))
    if auth.get("status") != "closed_preflight" or any(auth.get(k) is not False for k in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise HardStop("closed authorization drift")
    return {"status": "preflight-passed-closed", "schedule_requests": len(schedule_rows()), "coverage_status": "coverage-incomplete", "network_calls": 0, "provider_calls": 0, "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("preflight")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--registry", type=Path)
    audit_parser.add_argument("--ledger", type=Path)
    for command in ("resume", "execute-stage"):
        live = sub.add_parser(command)
        live.add_argument("--registry", type=Path, required=True)
        live.add_argument("--authorization-id", required=True)
        live.add_argument("--ledger", type=Path, required=True)
        live.add_argument("--stage", choices=STAGES, required=True)
        live.add_argument("--coverage", type=Path)
        live.add_argument("--probe-audit", type=Path)
    args = parser.parse_args(argv)
    if args.command in (None, "preflight"):
        print(json.dumps(run_local(), indent=2, sort_keys=True))
        return 0
    if args.command == "audit":
        if args.registry is None and args.ledger is None:
            print(json.dumps(run_local(), indent=2, sort_keys=True))
            return 0
        if args.registry is None or args.ledger is None:
            parser.error("audit requires both --registry and --ledger")
        records = load(args.ledger) if args.ledger.exists() else []
        validate_config(load(CONFIG))
        validate_prefix(schedule_rows(), records, args.registry)
        print(json.dumps({"status": "ledger-audit-passed", "rows": len(records), "ledger_sha256": stable(records)}, indent=2, sort_keys=True))
        return 0
    config = load(CONFIG)
    records = load(args.ledger) if args.ledger.exists() else []
    validate_config(config)
    resolved = validate_prefix(schedule_rows(), records, args.registry)
    if args.authorization_id not in resolved:
        raise HardStop("authorization registry cannot resolve current authorization", records)
    authorization, authorization_sha = resolved[args.authorization_id]
    validate_authorization(config, authorization, authorization_sha, args.stage)
    if not all(authorization.get(key) is True for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        raise HardStop("stage not authorized or execution switches closed", records)
    from scripts.acl2027_phase2_provider_adapter_v3 import QwenProviderAdapter
    provider = QwenProviderAdapter(authorization)
    result = execute_stage(config, args.registry, args.authorization_id, args.ledger, provider, args.stage, coverage_path=args.coverage, probe_audit_path=args.probe_audit)
    print(json.dumps({"status": "stage-complete", "rows": len(result)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
