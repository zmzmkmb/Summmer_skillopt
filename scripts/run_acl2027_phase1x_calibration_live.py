#!/usr/bin/env python3
"""Execute and score the authorized ACL 2027 Phase 1X calibration."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_acl2027_phase1v_calibration import (
    HardStop,
    PreflightError,
    exact_usage,
    parse_response,
    read_json,
    sha256_file,
    stable_hash,
    verify_response,
    write_json,
)

CONFIG = ROOT / "configs/acl2027/phase1x_calibration_live_authorized_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1x_calibration_live_v1"


def cost_cny(config: dict[str, Any], usage: dict[str, int]) -> float:
    cost = config["cost_control"]
    return (
        usage["input_tokens"] * cost["list_price_cny_per_million_input_tokens"]
        + usage["output_tokens"] * cost["list_price_cny_per_million_output_tokens"]
    ) / 1_000_000


def validate_live_config(config_path: Path = CONFIG) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = read_json(config_path)
    execution = config["execution"]
    authorization = config["authorization_gate"]
    if config.get("phase") != "1X" or not (
        execution["paid_api_allowed"] is True
        and execution["network_calls_allowed"] is True
        and execution["provider_calls_authorized"] == 24
        and execution["logical_calls"] == execution["physical_requests"] == 24
        and execution["formal_scaling_allowed"] is False
        and execution["model_id"] == "qwen3.7-plus"
        and execution["temperature"] == 0
        and execution["enable_thinking"] is False
        and execution["max_provider_attempts_per_logical_call"] == 1
        and execution["sdk_max_retries"] == execution["explicit_retries"] == 0
        and execution["request_interval_seconds"] == 1.0
        and "max_tokens" in execution["request_body_forbidden_keys"]
    ):
        raise PreflightError("Phase 1X live execution contract drift")
    if not (
        authorization["status"] == "authorized"
        and authorization["authorized_calls"] == 24
        and authorization["authorized_model"] == "qwen3.7-plus"
        and authorization["authorized_accounting_ceiling_cny"] == 100.0
        and authorization["inherited_from_phase1s"] is False
        and authorization["qwen3.8_max_allowed"] is False
        and authorization["staged_or_full_scaling_allowed"] is False
    ):
        raise PreflightError("Phase 1X authorization drift")
    cost = config["cost_control"]
    if not (
        cost["accounting_ceiling_cny"] == 100.0
        and cost["accounting_ceiling_is_request_parameter"] is False
        and cost["max_tokens_is_cost_control"] is False
        and cost["authorized_ceiling_supersedes_planning_ceiling"] is True
    ):
        raise PreflightError("Phase 1X accounting contract drift")
    binding = config["phase1w_binding"]
    for name in ("config", "audit", "manifest"):
        item = binding[name]
        if sha256_file(ROOT / item["path"]) != item["sha256"]:
            raise PreflightError(f"Phase 1W {name} binding mismatch")
    plan_item = binding["transport_plan"]
    plan_path = ROOT / plan_item["path"]
    plan = read_json(plan_path)
    if sha256_file(plan_path) != plan_item["file_sha256"] or stable_hash(plan) != plan_item["stable_sha256"] or len(plan) != 24:
        raise PreflightError("Phase 1W transport-plan binding mismatch")
    private_item = binding["evaluator_private"]
    private_path = ROOT / private_item["path"]
    private = read_json(private_path)
    if sha256_file(private_path) != private_item["file_sha256"] or stable_hash(private) != private_item["stable_sha256"]:
        raise PreflightError("evaluator-private binding mismatch")
    if any(
        stable_hash(row["request"]) != row["transport_request_hash"]
        or row["request"].get("model") != execution["model_id"]
        or row["request"].get("enable_thinking") is not False
        or row["request"].get("temperature") != 0
        or "max_tokens" in row["request"]
        for row in plan
    ):
        raise PreflightError("transport request drift")
    return config, plan, private


def assert_repository_authorized(config: dict[str, Any]) -> None:
    state = read_json(ROOT / "paper/acl2027/experiment_state.json")
    if not (
        state["execution_policy"]["paid_api_allowed"] is True
        and state["current_phase"]["id"] == "1X"
        and state["current_phase"]["status"] == "in_progress"
    ):
        raise PermissionError("Phase 1X repository paid permission is closed")
    key = os.environ.get(config["execution"]["api_key_env"], "").strip()
    if not key.startswith(config["execution"]["api_key_prefix"]):
        raise PermissionError("authorized Token Plan sk- key is required")


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(config: dict[str, Any], plan: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    usage = {key: sum(int(row.get(key, 0)) for row in records) for key in ("input_tokens", "output_tokens", "total_tokens")}
    families: dict[str, Any] = {}
    for family in ("SearchQA", "2WikiMultiHopQA"):
        rows = [row for row in records if row["task_family"] == family]
        planned = sum(item["task_family"] == family for item in plan)
        completed = [row for row in rows if row["status"] == "completed"]
        family_summary: dict[str, Any] = {
            "planned": planned,
            "recorded": len(rows),
            "contract_valid": len(completed),
            "invalid_output": sum(row["status"] == "invalid_output" for row in rows),
            "answer_correct": sum(row.get("answer_correct") is True for row in rows),
        }
        if family == "2WikiMultiHopQA":
            family_summary["support_correct"] = sum(row.get("support_correct") is True for row in rows)
            family_summary["joint_correct"] = sum(row.get("joint_correct") is True for row in rows)
        else:
            family_summary["joint_correct"] = family_summary["answer_correct"]
        families[family] = family_summary
    terminal = bool(records and records[-1].get("terminal"))
    return {
        "schema_version": 1,
        "status": "hard_stopped" if terminal else "completed_with_invalid_outputs" if len(records) == len(plan) and any(row["status"] == "invalid_output" for row in records) else "completed" if len(records) == len(plan) else "paused",
        "planned_logical_calls": len(plan),
        "recorded_calls": len(records),
        "provider_attempts": len(records),
        "usage_known_for_all_attempts": all(row.get("usage_known") is True for row in records),
        "raw_response_preserved_for_known_usage_attempts": all("raw_response_text" in row for row in records if row.get("usage_known") is True),
        "usage": usage,
        "exact_accounted_cost_cny": cost_cny(config, usage),
        "families": families,
        "transport_plan_sha256": stable_hash(plan),
    }


def execute_live(
    config: dict[str, Any],
    plan: list[dict[str, Any]],
    private: dict[str, Any],
    output: Path,
    provider: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    max_new_calls: int | None = None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "transport_plan.json"
    if plan_path.exists() and stable_hash(read_json(plan_path)) != stable_hash(plan):
        raise PreflightError("transport plan drift")
    if not plan_path.exists():
        write_json(plan_path, plan)
    results_path = output / "results.jsonl"
    records = _records(results_path)
    if len(records) > len(plan):
        raise PreflightError("call-count drift")
    seen: set[str] = set()
    for index, record in enumerate(records):
        expected = plan[index]
        if any(record.get(key) != expected[key] for key in ("call_index", "logical_call_id", "scientific_request_hash", "transport_request_hash")):
            raise PreflightError("completed records are not an exact transport-plan prefix")
        if record["logical_call_id"] in seen:
            raise PreflightError("duplicate logical call ID")
        seen.add(record["logical_call_id"])
        if record.get("terminal"):
            raise HardStop("terminal failure is not resumable")
    usage = {key: sum(int(row.get(key, 0)) for row in records) for key in ("input_tokens", "output_tokens", "total_tokens")}
    made = 0
    for item in plan[len(records):]:
        if max_new_calls is not None and made >= max_new_calls:
            break
        if len(records) >= config["authorization_gate"]["authorized_calls"]:
            raise HardStop("authorized call count exhausted")
        if cost_cny(config, usage) >= config["cost_control"]["accounting_ceiling_cny"]:
            raise HardStop("accounting ceiling reached before provider attempt")
        made += 1
        base = {key: item[key] for key in ("call_index", "logical_call_id", "task_family", "task_id", "scientific_request_hash", "transport_request_hash")}
        try:
            response = provider(deepcopy(item["request"]))
        except Exception as exc:  # noqa: BLE001
            record = {**base, "status": "hard_stop", "terminal": True, "usage_known": False, "error_stage": "provider", "error_type": type(exc).__name__, "error": str(exc)}
        else:
            try:
                exact = exact_usage(response)
            except Exception as exc:  # noqa: BLE001
                record = {**base, "status": "hard_stop", "terminal": True, "usage_known": False, "error_stage": "usage", "error_type": type(exc).__name__, "error": str(exc)}
            else:
                raw = response.get("content")
                common = {**base, **exact, "terminal": False, "usage_known": True, "raw_response_text": raw, "raw_response_sha256": stable_hash(raw)}
                try:
                    payload = parse_response(item["task_family"], raw)
                except Exception as exc:  # noqa: BLE001
                    record = {**common, "status": "invalid_output", "error_stage": "response_contract", "error_type": type(exc).__name__, "error": str(exc)}
                else:
                    record = {**common, "status": "completed", "response": payload, **verify_response(payload, private[item["logical_call_id"]])}
                for key in usage:
                    usage[key] += exact[key]
        with results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        records.append(record)
        write_json(output / "run_manifest.json", summarize(config, plan, records))
        if record["terminal"]:
            break
    manifest = summarize(config, plan, records)
    write_json(output / "run_manifest.json", manifest)
    return manifest


def openai_provider(config: dict[str, Any], output: Path) -> Callable[[dict[str, Any]], dict[str, Any]]:
    assert_repository_authorized(config)
    from openai import OpenAI

    execution = config["execution"]
    client = OpenAI(api_key=os.environ[execution["api_key_env"]], base_url=execution["endpoint"].rstrip("/"), max_retries=0)
    last_started_at: float | None = None

    def call(request: dict[str, Any]) -> dict[str, Any]:
        nonlocal last_started_at
        if set(request) != {"messages", "temperature", "model", "enable_thinking"} or "max_tokens" in request:
            raise PreflightError("live transport request shape drift")
        if last_started_at is not None:
            remaining = execution["request_interval_seconds"] - (time.monotonic() - last_started_at)
            if remaining > 0:
                time.sleep(remaining)
        last_started_at = time.monotonic()
        response = client.chat.completions.create(
            model=request["model"],
            messages=request["messages"],
            temperature=request["temperature"],
            extra_body={"enable_thinking": request["enable_thinking"]},
        )
        usage = getattr(response, "usage", None)
        choices = getattr(response, "choices", None) or []
        return {
            "content": str(getattr(choices[0].message, "content", "")) if choices else "",
            "usage": {"input_tokens": getattr(usage, "prompt_tokens", None), "output_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None)} if usage is not None else None,
        }

    return call


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    config, plan, private = validate_live_config(args.config)
    if not args.live:
        print(json.dumps({"mode": "zero-network-authorized-config-check", "logical_calls": len(plan), "transport_plan_sha256": stable_hash(plan), "authorized_calls": config["authorization_gate"]["authorized_calls"], "accounting_ceiling_cny": config["cost_control"]["accounting_ceiling_cny"], "max_tokens_omitted": all("max_tokens" not in row["request"] for row in plan)}, indent=2))
        return 0
    manifest = execute_live(config, plan, private, args.output_dir, openai_provider(config, args.output_dir))
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] in {"completed", "completed_with_invalid_outputs"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
