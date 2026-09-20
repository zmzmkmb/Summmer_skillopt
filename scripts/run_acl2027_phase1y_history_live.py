#!/usr/bin/env python3
"""Execute the exact authorized Phase 1Y history-generation plan."""
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
    HardStop, PreflightError, exact_usage, parse_response, read_json,
    sha256_file, stable_hash, verify_response, write_json,
)

CONFIG = ROOT / "configs/acl2027/phase1y_history_live_authorized_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1y_history_live_v1"


def _private(plan: list[dict[str, Any]]) -> dict[str, Any]:
    search = {str(r["id"]): r for r in read_json(ROOT / "data/searchqa_split/train/items.json")}
    wiki = {str(r["id"]): r for r in read_json(ROOT / "data/2wikimultihopqa_verified/partitions/history.json")}
    result = {}
    for row in plan:
        if row["task_family"] == "SearchQA":
            source = search[row["task_id"]]
            private = {"task_family": "SearchQA", "task_id": row["task_id"], "answers": source["answers"]}
        else:
            source = wiki[row["task_id"]]
            private = {"task_family": "2WikiMultiHopQA", "task_id": row["task_id"], "answers": [source["answer"]], "supporting_evidence": source["supporting_evidence"]}
        result[row["logical_call_id"]] = private
    return result


def validate_live_config(path: Path = CONFIG) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = read_json(path)
    execution, authorization = config["execution"], config["authorization"]
    if not (config["phase"] == "1Y" and config["status"] == "authorized"
            and execution["paid_api_allowed"] and execution["network_calls_allowed"]
            and execution["provider_calls_authorized"] == authorization["authorized_calls"] == 10
            and execution["model_id"] == authorization["authorized_model"] == "qwen3.7-plus"
            and execution["sdk_max_retries"] == execution["explicit_retries"] == 0
            and execution["enable_thinking"] is False and "max_tokens" in execution["forbidden_request_keys"]
            and authorization["phase1z_calls_allowed"] is False):
        raise PreflightError("Phase 1Y authorization drift")
    binding = config["plan_binding"]
    plan_path = ROOT / binding["path"]
    plan = read_json(plan_path)
    if sha256_file(plan_path) != binding["file_sha256"] or stable_hash(plan) != binding["stable_sha256"] or len(plan) != 10:
        raise PreflightError("Phase 1Y plan binding drift")
    if len({r["logical_call_id"] for r in plan}) != 10 or any(r["call_index"] != i for i, r in enumerate(plan, 1)):
        raise PreflightError("Phase 1Y call identity drift")
    if any(stable_hash(r["request"]) != r["request_hash"] or "max_tokens" in r["request"] for r in plan):
        raise PreflightError("Phase 1Y request hash drift")
    return config, plan, _private(plan)


def cost_cny(config: dict[str, Any], usage: dict[str, int]) -> float:
    cost = config["cost_control"]
    return (usage["input_tokens"] * cost["input_cny_per_million"] + usage["output_tokens"] * cost["output_cny_per_million"]) / 1_000_000


