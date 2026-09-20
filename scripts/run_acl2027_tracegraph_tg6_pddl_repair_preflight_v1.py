#!/usr/bin/env python3
"""Zero-network preflight for the versioned TG6 derived PDDL repair.

This validates every frozen task without constructing an ALFWorld environment.
If the local ``fast_downward`` Python module is available, each derived problem
is parsed through ``pddl2sas``.  Planner availability is recorded explicitly;
it is never silently treated as a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.repair_acl2027_tracegraph_tg6_pddl_v1 import (
    ROOT,
    SYNTHETIC_RECEPTACLE,
    SYNTHETIC_RECEPTACLE_TYPE,
    atoms,
    load_json,
    resolve_gamefile,
    sha256_file,
    task_tokens,
)

CONFIG = ROOT / "configs/acl2027/tracegraph_tg6_pddl_repair_preflight_v1.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/preflight.json"


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_config(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if config.get("experiment_line") != "tracegraph-observable-state-skill-composition":
        errors.append("wrong TraceGraph research line")
    if config.get("episode_count") != 40:
        errors.append("repair preflight must cover exactly 40 frozen tasks")
    if config.get("execution_authorized") is not False:
        errors.append("repair preflight must not authorize episode execution")
    for key in ("network_calls_allowed", "provider_calls_allowed", "model_calls_allowed", "paid_api_calls_allowed"):
        if config.get(key) is not False:
            errors.append(f"{key} must be false")
    for path_key, hash_key in (
        ("heldout_schedule", "heldout_schedule_sha256"),
        ("integrity_audit", "integrity_audit_sha256"),
        ("parent_scope_config", "parent_scope_config_sha256"),
    ):
        path = root / str(config.get(path_key, ""))
        if not path.is_file():
            errors.append(f"missing {path_key}")
        elif sha256_file(path) != config.get(hash_key):
            errors.append(f"{path_key} fingerprint mismatch")
    return errors


def _target_and_location(problem: str, task: dict[str, Any]) -> tuple[str, str | None, bool]:
    target_type, _ = task_tokens(str(task["task_relative_path"]))
    parsed = atoms(problem)
    typed = {
        args[0]: args[1]
        for predicate, args in parsed
        if predicate.lower() == "objecttype" and len(args) == 2
    }
    targets = sorted(
        name for name, kind in typed.items() if kind.lower() == f"{target_type}type".lower()
    )
    pickupable = {
        args[0] for predicate, args in parsed if predicate.lower() == "pickupable" and args
    }
    receptacles = {
        args[0] for predicate, args in parsed if predicate.lower() == "inreceptacle" and args
    }
    locations = {
        args[0]: args[1]
        for predicate, args in parsed
        if predicate.lower() == "objectatlocation" and len(args) == 2
    }
    candidates = [name for name in targets if name in pickupable]
    backed = [name for name in candidates if name in receptacles]
    if backed:
        target = backed[0]
        return target, locations.get(target), True
    if len(candidates) != 1:
        raise ValueError(f"expected one pickupable target without receptacle, got {candidates}")
    target = candidates[0]
    return target, locations.get(target), False


def validate_derived_pair(source: Path, derived: Path, task: dict[str, Any]) -> dict[str, Any]:
    source_game = load_json(source)
    derived_game = load_json(derived)
    if source_game.get("pddl_domain") != derived_game.get("pddl_domain"):
        raise ValueError("derived PDDL domain differs from official source")
    if source_game.get("grammar") != derived_game.get("grammar"):
        raise ValueError("derived grammar differs from official source")
    source_problem = str(source_game.get("pddl_problem", ""))
    derived_problem = str(derived_game.get("pddl_problem", ""))
    if "dummy(val1)" in derived_problem.lower():
        raise ValueError("derived PDDL still contains dummy(val1)")
    target, location, source_had_receptacle = _target_and_location(source_problem, task)
    _derived_target, derived_location, _derived_had_receptacle = _target_and_location(derived_problem, task)
    derived_atoms = atoms(derived_problem)
    synthetic_facts = {
        (predicate.lower(), tuple(args))
        for predicate, args in derived_atoms
        if predicate.lower() in {"inreceptacle", "receptacleatlocation", "receptacletype"}
    }
    if source_had_receptacle:
        if source_problem != derived_problem:
            raise ValueError("already-valid source was changed")
        return {
            "changed": False,
            "target_object": target,
            "source_location": location,
            "derived_location": derived_location,
            "synthetic_facts_present": False,
        }
    expected = {
        ("receptacletype", (SYNTHETIC_RECEPTACLE, SYNTHETIC_RECEPTACLE_TYPE)),
        ("receptacleatlocation", (SYNTHETIC_RECEPTACLE, location)),
        ("inreceptacle", (target, SYNTHETIC_RECEPTACLE)),
    }
    if not expected.issubset(synthetic_facts):
        raise ValueError(f"derived synthetic floor facts are incomplete: missing={sorted(expected - synthetic_facts)}")
    if derived_location != location:
        raise ValueError("derived target location changed")
    return {
        "changed": True,
        "target_object": target,
        "source_location": location,
        "derived_location": derived_location,
        "synthetic_facts_present": True,
    }


def planner_parse(domain: str, problem: str) -> dict[str, Any]:
    try:
        fast_downward = importlib.import_module("fast_downward")
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "error_type": type(exc).__name__, "error": str(exc)}
    try:
        task, sas = fast_downward.pddl2sas(domain, problem, verbose=False)
        return {
            "status": "passed",
            "task_type": type(task).__name__,
            "sas_type": type(sas).__name__,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}


def run_preflight(config: dict[str, Any], manifest_path: Path, data_root: Path) -> dict[str, Any]:
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = load_json(manifest_path)
    if manifest.get("task_count") != 40 or manifest.get("repaired_task_count") != 8:
        raise ValueError("repair manifest does not describe the expected 40-task/8-repair scope")
    schedule = load_json(ROOT / config["heldout_schedule"])
    tasks = list(schedule.get("tasks") or [])
    rows: list[dict[str, Any]] = []
    for task in tasks:
        source = resolve_gamefile(data_root, task)
        relative = Path(str(task["task_relative_path"]))
        if not relative.parts or relative.parts[0] != str(task["split"]):
            relative = Path(str(task["split"])) / relative
        derived = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/derived/json_2.1.1" / relative / "game.tw-pddl"
        pair = validate_derived_pair(source, derived, task)
        game = load_json(derived)
        planner = planner_parse(str(game.get("pddl_domain", "")), str(game.get("pddl_problem", "")))
        rows.append(
            {
                "task_identity": task["task_identity"],
                "task_relative_path": task["task_relative_path"],
                "source_sha256": sha256_file(source),
                "derived_sha256": sha256_file(derived),
                **pair,
                "planner": planner,
            }
        )
    planner_statuses = [row["planner"]["status"] for row in rows]
    if all(status == "passed" for status in planner_statuses):
        status = "completed"
    elif any(status == "failed" for status in planner_statuses):
        status = "blocked_planner_parse_failure"
    else:
        status = "blocked_fast_downward_unavailable"
    result = {
        "schema_version": 1,
        "phase_id": "TG6-tracegraph-pddl-derived-repair-preflight-v1",
        "experiment_line": config["experiment_line"],
        "status": status,
        "task_count": len(rows),
        "repaired_task_count": sum(bool(row["changed"]) for row in rows),
        "planner_status_counts": {name: planner_statuses.count(name) for name in sorted(set(planner_statuses))},
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": sha256_file(manifest_path),
        "rows": rows,
        "episodes_run": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "source_files_mutated": False,
        "frozen_schedule_mutated": False,
        "terminal_tg6_artifact_mutated": False,
        "phase0_to_phase6_reuse": False,
        "fresh_execution_authorization_required": True,
        "aggregate_fingerprint": fingerprint(
            [{"task_identity": row["task_identity"], "derived_sha256": row["derived_sha256"], "planner": row["planner"]["status"]} for row in rows]
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config = load_json(args.config)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing preflight: {output}")
    result = run_preflight(config, args.manifest, args.data_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = (
        "# TraceGraph TG6 Derived PDDL Repair Preflight v1\n\n"
        f"Status: `{result['status']}`. Checked {result['task_count']} derived tasks, "
        f"including {result['repaired_task_count']} repaired targets.\n"
        "No ALFWorld episode, provider/model/API call, or Phase 0-6 reuse occurred.\n"
    )
    output.parent.joinpath("preflight_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"output": str(output), "status": result["status"], "planner_status_counts": result["planner_status_counts"]}, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
