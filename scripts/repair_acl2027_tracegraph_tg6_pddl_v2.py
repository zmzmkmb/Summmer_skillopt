#!/usr/bin/env python3
"""Build a generalized, separately versioned TG6 PDDL repair.

The v1 repair handled only a missing receptacle for the named pickup target.
This version also repairs every goal-required toggleable object that is
represented only by objectAtLocation, while preserving source provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.repair_acl2027_tracegraph_tg6_pddl_v1 import ROOT, atoms, load_json, sha256_file

SYNTHETIC_TYPE = "TraceGraphFloorType"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2"
PARENT_MANIFEST = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/repair_manifest.json"


def _resolve_rooted(path: Path) -> Path:
    return (path if path.is_absolute() else ROOT / path).resolve()


def _insert_before_last_close(problem: str, start: int, end: int, addition: str) -> str:
    close = problem.rfind(")", start, end)
    if close < 0:
        raise ValueError("PDDL section has no closing parenthesis")
    return problem[:close] + addition + problem[close:]


def _goal_types(problem: str) -> set[str]:
    goal_match = re.search(r"\(:goal\b", problem, flags=re.IGNORECASE)
    if not goal_match:
        raise ValueError("PDDL problem has no goal")
    return set(re.findall(r"\(objectType\s+\?\w+\s+([^\s()]+)", problem[goal_match.end() :], flags=re.IGNORECASE))


def required_floor_objects(problem: str) -> list[dict[str, str]]:
    parsed = atoms(problem)
    typed = {a[0]: a[1] for p, a in parsed if p.lower() == "objecttype" and len(a) == 2}
    pickupable = {a[0] for p, a in parsed if p.lower() == "pickupable" and a}
    toggleable = {a[0] for p, a in parsed if p.lower() == "toggleable" and a}
    backed = {a[0] for p, a in parsed if p.lower() == "inreceptacle" and a}
    locations = {a[0]: a[1] for p, a in parsed if p.lower() == "objectatlocation" and len(a) == 2}
    goal = problem[re.search(r"\(:goal\b", problem, flags=re.IGNORECASE).end() :]
    needs_pickup = "(holds " in goal.lower()
    needs_toggle = "(istoggled " in goal.lower()
    result = []
    for goal_type in sorted(_goal_types(problem)):
        candidates = sorted(n for n, kind in typed.items() if kind.lower() == goal_type.lower())
        relevant = [n for n in candidates if (needs_pickup and n in pickupable) or (needs_toggle and n in toggleable)]
        if not relevant or any(n in backed for n in relevant):
            continue
        for name in relevant:
            if name in locations:
                result.append({"object": name, "location": locations[name], "goal_type": goal_type})
    return result


def derive_problem(problem: str) -> tuple[str, dict[str, Any]]:
    missing = required_floor_objects(problem)
    if not missing:
        return problem, {"changed": False, "repaired_objects": [], "repair_reason": "all goal-required interactive objects already have receptacles"}
    if "TraceGraphFloorType - rtype" in problem:
        raise ValueError("v2 synthetic type already exists")
    objects_start = re.search(r"\(:objects\b", problem, flags=re.IGNORECASE)
    init_start = re.search(r"\(:init\b", problem, flags=re.IGNORECASE)
    goal_start = re.search(r"\(:goal\b", problem, flags=re.IGNORECASE)
    if not objects_start or not init_start or not goal_start or not (objects_start.start() < init_start.start() < goal_start.start()):
        raise ValueError("unsupported PDDL section ordering")
    names = []
    for item in missing:
        suffix = hashlib.sha256(item["object"].encode("utf-8")).hexdigest()[:12]
        names.append({**item, "receptacle": f"TraceGraphFloorReceptacle_{suffix}"})
    object_addition = "\n" + "".join(f"        {x['receptacle']} - receptacle\n" for x in names) + "        TraceGraphFloorType - rtype\n        "
    repaired = _insert_before_last_close(problem, objects_start.start(), init_start.start(), object_addition)
    init_start = re.search(r"\(:init\b", repaired, flags=re.IGNORECASE)
    goal_start = re.search(r"\(:goal\b", repaired, flags=re.IGNORECASE)
    assert init_start and goal_start
    facts = "\n" + "".join(
        f"        (receptacleType {x['receptacle']} {SYNTHETIC_TYPE})\n"
        f"        (receptacleAtLocation {x['receptacle']} {x['location']})\n"
        f"        (inReceptacle {x['object']} {x['receptacle']})\n"
        for x in names
    ) + "        "
    repaired = _insert_before_last_close(repaired, init_start.start(), goal_start.start(), facts)
    return repaired, {"changed": True, "repaired_objects": names, "repair_reason": "goal-required pickup/toggle objects lacked inReceptacle"}


def derive_game(source: Path, destination: Path) -> dict[str, Any]:
    game = load_json(source)
    repaired, metadata = derive_problem(str(game.get("pddl_problem", "")))
    if metadata["changed"]:
        game["pddl_problem"] = repaired
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(game, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return {
        "source_gamefile": str(source),
        "derived_gamefile": str(destination.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_file(source),
        "derived_sha256": sha256_file(destination),
        **metadata,
    }


def build_repair(parent_manifest_path: Path, output_root: Path) -> dict[str, Any]:
    parent_manifest_path = _resolve_rooted(parent_manifest_path)
    parent = load_json(parent_manifest_path)
    tasks = list(parent.get("rows_detail") or [])
    if len(tasks) != 40:
        raise ValueError(f"expected 40 tasks, got {len(tasks)}")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite {output_root}")
    rows = []
    for task in tasks:
        source = ROOT / str(task["derived_gamefile"]).replace(chr(92), "/")
        if not source.is_file():
            raise FileNotFoundError(source)
        relative = Path(str(task["task_relative_path"]).replace(chr(92), "/"))
        if not relative.parts or relative.parts[0] != str(task["split"]):
            relative = Path(str(task["split"])) / relative
        destination = output_root / "derived" / "json_2.1.1" / relative / "game.tw-pddl"
        rows.append({"task_identity": task["task_identity"], "split": task["split"], "task_relative_path": task["task_relative_path"], **derive_game(source, destination)})
    manifest = {
        "schema_version": 2,
        "phase_id": "TG6-tracegraph-pddl-derived-repair-v2",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "status": "complete_pending_textworld_reset_audit",
        "task_count": 40,
        "repaired_task_count": sum(row["changed"] for row in rows),
        "repair_rule": "Add a unique non-openable synthetic floor receptacle for every goal-required pickupable or toggleable object lacking inReceptacle.",
        "parent_repair_manifest": str(parent_manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "parent_repair_manifest_sha256": sha256_file(parent_manifest_path),
        "schedule": parent.get("schedule"),
        "schedule_sha256": parent.get("schedule_sha256"),
        "source_files_mutated": False,
        "episodes_run": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "rows_detail": rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "repair_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, default=PARENT_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    result = build_repair(args.parent_manifest, output)
    print(json.dumps({"output_root": str(output), "task_count": 40, "repaired_task_count": result["repaired_task_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
