#!/usr/bin/env python3
"""Bounded Phase 2 formal-history acquisition v11.

This is deliberately independent of earlier closed stages. It can only acquire
the frozen 160 history responses, replay the frozen verifier, and close.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable, verify_response, load_gold
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
from scripts.materialize_acl2027_phase2_candidates_v3 import build_candidate_artifact
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import HardStop, usage

VERSION = 11
MODEL = "qwen3.7-plus"
CALLS = 160
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")
INTERVAL_NS = 1_000_000_000
COST_CEILING = 1.64
SYSTEM = 'Answer using only the supplied context. Return exactly one JSON object with schema {"answer":"<short answer>"}; no other keys or text.'

CONFIG = ROOT / "configs/acl2027/phase2_formal_history_preflight_v11.json"
AUTH = ROOT / "configs/acl2027/phase2_formal_history_authorization_v11.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_formal_history_v11"
SCHEDULE = ARTIFACT / "formal_history_schedule.json"
MANIFEST = ARTIFACT / "run_manifest.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING = ARTIFACT / "request_start_ledger.json"
CANDIDATES = ARTIFACT / "candidate_materialization.json"
AUDIT = ARTIFACT / "formal_history_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
REPORT = ROOT / "paper/acl2027/results/phase2_formal_history_v11.md"
SOURCE_SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
V4 = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
GOLD = ROOT / "data/searchqa_phase2_verified/formal_history.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
VERIFIER = ROOT / "scripts/acl2027_phase2_response_verifier_v3.py"
MATERIALIZER = ROOT / "scripts/materialize_acl2027_phase2_candidates_v3.py"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def schedule() -> list[dict[str, Any]]:
    source = [x for x in load(SOURCE_SCHEDULE)["schedule"] if x["partition"] == "formal_history"]
    if len(source) != CALLS:
        raise HardStop("v11 formal-history source schedule must contain 160 rows")
    rows = []
    for sequence, original in enumerate(source, 1):
        row = deepcopy(original)
        body = deepcopy(row["canonical_request_body"])
        body["messages"][0]["content"] = SYSTEM
        body["prompt_template_version"] = "phase2-prompt-v11-exact-json"
        body["response_format"] = {"type": "json_object"}
        row["logical_call_id"] = f"phase2-v11:formal_history:{row['skill_family']}:{row['task_id']}:cold"
        row["sequence"] = sequence
        row["source_request_hash"] = original["request_hash"]
        row["canonical_request_body"] = body
        row["prompt_template_version"] = body["prompt_template_version"]
        row["request_hash"] = stable(body)
        rows.append(row)
    if len({x["logical_call_id"] for x in rows}) != CALLS or len({x["request_hash"] for x in rows}) != CALLS:
        raise HardStop("v11 schedule identities are not unique")
    if any(sum(x["skill_family"] == f for x in rows) != 32 for f in FAMILIES):
        raise HardStop("v11 family allocation drift")
    return rows


def config() -> dict[str, Any]:
    v4 = load(V4)
    return {
        "schema_version": VERSION, "experiment": "acl2027_phase2_formal_history_v11", "status": "preflight_only_closed",
        "execution": {"network_calls_allowed": False, "provider_calls_allowed": False, "paid_api_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False},
        "bindings": {"source_schedule_sha256": sha256_file(SOURCE_SCHEDULE), "v4_config_sha256": sha256_file(V4), "formal_history_gold_sha256": sha256_file(GOLD), "provider_adapter_sha256": sha256_file(ADAPTER), "verifier_source_sha256": sha256_file(VERIFIER), "materializer_source_sha256": sha256_file(MATERIALIZER), "runner_source_sha256": sha256_file(Path(__file__).resolve())},
        "stage": {"name": "formal_history", "logical_calls": CALLS, "calls_per_family": 32, "target_verified_supports_per_family": 8, "model_id": MODEL, "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False, "stage_cost_ceiling_cny": COST_CEILING},
        "coverage_gate": v4["coverage_gate"], "trusted_evaluation": v4["trusted_evaluation"],
        "forbidden_stages": ["probe", "held_out", "formal_scaling"], "counters": {"network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
    }


def manifest() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]
    return {"schema_version": VERSION, "status": "preflight-passed-closed", "config_sha256": sha256_file(CONFIG), "schedule_sha256": sha256_file(SCHEDULE), "request_count": len(rows), "family_counts": {f: sum(x["skill_family"] == f for x in rows) for f in FAMILIES}, "request_hashes_sha256": stable([x["request_hash"] for x in rows]), "counters": {"network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}}


def prepare() -> dict[str, Any]:
    write(CONFIG, config()); write(SCHEDULE, {"schema_version": VERSION, "schedule": schedule()}); write(MANIFEST, manifest())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Phase 2 Formal History v11\n\nZero-network preflight passed; authorization remains closed.\n", encoding="utf-8")
    return manifest()


def validate_preflight() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if load(CONFIG) != config() or load(SCHEDULE) != {"schema_version": VERSION, "schedule": schedule()} or load(MANIFEST) != manifest():
        raise HardStop("v11 preflight binding drift")
    cfg = load(CONFIG)
    if any(cfg["execution"].values()) or any(cfg["counters"].values()):
        raise HardStop("v11 preflight must be closed")
    return cfg, load(SCHEDULE)["schedule"]


def bindings() -> dict[str, str]:
    return {"preflight_config_sha256": sha256_file(CONFIG), "manifest_sha256": sha256_file(MANIFEST), "schedule_sha256": sha256_file(SCHEDULE), "runner_source_sha256": sha256_file(Path(__file__).resolve()), "provider_adapter_sha256": sha256_file(ADAPTER), "formal_history_gold_sha256": sha256_file(GOLD), "verifier_source_sha256": sha256_file(VERIFIER), "materializer_source_sha256": sha256_file(MATERIALIZER)}


def build_auth(key: str) -> dict[str, Any]:
    return {"schema_version": VERSION, "authorization_id": "phase2-formal-history-token-plan-v11", "status": "open", "opened_at": datetime.now(timezone.utc).isoformat(), "bindings": bindings(), "credential_sha256": hashlib.sha256(key.encode()).hexdigest(), "user_authorization": {"scope": "phase2_formal_history_only", "authorized_calls": CALLS, "calls_per_family": 32, "target_verified_supports_per_family": 8, "max_tokens_present": False, "retries": 0, "probe_authorized": False, "held_out_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False}, "authorized_stage": "formal_history", "authorized_calls": CALLS, "stage_call_ceiling": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": COST_CEILING, "model_id": MODEL, "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False, "formal_scaling_allowed": False, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "forbidden_stages": ["probe", "held_out", "formal_scaling"]}


def open_auth() -> dict[str, Any]:
    validate_preflight()
    if AUTH.exists() or REGISTRY.exists() or CLOSURE.exists(): raise HardStop("v11 authorization lifecycle already exists")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key: raise HardStop("DASHSCOPE_API_KEY is missing")
    auth = build_auth(key); write(AUTH, auth)
    auth_path = os.path.relpath(AUTH, REGISTRY.parent).replace("\\", "/")
    write(REGISTRY, {"schema_version": VERSION, "authorizations": {auth["authorization_id"]: {"path": auth_path, "sha256": sha256_file(AUTH)}}})
    return auth


def validate_auth() -> tuple[dict[str, Any], str]:
    registry = load(REGISTRY); item = registry.get("authorizations", {}).get("phase2-formal-history-token-plan-v11")
    if not item or (REGISTRY.parent / item["path"]).resolve() != AUTH.resolve() or item["sha256"] != sha256_file(AUTH): raise HardStop("v11 authorization registry drift")
    auth = load(AUTH); key = os.environ.get("DASHSCOPE_API_KEY")
    required = {"status": "open", "bindings": bindings(), "authorized_stage": "formal_history", "authorized_calls": CALLS, "stage_call_ceiling": CALLS, "max_provider_attempts": CALLS, "stage_cost_ceiling_cny": COST_CEILING, "cumulative_cost_ceiling_cny": COST_CEILING, "model_id": MODEL, "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False, "formal_scaling_allowed": False, "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True, "forbidden_stages": ["probe", "held_out", "formal_scaling"]}
    if any(auth.get(k) != v for k, v in required.items()) or not key or auth.get("credential_sha256") != hashlib.sha256(key.encode()).hexdigest(): raise HardStop("v11 authorization boundary drift")
    return auth, item["sha256"]


def seal(record: dict[str, Any]) -> None: record["ledger_entry_sha256"] = stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"})


def check_prefix(records: list[dict[str, Any]], rows: list[dict[str, Any]], auth_sha: str) -> None:
    if len(records) > CALLS: raise HardStop("v11 ledger exceeds authorization", records)
    previous = None
    for expected, record in zip(rows, records):
        if any(record.get(k) != expected.get(k) for k in ("logical_call_id", "request_hash", "task_id", "skill_family", "sequence")): raise HardStop("v11 non-prefix resume", records)
        if record.get("authorization_sha256") != auth_sha or record.get("previous_ledger_entry_sha256") != previous or record.get("ledger_entry_sha256") != stable({k:v for k,v in record.items() if k != "ledger_entry_sha256"}) or record.get("terminal"): raise HardStop("v11 ledger integrity drift", records)
        usage(record); previous = record["ledger_entry_sha256"]


def cost(records: list[dict[str, Any]]) -> float:
    return round(sum(usage(x)["input_tokens"] * 2.0 + usage(x)["output_tokens"] * 8.0 for x in records) / 1_000_000, 6)


def execute(provider: Callable[[dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    _, rows = validate_preflight(); _, auth_sha = validate_auth(); records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []
    check_prefix(records, rows, auth_sha)
    if len(starts) != len(records): raise HardStop("v11 ambiguous request start; retry forbidden", records)
    while len(records) < CALLS:
        row = rows[len(records)]; body = deepcopy(row["canonical_request_body"])
        if "max_tokens" in body or body.get("response_format") != {"type": "json_object"}: raise HardStop("v11 request boundary drift", records)
        if starts:
            wait = INTERVAL_NS - (time.time_ns() - starts[-1]["request_started_at_unix_ns"])
            if wait > 0: time.sleep(wait / 1_000_000_000)
        event = {"sequence": len(starts)+1, "request_body_sha256": stable(body), "request_started_at_unix_ns": time.time_ns(), "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None}; event["start_entry_sha256"] = stable(event); starts.append(event); write(PACING, starts)
        base = {k: row[k] for k in ("logical_call_id", "request_hash", "partition", "task_id", "task_family", "task_type", "skill_family", "condition", "payload_hash", "sequence")}; base.update(authorization_id="phase2-formal-history-token-plan-v11", authorization_sha256=auth_sha, authorized_stage="formal_history", retries=0, max_tokens_present=False, previous_ledger_entry_sha256=records[-1]["ledger_entry_sha256"] if records else None)
        response = None
        try:
            response = provider(body); exact = usage(response); raw = response.get("content")
            if not isinstance(raw, str): raise HardStop("v11 provider response missing raw content")
            record = {**base, "raw_response": raw, "raw_response_sha256": stable(raw), "raw_provider_response": response.get("raw_provider_response", response), "usage": exact, "terminal": False, "status": "completed", "error": None}
        except Exception as exc:
            record = {**base, "raw_response": response.get("content") if isinstance(response, dict) else None, "raw_response_sha256": stable(response.get("content") if isinstance(response, dict) else None), "raw_provider_response": response.get("raw_provider_response", response) if isinstance(response, dict) else response, "usage": response.get("usage") if isinstance(response, dict) else None, "terminal": True, "status": "hard_stop", "error": f"{type(exc).__name__}: {exc}"}
        seal(record); records.append(record); write(LEDGER, records)
        if record["terminal"]: raise HardStop(record["error"], records)
        if cost(records) > COST_CEILING:
            records[-1].update(terminal=True, status="hard_stop", error="v11 cost ceiling exceeded"); seal(records[-1]); write(LEDGER, records); raise HardStop(records[-1]["error"], records)
    return records


def audit() -> dict[str, Any]:
    cfg, rows = validate_preflight(); records = load(LEDGER) if LEDGER.exists() else []; starts = load(PACING) if PACING.exists() else []; terminal = bool(records and records[-1].get("terminal"))
    if not terminal: check_prefix(records, rows, sha256_file(AUTH))
    if len(starts) != len(records): raise HardStop("v11 pacing count drift")
    candidate = None
    if len(records) == CALLS and not terminal:
        candidate = build_candidate_artifact(records, rows, cfg); write(CANDIDATES, candidate)
    counts = candidate["independent_verified_supports"] if candidate else {f: 0 for f in FAMILIES}
    return {"schema_version": VERSION, "experiment": "acl2027_phase2_formal_history_v11", "status": "completed" if candidate else "terminal_hard_stop", "provider_attempts": len(records), "completed_calls": sum(x.get("status") == "completed" for x in records), "terminal_rows": sum(bool(x.get("terminal")) for x in records), "total_tokens": sum(usage(x)["total_tokens"] for x in records) if len(records) == CALLS and not terminal else None, "exact_local_cost_cny": cost(records) if len(records) == CALLS and not terminal else None, "retries": sum(x.get("retries", 0) for x in records), "duplicates": len(records)-len({x["logical_call_id"] for x in records}), "max_tokens_present": any(x.get("max_tokens_present") for x in records), "request_start_pacing_valid": all(b["request_started_at_unix_ns"]-a["request_started_at_unix_ns"] >= INTERVAL_NS for a,b in zip(starts,starts[1:])), "coverage_status": candidate["coverage_status"] if candidate else "not_reached", "coverage_passed": candidate["passed"] if candidate else False, "independent_verified_supports": counts, "probe_calls": 0, "held_out_calls": 0, "formal_scaling_calls": 0, "authorization_closed": True}


def close() -> dict[str, Any]:
    result = audit(); write(AUDIT, result); write(CLOSURE, {"schema_version": VERSION, "status": "closed_completed" if result["status"] == "completed" else "closed_terminal_hard_stop", "authorization_sha256": sha256_file(AUTH), "audit_sha256": sha256_file(AUDIT), "provider_attempts": result["provider_attempts"], "later_stages_authorized": False}); auth_path = os.path.relpath(AUTH, REGISTRY.parent).replace("\\", "/"); write(REGISTRY, {"schema_version": VERSION, "authorizations": {}, "closed_authorizations": {"phase2-formal-history-token-plan-v11": {"path": auth_path, "sha256": sha256_file(AUTH)}}}); REPORT.write_text("# Phase 2 Formal History v11\n\n```json\n"+json.dumps(result, indent=2, sort_keys=True)+"\n```\n\nProbe and held-out remain unauthorized.\n", encoding="utf-8"); return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("prepare", "open", "execute", "audit", "close")); args = parser.parse_args()
    if args.command == "prepare": output = prepare()
    elif args.command == "open": output = open_auth()
    elif args.command == "execute": output = {"rows": len(execute(QwenTokenPlanProviderAdapter(validate_auth()[0])))}
    elif args.command == "audit": output = audit()
    else: output = close()
    print(json.dumps(output, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
