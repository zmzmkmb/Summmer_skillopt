#!/usr/bin/env python3
"""Prepare, authorize, execute, audit, and close Phase 2 development acquisition v10."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import string
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import (  # noqa: E402
    QwenTokenPlanProviderAdapter,
)
from scripts.run_acl2027_phase2_staged_live_runner_preflight_v4 import (  # noqa: E402
    HardStop,
    _seal_record,
    atomic_write_ledger,
    load,
    sha256_file,
    stable,
    usage,
)

CONFIG = ROOT / "configs/acl2027/phase2_development_acquisition_preflight_v10.json"
AUTH = ROOT / "configs/acl2027/phase2_development_acquisition_authorization_v10.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_development_acquisition_v10"
SCHEDULE = ARTIFACT / "development_schedule.json"
MANIFEST = ARTIFACT / "run_manifest.json"
REGISTRY = ARTIFACT / "authorization_registry.json"
LEDGER = ARTIFACT / "ledger.json"
PACING_LEDGER = ARTIFACT / "request_start_ledger.json"
AUDIT = ARTIFACT / "development_audit.json"
CLOSURE = ARTIFACT / "authorization_closure.json"
REPORT = ROOT / "paper/acl2027/results/phase2_development_acquisition_v10.md"

V9_CONFIG = ROOT / "configs/acl2027/phase2_postcalibration_activation_preflight_v9.json"
V8_AUDIT = ROOT / "artifacts/acl2027_phase2_calibration_live_v8/calibration_audit.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
SOURCE_SCHEDULE = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2/staged_execution_schedule.json"
DEV_GOLD = ROOT / "data/searchqa_phase2_verified/development_acquisition.json"
ADAPTER = ROOT / "scripts/acl2027_phase2_token_plan_provider_adapter_v8.py"
TEST_SOURCE = ROOT / "tests/test_acl2027_phase2_development_acquisition_v10.py"

MODEL_ID = "qwen3.7-plus"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
AUTHORIZATION_ID = "phase2-development-acquisition-token-plan-v10"
INTERVAL_NS = 1_000_000_000
STAGE_COST_CEILING_CNY = 0.11
SYSTEM_PROMPT = (
    "Answer the question using only the supplied context. Return exactly one JSON object "
    'with schema {"answer":"<short answer>"}; use no other keys and no other text.'
)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_schedule() -> list[dict[str, Any]]:
    source = [
        row for row in load(SOURCE_SCHEDULE)["schedule"]
        if row["partition"] == "development_acquisition"
    ]
    if len(source) != 10:
        raise HardStop("v10 source development schedule must contain exactly 10 rows")
    rows: list[dict[str, Any]] = []
    for sequence, original in enumerate(source, start=1):
        row = deepcopy(original)
        body = deepcopy(row["canonical_request_body"])
        body["messages"][0]["content"] = SYSTEM_PROMPT
        body["prompt_template_version"] = "phase2-prompt-v10-exact-json"
        body["response_format"] = {"type": "json_object"}
        body["development_outputs_not_formal_history"] = True
        row["logical_call_id"] = (
            f"phase2-v10:development_acquisition:{row['skill_family']}:"
            f"{row['task_id']}:cold"
        )
        row["sequence"] = sequence
        row["source_request_hash"] = original["request_hash"]
        row["prompt_template_version"] = body["prompt_template_version"]
        row["canonical_request_body"] = body
        row["request_hash"] = stable(body)
        row["development_outputs_not_formal_history"] = True
        rows.append(row)
    families = [row["skill_family"] for row in rows]
    expected = {
        "fact_retrieval",
        "attribute_comparison",
        "bridge_attribute_comparison",
        "entity_bridge",
        "relation_inference",
    }
    if set(families) != expected or any(families.count(family) != 2 for family in expected):
        raise HardStop("v10 family allocation drift")
    if len({row["logical_call_id"] for row in rows}) != 10:
        raise HardStop("v10 duplicate logical call id")
    if len({row["request_hash"] for row in rows}) != 10:
        raise HardStop("v10 duplicate request hash")
    return rows


def build_config() -> dict[str, Any]:
    v9 = load(V9_CONFIG)
    v8 = load(V8_AUDIT)
    if not v9["v8_gate_requirement"]["eligibility_gate"]["passed"]:
        raise HardStop("v10 requires the passed v8 calibration gate")
    if v9["next_live_stage_only"] != {
        "stage": "development_acquisition",
        "logical_calls": 10,
        "families": 5,
        "calls_per_family": 2,
        "model_id": MODEL_ID,
        "retries": 0,
        "max_tokens_present": False,
        "hard_stops": [
            "unknown_usage",
            "provider_exception",
            "authorization_drift",
            "schedule_drift",
            "duplicate_request",
            "cost_ceiling",
        ],
    }:
        raise HardStop("v10 activation boundary drift")
    if v8.get("status") != "completed" or v8.get("authorization_closed") is not True:
        raise HardStop("v10 requires completed and closed v8 evidence")
    return {
        "schema_version": 10,
        "experiment": "acl2027_phase2_development_acquisition_v10",
        "status": "preflight_only_closed",
        "execution": {
            "network_calls_allowed": False,
            "provider_calls_allowed": False,
            "paid_api_allowed": False,
            "qwen_authorization_open": False,
            "formal_scaling_allowed": False,
        },
        "bindings": {
            "v9_config_sha256": sha256_file(V9_CONFIG),
            "v8_audit_sha256": sha256_file(V8_AUDIT),
            "v4_config_sha256": sha256_file(V4_CONFIG),
            "source_schedule_sha256": sha256_file(SOURCE_SCHEDULE),
            "development_gold_sha256": sha256_file(DEV_GOLD),
            "provider_adapter_sha256": sha256_file(ADAPTER),
            "runner_source_sha256": sha256_file(Path(__file__).resolve()),
            "test_source_sha256": sha256_file(TEST_SOURCE),
        },
        "stage": {
            "name": "development_acquisition",
            "logical_calls": 10,
            "calls_per_family": 2,
            "model_id": MODEL_ID,
            "temperature": 0,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
            "request_interval_seconds": 1.0,
            "retries": 0,
            "max_tokens_present": False,
            "stage_cost_ceiling_cny": STAGE_COST_CEILING_CNY,
            "development_outputs_not_formal_history": True,
        },
        "forbidden_stages": ["formal_history", "probe", "held_out", "formal_scaling"],
        "counters": {"network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
    }


def build_manifest() -> dict[str, Any]:
    rows = load(SCHEDULE)["schedule"]
    return {
        "schema_version": 10,
        "status": "preflight-passed-closed",
        "config_sha256": sha256_file(CONFIG),
        "schedule_sha256": sha256_file(SCHEDULE),
        "runner_source_sha256": sha256_file(Path(__file__).resolve()),
        "test_source_sha256": sha256_file(TEST_SOURCE),
        "request_count": len(rows),
        "logical_call_ids": [row["logical_call_id"] for row in rows],
        "request_hashes": [row["request_hash"] for row in rows],
        "family_counts": {
            family: sum(row["skill_family"] == family for row in rows)
            for family in sorted({row["skill_family"] for row in rows})
        },
        "counters": {"network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
    }


def render_report(decision: str, details: dict[str, Any]) -> str:
    lines = [
        "# Phase 2 Development Acquisition v10",
        "",
        "## Decision",
        "",
        decision,
        "",
        "## Scope",
        "",
        "This stage contains exactly 10 qwen3.7-plus Token Plan calls: two development tasks",
        "for each of five skill families. It uses zero retries, omits max_tokens, and does",
        "not authorize formal history, probe, held-out execution, or formal scaling.",
        "Development responses are diagnostic and cannot be reused as formal history.",
        "",
        "## Audit Summary",
        "",
        "```json",
        json.dumps(details, ensure_ascii=True, sort_keys=True, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def prepare() -> dict[str, Any]:
    rows = build_schedule()
    config = build_config()
    write_json_atomic(CONFIG, config)
    write_json_atomic(SCHEDULE, {"schema_version": 10, "schedule": rows})
    manifest = build_manifest()
    write_json_atomic(MANIFEST, manifest)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        render_report(
            "Zero-network preflight passed and remains closed pending the explicit v10 authorization.",
            manifest,
        ),
        encoding="utf-8",
    )
    return manifest


def validate_preflight() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = load(CONFIG)
    rows_doc = load(SCHEDULE)
    manifest = load(MANIFEST)
    if config != build_config():
        raise HardStop("v10 preflight config drift")
    if rows_doc != {"schema_version": 10, "schedule": build_schedule()}:
        raise HardStop("v10 development schedule drift")
    if manifest != build_manifest():
        raise HardStop("v10 preflight manifest drift")
    if any(config["execution"].values()) or any(config["counters"].values()):
        raise HardStop("v10 preflight is not closed")
    return config, rows_doc["schedule"], manifest


def authorization_bindings() -> dict[str, str]:
    return {
        "preflight_config_sha256": sha256_file(CONFIG),
        "preflight_manifest_sha256": sha256_file(MANIFEST),
        "schedule_sha256": sha256_file(SCHEDULE),
        "runner_source_sha256": sha256_file(Path(__file__).resolve()),
        "provider_adapter_sha256": sha256_file(ADAPTER),
        "development_gold_sha256": sha256_file(DEV_GOLD),
        "v9_config_sha256": sha256_file(V9_CONFIG),
    }


def build_authorization(key: str) -> dict[str, Any]:
    return {
        "schema_version": 10,
        "authorization_id": AUTHORIZATION_ID,
        "status": "open",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "bindings": authorization_bindings(),
        "credential_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "user_authorization": {
            "scope": "phase2_development_acquisition_only",
            "authorized_calls": 10,
            "model_id": MODEL_ID,
            "max_tokens_present": False,
            "formal_history_authorized": False,
            "probe_authorized": False,
            "held_out_authorized": False,
            "later_stages_authorized": False,
            "formal_scaling_authorized": False,
        },
        "authorized_stage": "development_acquisition",
        "authorized_calls": 10,
        "stage_call_ceiling": 10,
        "max_provider_attempts": 10,
        "stage_cost_ceiling_cny": STAGE_COST_CEILING_CNY,
        "cumulative_cost_ceiling_cny": STAGE_COST_CEILING_CNY,
        "model_id": MODEL_ID,
        "endpoint": ENDPOINT,
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "retries": 0,
        "max_tokens_present": False,
        "formal_scaling_allowed": False,
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "forbidden_stages": ["formal_history", "probe", "held_out", "formal_scaling"],
    }


def open_authorization() -> dict[str, Any]:
    validate_preflight()
    if AUTH.exists() or REGISTRY.exists() or CLOSURE.exists():
        raise HardStop("v10 authorization or lifecycle artifact already exists")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise HardStop("DASHSCOPE_API_KEY is missing")
    auth = build_authorization(key)
    write_json_atomic(AUTH, auth)
    write_json_atomic(
        REGISTRY,
        {
            "schema_version": 10,
            "authorizations": {
                AUTHORIZATION_ID: {
                    "path": "../../configs/acl2027/phase2_development_acquisition_authorization_v10.json",
                    "sha256": sha256_file(AUTH),
                }
            },
        },
    )
    return auth


def validate_authorization(registry_path: Path = REGISTRY) -> tuple[dict[str, Any], str]:
    registry = load(registry_path)
    item = registry.get("authorizations", {}).get(AUTHORIZATION_ID)
    if not item:
        raise HardStop("v10 authorization missing or closed")
    path = (registry_path.parent / item["path"]).resolve()
    if path != AUTH.resolve() or sha256_file(path) != item.get("sha256"):
        raise HardStop("v10 authorization registry drift")
    auth = load(path)
    key = os.environ.get("DASHSCOPE_API_KEY")
    exact = {
        "status": "open",
        "bindings": authorization_bindings(),
        "authorized_stage": "development_acquisition",
        "authorized_calls": 10,
        "stage_call_ceiling": 10,
        "max_provider_attempts": 10,
        "stage_cost_ceiling_cny": STAGE_COST_CEILING_CNY,
        "cumulative_cost_ceiling_cny": STAGE_COST_CEILING_CNY,
        "model_id": MODEL_ID,
        "endpoint": ENDPOINT,
        "temperature": 0,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "request_interval_seconds": 1.0,
        "retries": 0,
        "max_tokens_present": False,
        "formal_scaling_allowed": False,
        "paid_api_allowed": True,
        "provider_calls_allowed": True,
        "qwen_authorization_open": True,
        "forbidden_stages": ["formal_history", "probe", "held_out", "formal_scaling"],
    }
    if any(auth.get(field) != value for field, value in exact.items()):
        raise HardStop("v10 authorization boundary drift")
    scope = auth.get("user_authorization", {})
    if scope.get("scope") != "phase2_development_acquisition_only" or any(
        scope.get(field) is not False
        for field in (
            "formal_history_authorized",
            "probe_authorized",
            "held_out_authorized",
            "later_stages_authorized",
            "formal_scaling_authorized",
        )
    ):
        raise HardStop("v10 user authorization scope drift")
    if not key or auth.get("credential_sha256") != hashlib.sha256(key.encode("utf-8")).hexdigest():
        raise HardStop("v10 credential binding drift")
    return auth, item["sha256"]


class PersistentRequestStartPacer:
    def __init__(
        self,
        provider: Callable[[dict[str, Any]], dict[str, Any]],
        ledger_path: Path = LEDGER,
        pacing_path: Path = PACING_LEDGER,
        *,
        clock_ns: Callable[[], int] = time.time_ns,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.provider = provider
        self.ledger_path = ledger_path
        self.pacing_path = pacing_path
        self.clock_ns = clock_ns
        self.sleeper = sleeper

    def __call__(self, body: dict[str, Any]) -> dict[str, Any]:
        records = load(self.ledger_path) if self.ledger_path.exists() else []
        starts = load(self.pacing_path) if self.pacing_path.exists() else []
        if len(starts) != len(records):
            raise HardStop("v10 ambiguous request start; automatic retry forbidden", records)
        last = starts[-1]["request_started_at_unix_ns"] if starts else None
        while last is not None and self.clock_ns() - last < INTERVAL_NS:
            self.sleeper((INTERVAL_NS - (self.clock_ns() - last)) / 1_000_000_000)
        started = self.clock_ns()
        event = {
            "sequence": len(starts) + 1,
            "request_body_sha256": stable(body),
            "request_started_at_unix_ns": started,
            "previous_start_entry_sha256": starts[-1]["start_entry_sha256"] if starts else None,
        }
        event["start_entry_sha256"] = stable(event)
        starts.append(event)
        write_json_atomic(self.pacing_path, starts)
        return self.provider(body)


def validate_prefix(
    records: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    auth_sha: str,
) -> None:
    if len(records) > 10:
        raise HardStop("v10 ledger exceeds authorization", records)
    previous = None
    seen: set[str] = set()
    for expected, record in zip(rows, records):
        for field in ("logical_call_id", "request_hash", "task_id", "skill_family", "sequence"):
            if record.get(field) != expected.get(field):
                raise HardStop("v10 non-prefix resume", records)
        if record["logical_call_id"] in seen:
            raise HardStop("v10 duplicate logical request", records)
        seen.add(record["logical_call_id"])
        if record.get("authorization_id") != AUTHORIZATION_ID or record.get("authorization_sha256") != auth_sha:
            raise HardStop("v10 ledger authorization drift", records)
        if record.get("previous_ledger_entry_sha256") != previous:
            raise HardStop("v10 ledger chain drift", records)
        if record.get("ledger_entry_sha256") != stable(
            {key: value for key, value in record.items() if key != "ledger_entry_sha256"}
        ):
            raise HardStop("v10 ledger entry drift", records)
        previous = record["ledger_entry_sha256"]
        if record.get("terminal"):
            raise HardStop("v10 terminal ledger is not resumable", records)
        usage(record)


def exact_cost(records: list[dict[str, Any]]) -> float:
    input_tokens = sum(usage(record)["input_tokens"] for record in records)
    output_tokens = sum(usage(record)["output_tokens"] for record in records)
    return round(input_tokens * 2.0 / 1_000_000 + output_tokens * 8.0 / 1_000_000, 6)


def execute_requests(
    provider: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    registry_path: Path = REGISTRY,
    ledger_path: Path = LEDGER,
    interrupt_after: int | None = None,
) -> list[dict[str, Any]]:
    _, rows, _ = validate_preflight()
    _, auth_sha = validate_authorization(registry_path)
    records = load(ledger_path) if ledger_path.exists() else []
    validate_prefix(records, rows, auth_sha)
    while len(records) < 10:
        row = rows[len(records)]
        body = deepcopy(row["canonical_request_body"])
        if (
            "max_tokens" in body
            or body.get("response_format") != {"type": "json_object"}
            or body.get("prompt_template_version") != "phase2-prompt-v10-exact-json"
            or body.get("development_outputs_not_formal_history") is not True
        ):
            raise HardStop("v10 request boundary drift", records)
        base = {
            field: row[field]
            for field in (
                "logical_call_id",
                "request_hash",
                "partition",
                "task_id",
                "task_family",
                "task_type",
                "skill_family",
                "condition",
                "payload_hash",
                "sequence",
            )
        }
        base.update(
            authorization_id=AUTHORIZATION_ID,
            authorization_sha256=auth_sha,
            authorized_stage="development_acquisition",
            request_id=None,
            retries=0,
            max_tokens_present=False,
            development_outputs_not_formal_history=True,
            previous_ledger_entry_sha256=(records[-1]["ledger_entry_sha256"] if records else None),
        )
        response = None
        try:
            response = provider(body)
            exact = usage(response)
            raw = response.get("content")
            if not isinstance(raw, str):
                raise HardStop("v10 provider response missing raw content")
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
        if exact_cost(records) > STAGE_COST_CEILING_CNY:
            records[-1]["terminal"] = True
            records[-1]["status"] = "hard_stop"
            records[-1]["error"] = "v10 cost ceiling exceeded"
            _seal_record(records[-1])
            atomic_write_ledger(ledger_path, records)
            raise HardStop(records[-1]["error"], records)
    return records


def normalize_answer(value: str) -> str:
    value = value.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in value.split() if token not in {"a", "an", "the"})


def parse_answer(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ValueError("raw response is not text")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {"answer"}:
        raise ValueError("response schema must contain exactly answer")
    answer = payload["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer must be non-empty text")
    return answer


def build_audit() -> dict[str, Any]:
    _, rows, _ = validate_preflight()
    records = load(LEDGER) if LEDGER.exists() else []
    starts = load(PACING_LEDGER) if PACING_LEDGER.exists() else []
    auth_sha = sha256_file(AUTH)
    terminal = bool(records and records[-1].get("terminal"))
    if not terminal:
        validate_prefix(records, rows, auth_sha)
    if len(starts) != len(records):
        raise HardStop("v10 audit found ambiguous request-start count")
    previous = None
    for sequence, event in enumerate(starts, start=1):
        if event.get("sequence") != sequence or event.get("previous_start_entry_sha256") != previous:
            raise HardStop("v10 pacing ledger chain drift")
        if event.get("start_entry_sha256") != stable(
            {key: value for key, value in event.items() if key != "start_entry_sha256"}
        ):
            raise HardStop("v10 pacing entry drift")
        previous = event["start_entry_sha256"]
    gold = {str(row["task_id"]): row for row in load(DEV_GOLD)}
    evaluations: list[dict[str, Any]] = []
    for record in records:
        contract_valid = False
        answer_correct = False
        parsed_answer = None
        try:
            parsed_answer = parse_answer(record.get("raw_response"))
            contract_valid = True
            private = gold[record["task_id"]]
            answers = private.get("answers") or [private.get("answer")]
            expected = {normalize_answer(str(answer)) for answer in answers if answer is not None}
            answer_correct = normalize_answer(parsed_answer) in expected
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        evaluations.append(
            {
                "logical_call_id": record["logical_call_id"],
                "task_id": record["task_id"],
                "skill_family": record["skill_family"],
                "contract_valid": contract_valid,
                "answer_correct": answer_correct,
                "parsed_answer": parsed_answer,
                "development_only": True,
                "eligible_for_formal_history": False,
            }
        )
    known_usage = all(record.get("usage") is not None for record in records)
    total_input = sum(usage(record)["input_tokens"] for record in records if record.get("usage") is not None)
    total_output = sum(usage(record)["output_tokens"] for record in records if record.get("usage") is not None)
    per_family = {
        family: {
            "calls": sum(item["skill_family"] == family for item in evaluations),
            "contract_valid": sum(item["skill_family"] == family and item["contract_valid"] for item in evaluations),
            "answer_correct": sum(item["skill_family"] == family and item["answer_correct"] for item in evaluations),
        }
        for family in sorted({row["skill_family"] for row in rows})
    }
    completed = len(records) == 10 and not terminal
    return {
        "schema_version": 10,
        "experiment": "acl2027_phase2_development_acquisition_v10",
        "status": "completed" if completed else "terminal_hard_stop",
        "authorized_calls": 10,
        "provider_attempts": len(records),
        "completed_calls": sum(record.get("status") == "completed" for record in records),
        "terminal_rows": sum(bool(record.get("terminal")) for record in records),
        "contract_valid": sum(item["contract_valid"] for item in evaluations),
        "answer_correct": sum(item["answer_correct"] for item in evaluations),
        "per_family": per_family,
        "evaluations": evaluations,
        "total_input_tokens": total_input if known_usage else None,
        "total_output_tokens": total_output if known_usage else None,
        "total_tokens": total_input + total_output if known_usage else None,
        "exact_local_cost_cny": exact_cost(records) if known_usage else None,
        "cost_status": "exact" if known_usage else "unknown_usage_terminal_hard_stop",
        "request_start_spacing_minimum_seconds": min(
            [
                (b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"]) / 1_000_000_000
                for a, b in zip(starts, starts[1:])
            ],
            default=None,
        ),
        "request_start_pacing_valid": all(
            b["request_started_at_unix_ns"] - a["request_started_at_unix_ns"] >= INTERVAL_NS
            for a, b in zip(starts, starts[1:])
        ),
        "retries": sum(record.get("retries", 0) for record in records),
        "duplicates": len(records) - len({record["logical_call_id"] for record in records}),
        "max_tokens_present": any(record.get("max_tokens_present") for record in records),
        "development_outputs_not_formal_history": all(
            item["eligible_for_formal_history"] is False for item in evaluations
        ),
        "formal_history_calls": 0,
        "probe_calls": 0,
        "held_out_calls": 0,
        "formal_scaling_calls": 0,
        "ledger_sha256": sha256_file(LEDGER) if LEDGER.exists() else None,
        "pacing_ledger_sha256": sha256_file(PACING_LEDGER) if PACING_LEDGER.exists() else None,
        "authorization_sha256": auth_sha,
        "authorization_closed": True,
    }


def close_authorization() -> dict[str, Any]:
    if CLOSURE.exists():
        return load(AUDIT)
    try:
        audit = build_audit()
    except Exception as exc:
        records = load(LEDGER) if LEDGER.exists() else []
        audit = {
            "schema_version": 10,
            "experiment": "acl2027_phase2_development_acquisition_v10",
            "status": "audit_failed_closed",
            "error": f"{type(exc).__name__}: {exc}",
            "provider_attempts": len(records),
            "authorization_sha256": sha256_file(AUTH),
            "authorization_closed": True,
            "formal_history_calls": 0,
            "probe_calls": 0,
            "held_out_calls": 0,
            "formal_scaling_calls": 0,
        }
    write_json_atomic(AUDIT, audit)
    closure = {
        "schema_version": 10,
        "authorization_id": AUTHORIZATION_ID,
        "status": "closed_completed" if audit["status"] == "completed" else "closed_terminal_hard_stop",
        "authorization_sha256": sha256_file(AUTH),
        "audit_sha256": sha256_file(AUDIT),
        "provider_attempts": audit.get("provider_attempts"),
        "later_stages_authorized": False,
    }
    write_json_atomic(CLOSURE, closure)
    write_json_atomic(
        REGISTRY,
        {
            "schema_version": 10,
            "authorizations": {},
            "closed_authorizations": {
                AUTHORIZATION_ID: {
                    "path": "../../configs/acl2027/phase2_development_acquisition_authorization_v10.json",
                    "sha256": sha256_file(AUTH),
                }
            },
        },
    )
    REPORT.write_text(
        render_report(
            "The development-acquisition authorization is closed. No later Phase 2 stage ran.",
            audit,
        ),
        encoding="utf-8",
    )
    return audit


def execute_live() -> dict[str, Any]:
    if CLOSURE.exists():
        raise HardStop("v10 authorization already closed")
    auth, _ = validate_authorization()
    adapter = QwenTokenPlanProviderAdapter(auth)
    provider = PersistentRequestStartPacer(adapter)
    try:
        records = execute_requests(provider)
    except KeyboardInterrupt:
        raise
    except BaseException:
        close_authorization()
        raise
    audit = close_authorization()
    return {
        "status": "development-acquisition-complete-authorization-closed",
        "rows": len(records),
        "audit": audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "open", "preflight", "execute", "audit"))
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, sort_keys=True))
        return 0
    if args.command == "open":
        auth = open_authorization()
        print(json.dumps({"status": "authorization-open", "authorization_id": auth["authorization_id"]}, indent=2))
        return 0
    if args.command == "preflight":
        validate_preflight()
        if AUTH.exists() and not CLOSURE.exists():
            validate_authorization()
            status = "live-preflight-passed-open"
        else:
            status = "preflight-passed-closed"
        print(json.dumps({"status": status, "network_calls": 0, "provider_calls": 0}, indent=2))
        return 0
    if args.command == "audit":
        audit = close_authorization()
        print(json.dumps(audit, indent=2, sort_keys=True))
        return 0 if audit["status"] == "completed" else 1
    print(json.dumps(execute_live(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
