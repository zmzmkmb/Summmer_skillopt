#!/usr/bin/env python3
"""Zero-action TextWorld reset preflight for TG6 repair v2."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tracegraph_tg6_pddl_derived_repair_v2.pending/repair_manifest.json"
DEFAULT_OUTPUT = ROOT / "tracegraph_tg6_textworld_zero_step_preflight_v2.pending.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_builder():
    module_path = ROOT / "skillopt/envs/alfworld/vendor/alfworld_envs.py"
    spec = importlib.util.spec_from_file_location("tracegraph_alfworld_envs_zero_step", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_alfworld_envs


def probe_one(build_env: Any, gamefile: Path, split: str, ordinal: int) -> dict[str, Any]:
    dataset = "eval_in_distribution" if split == "valid_seen" else "eval_out_of_distribution"
    env = build_env(
        str(ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml"),
        seed=1000 + ordinal,
        env_num=1,
        group_n=1,
        resources_per_worker=None,
        is_train=False,
        env_kwargs={"eval_dataset": dataset},
        gamefiles=[str(gamefile)],
    )
    try:
        observations, _images, infos = env.reset()
        return {"status": "passed", "observation_present": bool(observations and observations[0]), "info_present": bool(infos and isinstance(infos[0], dict)), "actions_taken": 0}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error_type": type(exc).__name__, "error": str(exc), "actions_taken": 0}
    finally:
        env.close()


def run(manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    builder = load_builder()
    rows = []
    for ordinal, item in enumerate(manifest.get("rows_detail") or []):
        gamefile = ROOT / str(item["derived_gamefile"]).replace(chr(92), "/")
        probe = probe_one(builder, gamefile, str(item["split"]), ordinal)
        rows.append({"task_identity": item["task_identity"], "task_relative_path": item["task_relative_path"], "derived_gamefile": str(gamefile.relative_to(ROOT)).replace(chr(92), "/"), "derived_sha256": sha256(gamefile), **probe})
    statuses = [row["status"] for row in rows]
    return {
        "schema_version": 2,
        "phase_id": "TG6-tracegraph-textworld-zero-step-preflight-v2",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "status": "passed" if rows and all(status == "passed" for status in statuses) else "blocked_textworld_reset",
        "task_count": len(rows),
        "passed_task_count": statuses.count("passed"),
        "failed_task_count": statuses.count("failed"),
        "manifest": str(manifest_path.relative_to(ROOT)).replace(chr(92), "/"),
        "manifest_sha256": sha256(manifest_path),
        "alfworld_data": os.environ.get("ALFWORLD_DATA", ""),
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    result = run(args.manifest)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    print(f"TG6 TextWorld zero-step preflight: passed={result['passed_task_count']}/{result['task_count']}; failed={result['failed_task_count']}; actions=0")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
