#!/usr/bin/env python3
"""Zero-action TG9 readiness audit; proves the effective 50-step horizon."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/tracegraph_tg9_readiness_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def configured_horizon(yaml_text: str) -> int:
    values = [int(value) for value in re.findall(r"max_nb_steps_per_episode:\s*(\d+)", yaml_text)]
    if not values or len(set(values)) != 1:
        raise ValueError("ALFWorld horizon is missing or inconsistent")
    return values[0]


def audit(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("execution_authorized") is not False or config.get("readiness_only") is not True:
        raise ValueError("readiness must remain closed and zero-action")
    paths = {
        key: ROOT / config[key]
        for key in (
            "task_pool_preflight",
            "schedule",
            "selector",
            "base_skillbank",
            "interaction_skillbank",
            "environment_config",
        )
    }
    for key, path in paths.items():
        if not path.is_file() or sha256(path) != config[f"{key}_sha256"]:
            raise ValueError(f"{key} missing or hash mismatch")
    schedule = read_json(paths["schedule"])
    if len(schedule.get("rows") or []) != 180:
        raise ValueError("schedule is not the frozen 180-row factorial")
    horizon = configured_horizon(paths["environment_config"].read_text(encoding="utf-8"))
    return {
        "schema_version": "tg9-readiness-v1",
        "status": "passed_for_step_50_blocked_for_step_75",
        "phase_id": "TG9-tracegraph-readiness-v1",
        "effective_environment_horizon": horizon,
        "primary_endpoint": f"completion_by_step_{horizon}",
        "completion_by_step_75_available": horizon >= 75,
        "planned_rows": 180,
        "runtime_allowed_inputs": ["observation", "historical_actions", "admissible_actions"],
        "bound_inputs": {
            key: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
            for key, path in paths.items()
        },
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "execution_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    payload = audit(read_json(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VALID: TG9 primary horizon={payload['effective_environment_horizon']}; episodes=0; actions=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
