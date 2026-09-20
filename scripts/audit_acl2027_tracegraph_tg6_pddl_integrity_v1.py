#!/usr/bin/env python3
"""Read-only integrity audit for the frozen TraceGraph TG6 ALFWorld schedule."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / "artifacts/acl2027_tracegraph_tg4_heldout_mechanism_preflight_v1/heldout_schedule.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_integrity_audit_v1/audit.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def task_tokens(task_relative_path: str) -> tuple[str, str]:
    leaf = Path(task_relative_path).parent.name
    prefix = "look_at_obj_in_light-"
    if not leaf.startswith(prefix) or "-None-" not in leaf:
        raise ValueError(f"unsupported TG6 task path: {task_relative_path}")
    target, suffix = leaf[len(prefix) :].split("-None-", 1)
    light, scene = suffix.rsplit("-", 1)
    if not scene.isdigit():
        raise ValueError(f"unsupported TG6 task scene token: {task_relative_path}")
    return target, light


def init_section(problem: str) -> str:
    match = re.search(r"\(:init\b(.*?)\(:goal\b", problem, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("PDDL problem has no :init/:goal section")
    return match.group(1)


def atoms(problem: str) -> list[tuple[str, list[str]]]:
    section = init_section(problem)
    section = re.sub(r";[^\n]*", "", section)
    result: list[tuple[str, list[str]]] = []
    for match in re.finditer(r"\(([^()\s]+)([^()]*)\)", section):
        predicate = match.group(1)
        args = match.group(2).split()
        result.append((predicate, args))
    return result


def inspect_task(data_root: Path, task: dict[str, Any]) -> dict[str, Any]:
    relative = Path(str(task["task_relative_path"]))
    gamefile = data_root / "json_2.1.1" / relative / "game.tw-pddl"
    result: dict[str, Any] = {
        "task_identity": task["task_identity"],
        "split": task["split"],
        "task_relative_path": task["task_relative_path"],
        "gamefile": str(gamefile),
        "gamefile_exists": gamefile.is_file(),
        "issues": [],
    }
    if not gamefile.is_file():
        result["issues"].append("missing_gamefile")
        return result

    game = load_json(gamefile)
    problem = str(game.get("pddl_problem", ""))
    parsed = atoms(problem)
    typed: dict[str, str] = {}
    for predicate, args in parsed:
        if predicate.lower() == "objecttype" and len(args) == 2:
            typed[args[0]] = args[1]

    target_type, light_type = task_tokens(str(task["task_relative_path"]))
    target_objects = sorted(name for name, kind in typed.items() if kind.lower() == f"{target_type}type".lower())
    light_objects = sorted(name for name, kind in typed.items() if kind.lower() == f"{light_type}type".lower())
    in_receptacle = {args[0] for predicate, args in parsed if predicate.lower() == "inreceptacle" and args}
    pickupable = {args[0] for predicate, args in parsed if predicate.lower() == "pickupable" and args}
    toggleable = {args[0] for predicate, args in parsed if predicate.lower() == "toggleable" and args}

    target_with_container = [name for name in target_objects if name in in_receptacle]
    light_with_container = [name for name in light_objects if name in in_receptacle]
    result.update(
        {
            "target_type": target_type,
            "light_type": light_type,
            "target_objects": target_objects,
            "target_pickupable": [name for name in target_objects if name in pickupable],
            "target_in_receptacle": target_with_container,
            "light_objects": light_objects,
            "light_toggleable": [name for name in light_objects if name in toggleable],
            "light_in_receptacle": light_with_container,
        }
    )
    if not target_objects:
        result["issues"].append("target_object_type_missing")
    elif not target_with_container:
        result["issues"].append("target_object_missing_in_receptacle")
    if not any(name in pickupable for name in target_objects):
        result["issues"].append("target_object_not_pickupable")
    if not light_objects:
        result["issues"].append("light_object_type_missing")
    elif not any(name in toggleable for name in light_objects):
        result["issues"].append("light_object_not_toggleable")
    return result


def audit(data_root: Path, schedule_path: Path = SCHEDULE) -> dict[str, Any]:
    schedule = load_json(schedule_path)
    tasks = list(schedule.get("tasks") or [])
    rows = [inspect_task(data_root, task) for task in tasks]
    issue_counts: dict[str, int] = {}
    for row in rows:
        for issue in row["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    return {
        "schema_version": 1,
        "phase_id": "TG6-tracegraph-pddl-integrity-audit-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "mode": "read_only_pddl_integrity_audit",
        "schedule": str(schedule_path.relative_to(ROOT)),
        "schedule_sha256": sha256_file(schedule_path),
        "data_root": str(data_root),
        "task_count": len(tasks),
        "rows": rows,
        "issue_counts": issue_counts,
        "blocking_rule": "ALFRED PickupObject requires inReceptacle(target, receptacle); missing target inReceptacle is an environment-integrity blocker.",
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "episodes_run": 0,
        "phase0_to_phase6_reuse": False,
        "webshop_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, default=SCHEDULE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing audit: {output}")
    result = audit(args.data_root, args.schedule)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "task_count": result["task_count"], "issue_counts": result["issue_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
