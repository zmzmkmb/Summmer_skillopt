#!/usr/bin/env python3
"""Validate and, only when authorized, execute ACL 2027 Phase 1S."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_phase1r_development import (
    RunnerError,
    execute_plan,
    read_json,
    sha256_file,
    stable_hash,
)

DEFAULT_CONFIG = (
    ROOT / "configs/acl2027/phase1s_development_method_effect_live_v1.json"
)
TOKEN_PLAN_ENDPOINT = (
    "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
)


def validate_config_data(config: dict[str, Any]) -> None:
    if config.get("phase") != "1S":
        raise RunnerError("config phase must be 1S")
    execution = config["execution"]
    endpoint = str(execution["endpoint"]).rstrip("/")
    if endpoint != TOKEN_PLAN_ENDPOINT:
        raise RunnerError("Phase 1S requires the user-confirmed Token Plan endpoint")
    if execution["endpoint_class"] != "token_plan_user_confirmed":
        raise RunnerError("provider endpoint class drift")
    if execution["model_id"] != "qwen3.7-plus":
        raise RunnerError("Phase 1S model drift")
    if (
        execution["logical_calls"] != 192
        or execution["physical_requests"] != 192
        or execution["max_provider_attempts_per_logical_call"] != 1
        or execution["sdk_max_retries"] != 0
        or execution["explicit_retries"] != 0
        or execution["request_interval_seconds"] != 1.0
    ):
        raise RunnerError("Phase 1S call or retry contract changed")
    if "max_tokens" not in execution["request_body_forbidden_keys"]:
        raise RunnerError("max_tokens omission is not frozen")
    cost = config["cost_control"]
    if (
        cost["accounting_ceiling"] != 200.0
        or cost["accounting_ceiling_is_request_parameter"] is not False
        or cost["max_tokens_is_cost_control"] is not False
    ):
        raise RunnerError("accounting ceiling semantics changed")
    authorization = config["authorization_gate"]
    if (
        authorization["status"] != "authorized"
        or authorization["authorized_calls"] != 192
        or authorization["authorized_model"] != "qwen3.7-plus"
        or authorization["qwen3.8_max_allowed"]
    ):
        raise RunnerError("qwen3.8-max must remain closed")


def load_frozen_plan(
    config_path: Path = DEFAULT_CONFIG,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    validate_config_data(config)
    for name, source in config["source_contracts"].items():
        path = ROOT / source["path"]
        if not path.is_file() or sha256_file(path) != source["sha256"]:
            raise RunnerError(f"immutable source hash mismatch: {name}")
    binding = config["immutable_request_plan"]
    plan_path = ROOT / binding["path"]
    if sha256_file(plan_path) != binding["file_sha256"]:
        raise RunnerError("immutable request-plan file hash mismatch")
    plan = read_json(plan_path)
    if stable_hash(plan) != binding["stable_sha256"]:
        raise RunnerError("immutable request-plan stable hash mismatch")
    if len(plan) != binding["logical_calls"] or len(plan) != 192:
        raise RunnerError("immutable request-plan call-count drift")
    if sum(row["branch"] == "candidate" for row in plan) != 96:
        raise RunnerError("candidate branch count drift")
    if sum(row["branch"] == "fallback" for row in plan) != 96:
        raise RunnerError("fallback branch count drift")
    if len({row["request_hash"] for row in plan}) != binding["unique_request_bodies"]:
        raise RunnerError("unique request-body count drift")
    if any("max_tokens" in row["request"] for row in plan):
        raise RunnerError("frozen request plan contains max_tokens")
    if any(row["request"]["model"] != "qwen3.7-plus" for row in plan):
        raise RunnerError("frozen request-plan model drift")
    return config, plan


def assert_live_authorized(config: dict[str, Any]) -> None:
    execution = config["execution"]
    authorization = config["authorization_gate"]
    state = read_json(ROOT / "paper/acl2027/experiment_state.json")
    if not (
        execution["paid_api_allowed"] is True
        and execution["network_calls_allowed"] is True
        and execution["provider_calls_authorized"] == 192
        and authorization["status"] == "authorized"
        and state["execution_policy"]["paid_api_allowed"] is True
        and state["current_phase"]["id"] == "1S"
        and state["current_phase"]["status"] == "in_progress"
    ):
        raise PermissionError("Phase 1S paid execution is closed")
    key = os.environ.get(execution["api_key_env"], "").strip()
    if not key.startswith(execution["api_key_prefix"]):
        raise PermissionError("the authorized Token Plan sk- key is required")


def openai_provider(config: dict[str, Any]):
    assert_live_authorized(config)
    from openai import OpenAI

    execution = config["execution"]
    client = OpenAI(
        api_key=os.environ[execution["api_key_env"]],
        base_url=execution["endpoint"].rstrip("/"),
        max_retries=0,
    )
    last_started_at: float | None = None

    def call(request: dict[str, Any]) -> dict[str, Any]:
        nonlocal last_started_at
        if "max_tokens" in request:
            raise RunnerError("max_tokens is forbidden")
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
        return {
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

    return call


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    config, plan = load_frozen_plan(args.config)
    if not args.live:
        print(
            json.dumps(
                {
                    "mode": "zero-network-eligibility",
                    "endpoint_class": config["execution"]["endpoint_class"],
                    "logical_calls": len(plan),
                    "request_plan_sha256": stable_hash(plan),
                    "max_tokens_omitted": all(
                        "max_tokens" not in row["request"] for row in plan
                    ),
                    "paid_api_allowed": config["execution"]["paid_api_allowed"],
                    "network_calls_allowed": config["execution"][
                        "network_calls_allowed"
                    ],
                    "list_price_estimate_cny": config["cost_control"][
                        "list_price_estimate_cny"
                    ],
                    "accounting_ceiling_cny": config["cost_control"][
                        "accounting_ceiling"
                    ],
                },
                indent=2,
            )
        )
        return 0
    if args.output_dir is None:
        raise RunnerError("--output-dir is required for live execution")
    provider = openai_provider(config)
    execute_plan(deepcopy(plan), args.output_dir, provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
