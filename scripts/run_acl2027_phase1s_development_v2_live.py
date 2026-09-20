#!/usr/bin/env python3
"""Execute the authorized ACL 2027 Phase 1S v2 live plan."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_phase1r_development import (
    RunnerError,
    exact_usage,
    read_json,
    sha256_file,
    stable_hash,
)
from scripts.run_acl2027_phase1s_development_v2 import execute_plan_v2

DEFAULT_CONFIG = (
    ROOT
    / "configs/acl2027/phase1s_development_method_effect_live_v2_authorized.json"
)


def validate_live_config(
    config_path: Path = DEFAULT_CONFIG,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    execution = config["execution"]
    authorization = config["authorization_gate"]
    if config.get("phase") != "1S":
        raise RunnerError("config phase must be 1S")
    if not (
        execution["paid_api_allowed"] is True
        and execution["network_calls_allowed"] is True
        and execution["provider_calls_authorized"] == 192
        and execution["formal_scaling_allowed"] is False
        and execution["model_id"] == "qwen3.7-plus"
        and execution["max_provider_attempts_per_logical_call"] == 1
        and execution["sdk_max_retries"] == 0
        and execution["explicit_retries"] == 0
        and execution["request_interval_seconds"] == 1.0
    ):
        raise RunnerError("Phase 1S v2 live execution contract drift")
    if "max_tokens" not in execution["request_body_forbidden_keys"]:
        raise RunnerError("max_tokens omission is not frozen")
    if not (
        authorization["status"] == "authorized"
        and authorization["authorized_calls"] == 192
        and authorization["authorized_model"] == "qwen3.7-plus"
        and authorization["authorized_accounting_ceiling_cny"] == 2000.0
        and authorization["qwen3.8_max_allowed"] is False
        and authorization["staged_384_calls_allowed"] is False
        and authorization["full_960_calls_allowed"] is False
    ):
        raise RunnerError("Phase 1S v2 authorization drift")
    cost = config["cost_control"]
    if not (
        cost["accounting_ceiling"] == 2000.0
        and cost["accounting_ceiling_is_request_parameter"] is False
        and cost["max_tokens_is_cost_control"] is False
    ):
        raise RunnerError("Phase 1S v2 accounting contract drift")

    for name, source in config["v2_preflight_binding"].items():
        if not isinstance(source, dict) or "path" not in source:
            continue
        path = ROOT / source["path"]
        if not path.is_file() or sha256_file(path) != source["sha256"]:
            raise RunnerError(f"v2 preflight binding mismatch: {name}")
    terminal = config["terminal_v1_binding"]
    for label in ("manifest", "results"):
        path = ROOT / terminal[f"{label}_path"]
        if sha256_file(path) != terminal[f"{label}_sha256"]:
            raise RunnerError(f"terminal v1 {label} hash mismatch")

    binding = config["immutable_request_plan"]
    plan_path = ROOT / binding["path"]
    if sha256_file(plan_path) != binding["file_sha256"]:
        raise RunnerError("immutable request-plan file hash mismatch")
    plan = read_json(plan_path)
    if stable_hash(plan) != binding["stable_sha256"] or len(plan) != 192:
        raise RunnerError("immutable request-plan drift")
    if any("max_tokens" in row["request"] for row in plan):
        raise RunnerError("request plan contains max_tokens")
    return config, plan


def assert_repository_authorized(config: dict[str, Any]) -> None:
    state = read_json(ROOT / "paper/acl2027/experiment_state.json")
    if not (
        state["execution_policy"]["paid_api_allowed"] is True
        and state["current_phase"]["id"] == "1S"
        and state["current_phase"]["status"] == "in_progress"
    ):
        raise PermissionError("Phase 1S v2 repository paid permission is closed")
    execution = config["execution"]
    key = os.environ.get(execution["api_key_env"], "").strip()
    if not key.startswith(execution["api_key_prefix"]):
        raise PermissionError("authorized Token Plan sk- key is required")


def _existing_usage(output_dir: Path) -> dict[str, int]:
    path = output_dir / "results.jsonl"
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not path.exists():
        return totals
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for key in totals:
            totals[key] += int(record.get(key, 0))
    return totals


def _cost_cny(config: dict[str, Any], usage: dict[str, int]) -> float:
    cost = config["cost_control"]
    return (
        usage["input_tokens"] * cost["list_price_cny_per_million_input_tokens"]
        + usage["output_tokens"] * cost["list_price_cny_per_million_output_tokens"]
    ) / 1_000_000


def openai_provider(config: dict[str, Any], output_dir: Path):
    assert_repository_authorized(config)
    from openai import OpenAI

    execution = config["execution"]
    client = OpenAI(
        api_key=os.environ[execution["api_key_env"]],
        base_url=execution["endpoint"].rstrip("/"),
        max_retries=0,
    )
    accumulated = _existing_usage(output_dir)
    last_started_at: float | None = None

    def call(request: dict[str, Any]) -> dict[str, Any]:
        nonlocal last_started_at
        if "max_tokens" in request:
            raise RunnerError("max_tokens is forbidden")
        if _cost_cny(config, accumulated) >= config["cost_control"][
            "accounting_ceiling"
        ]:
            raise RunnerError("accounting ceiling reached before provider attempt")
        if last_started_at is not None:
            remaining = execution["request_interval_seconds"] - (
                time.monotonic() - last_started_at
            )
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
        result = {
            "content": (
                str(getattr(choices[0].message, "content", "")) if choices else ""
            ),
            "usage": (
                {
                    "input_tokens": getattr(usage, "prompt_tokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                }
                if usage is not None
                else None
            ),
        }
        known = exact_usage(result)
        for key in accumulated:
            accumulated[key] += known[key]
        return result

    return call


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    config, plan = validate_live_config(args.config)
    if not args.live:
        print(json.dumps({
            "mode": "zero-network-authorized-config-check",
            "logical_calls": len(plan),
            "request_plan_sha256": stable_hash(plan),
            "authorized_calls": config["authorization_gate"]["authorized_calls"],
            "accounting_ceiling_cny": config["cost_control"]["accounting_ceiling"],
            "max_tokens_omitted": all(
                "max_tokens" not in row["request"] for row in plan
            ),
        }, indent=2))
        return 0
    if args.output_dir is None:
        raise RunnerError("--output-dir is required for live execution")
    manifest = execute_plan_v2(
        plan, args.output_dir, openai_provider(config, args.output_dir)
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