def assert_repository_authorized(config: dict[str, Any]) -> None:
    state = read_json(ROOT / "paper/acl2027/experiment_state.json")
    if not (state["execution_policy"]["paid_api_allowed"] is True and state["current_phase"]["id"] == "1Z"
            and any("exact Phase 1Y 10-attempt history plan" in x for x in state["current_phase"]["next_actions"])):
        raise PermissionError("Phase 1Y repository paid permission is closed")
    key = os.environ.get(config["execution"]["api_key_env"], "").strip()
    if not key.startswith(config["execution"]["api_key_prefix"]):
        raise PermissionError("authorized Token Plan key is required")


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def summarize(config: dict[str, Any], plan: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    usage = {k: sum(int(r.get(k, 0)) for r in records) for k in ("input_tokens", "output_tokens", "total_tokens")}
    verified = [r for r in records if r.get("joint_correct") is True]
    by_family = {f: sum(r["task_family"] == f for r in verified) for f in ("SearchQA", "2WikiMultiHopQA")}
    return {"schema_version": 1, "status": "hard_stopped" if records and records[-1].get("terminal") else "completed" if len(records) == len(plan) else "paused", "planned_logical_calls": 10, "recorded_calls": len(records), "provider_attempts": len(records), "verified_trajectories": len(verified), "verified_by_family": by_family, "usage": usage, "exact_accounted_cost_cny": cost_cny(config, usage), "plan_sha256": stable_hash(plan)}


def execute_live(config: dict[str, Any], plan: list[dict[str, Any]], private: dict[str, Any], output: Path, provider: Callable[[dict[str, Any]], dict[str, Any]], *, max_new_calls: int | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.jsonl"
    records = _records(results_path)
    for i, record in enumerate(records):
        expected = plan[i]
        if any(record.get(k) != expected[k] for k in ("call_index", "logical_call_id", "request_hash")):
            raise PreflightError("non-prefix resume")
        if record.get("terminal"):
            raise HardStop("terminal failure is not resumable")
    usage = {k: sum(int(r.get(k, 0)) for r in records) for k in ("input_tokens", "output_tokens", "total_tokens")}
    made = 0
    for item in plan[len(records):]:
        if max_new_calls is not None and made >= max_new_calls:
            break
        if cost_cny(config, usage) >= config["cost_control"]["accounting_ceiling_cny"]:
            raise HardStop("cost ceiling")
        made += 1
        base = {k: item[k] for k in ("call_index", "logical_call_id", "task_family", "task_id", "task_type", "skill_family", "typed_scope", "request_hash", "payload_sha256", "provenance")}
        try:
            response = provider(deepcopy(item["request"]))
            exact = exact_usage(response)
        except Exception as exc:  # noqa: BLE001
            record = {**base, "status": "hard_stop", "terminal": True, "usage_known": False, "error_type": type(exc).__name__, "error": str(exc)}
        else:
            raw = response.get("content")
            common = {**base, **exact, "terminal": False, "usage_known": True, "raw_response_text": raw, "raw_response_sha256": stable_hash(raw)}
            try:
                payload = parse_response(item["task_family"], raw)
                scores = verify_response(payload, private[item["logical_call_id"]])
                record = {**common, "status": "completed", "response": payload, **scores}
            except Exception as exc:  # noqa: BLE001
                record = {**common, "status": "invalid_output", "error_type": type(exc).__name__, "error": str(exc), "joint_correct": False}
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


def openai_provider(config: dict[str, Any]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    assert_repository_authorized(config)
    from openai import OpenAI
    execution = config["execution"]
    client = OpenAI(api_key=os.environ[execution["api_key_env"]], base_url=execution["endpoint"], max_retries=0)
    last: float | None = None
    def call(request: dict[str, Any]) -> dict[str, Any]:
        nonlocal last
        if set(request) != {"messages", "temperature"} or "max_tokens" in request:
            raise PreflightError("request shape drift")
        if last is not None:
            time.sleep(max(0.0, execution["request_interval_seconds"] - (time.monotonic() - last)))
        last = time.monotonic()
        response = client.chat.completions.create(model=execution["model_id"], messages=request["messages"], temperature=request["temperature"], extra_body={"enable_thinking": False})
        usage, choices = response.usage, response.choices or []
        return {"content": str(choices[0].message.content) if choices else "", "usage": {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens, "total_tokens": usage.total_tokens} if usage else None}
    return call


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    config, plan, private = validate_live_config(args.config)
    if not args.live:
        print(json.dumps({"mode": "zero-network-check", "calls": 10, "plan_sha256": stable_hash(plan), "max_tokens_omitted": True}, indent=2))
        return 0
    manifest = execute_live(config, plan, private, args.output_dir, openai_provider(config))
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
