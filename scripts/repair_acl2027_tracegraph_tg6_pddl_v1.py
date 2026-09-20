#!/usr/bin/env python3
"""Build a versioned, derived PDDL repair for the frozen TG6 schedule.

The official ALFWorld files are never edited.  The only repair performed is to
give a pickupable target that is represented on the floor an explicit,
non-openable synthetic receptacle at its existing location.  This makes the
vendored ALFRED ``PickupObject`` precondition represent the observed state
without inventing a container, moving an object, or changing the domain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / "artifacts/acl2027_tracegraph_tg4_heldout_mechanism_preflight_v1/heldout_schedule.json"
INTEGRITY_AUDIT = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_integrity_audit_v1/audit.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1"
SYNTHETIC_RECEPTACLE = "TraceGraphFloorReceptacle"
SYNTHETIC_RECEPTACLE_TYPE = "TraceGraphFloorType"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


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
    section = re.sub(r";[^\n]*", "", init_section(problem))
    return [
        (match.group(1), match.group(2).split())
        for match in re.finditer(r"\(([^()\s]+)([^()]*)\)", section)
    ]


def resolve_gamefile(data_root: Path, task: dict[str, Any]) -> Path:
    relative = Path(str(task["task_relative_path"]))
    split = str(task["split"])
    if not relative.parts or relative.parts[0] != split:
        relative = Path(split) / relative
    return data_root / "json_2.1.1" / relative / "game.tw-pddl"


def _target_facts(problem: str, task: dict[str, Any]) -> tuple[str, str, list[str], list[str]]:
    target_type, _light_type = task_tokens(str(task["task_relative_path"]))
    parsed = atoms(problem)
    typed = {
        args[0]: args[1]
        for predicate, args in parsed
        if predicate.lower() == "objecttype" and len(args) == 2
    }
    target_objects = sorted(
        name for name, kind in typed.items() if kind.lower() == f"{target_type}type".lower()
    )
    pickupable = {
        args[0] for predicate, args in parsed if predicate.lower() == "pickupable" and args
    }
    in_receptacle = {
        args[0] for predicate, args in parsed if predicate.lower() == "inreceptacle" and args
    }
    locations = {
        args[0]: args[1]
        for predicate, args in parsed
        if predicate.lower() == "objectatlocation" and len(args) == 2
    }
    # The ALFRED goal is existential over the target type.  If any target
    # instance already has a receptacle, the task is not blocked and must be
    # copied unchanged even when a distractor instance is on the floor.
    if any(name in in_receptacle for name in target_objects):
        return target_type, SYNTHETIC_RECEPTACLE, [], []
    missing = [name for name in target_objects if name in pickupable and name not in in_receptacle]
    return target_type, SYNTHETIC_RECEPTACLE, missing, [locations[name] for name in missing if name in locations]


def _insert_before_last_close(problem: str, start: int, end: int, addition: str) -> str:
    close = problem.rfind(")", start, end)
    if close < 0:
        raise ValueError("PDDL section has no closing parenthesis")
    return problem[:close] + addition + problem[close:]


def derive_problem(problem: str, task: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    _target_type, synthetic_name, missing, locations = _target_facts(problem, task)
    if len(missing) == 0:
        return problem, {
            "changed": False,
            "repair_reason": "target already has inReceptacle or is not a missing pickupable target",
            "target_object": None,
            "synthetic_receptacle": None,
            "synthetic_location": None,
        }
    if len(missing) != 1 or len(locations) != 1:
        raise ValueError(
            "repair requires exactly one pickupable target without inReceptacle and one objectAtLocation"
        )
    target = missing[0]
    location = locations[0]
    if re.search(rf"\b{re.escape(synthetic_name)}\b", problem):
        raise ValueError(f"synthetic receptacle name already exists: {synthetic_name}")

    init_start = re.search(r"\(:init\b", problem, flags=re.IGNORECASE)
    goal_start = re.search(r"\(:goal\b", problem, flags=re.IGNORECASE)
    objects_start = re.search(r"\(:objects\b", problem, flags=re.IGNORECASE)
    if not init_start or not goal_start or not objects_start:
        raise ValueError("PDDL problem is missing objects/init/goal section")
    if not (objects_start.start() < init_start.start() < goal_start.start()):
        raise ValueError("PDDL section ordering is unsupported")

    object_addition = (
        f"\n        {synthetic_name} - receptacle"
        f"\n        {SYNTHETIC_RECEPTACLE_TYPE} - rtype\n        "
    )
    repaired = _insert_before_last_close(
        problem, objects_start.start(), init_start.start(), object_addition
    )
    # Recompute section boundaries after inserting object declarations.
    init_start = re.search(r"\(:init\b", repaired, flags=re.IGNORECASE)
    goal_start = re.search(r"\(:goal\b", repaired, flags=re.IGNORECASE)
    assert init_start and goal_start
    facts = (
        f"\n        (receptacleType {synthetic_name} {SYNTHETIC_RECEPTACLE_TYPE})"
        f"\n        (receptacleAtLocation {synthetic_name} {location})"
        f"\n        (inReceptacle {target} {synthetic_name})\n        "
    )
    repaired = _insert_before_last_close(repaired, init_start.start(), goal_start.start(), facts)
    return repaired, {
        "changed": True,
        "repair_reason": "pickupable target had objectAtLocation but no inReceptacle",
        "target_object": target,
        "synthetic_receptacle": synthetic_name,
        "synthetic_location": location,
    }


def derive_game(source: Path, destination: Path, task: dict[str, Any]) -> dict[str, Any]:
    source_bytes = source.read_bytes()
    game = load_json(source)
    problem = str(game.get("pddl_problem", ""))
    repaired_problem, metadata = derive_problem(problem, task)
    if metadata["changed"]:
        game["pddl_problem"] = repaired_problem
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(game, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    try:
        derived_display = str(destination.relative_to(ROOT))
    except ValueError:
        derived_display = str(destination)
    return {
        "task_identity": task["task_identity"],
        "split": task["split"],
        "task_relative_path": task["task_relative_path"],
        "source_gamefile": str(source),
        "derived_gamefile": derived_display,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "derived_sha256": sha256_file(destination),
        **metadata,
    }


def build_repair(data_root: Path, output_root: Path, schedule_path: Path = SCHEDULE) -> dict[str, Any]:
    schedule = load_json(schedule_path)
    tasks = list(schedule.get("tasks") or [])
    if len(tasks) != 40:
        raise ValueError(f"expected frozen 40-task schedule, got {len(tasks)}")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing repair output: {output_root}")
    derived_root = output_root / "derived"
    rows: list[dict[str, Any]] = []
    for task in tasks:
        source = resolve_gamefile(data_root, task)
        if not source.is_file():
            raise FileNotFoundError(source)
        relative = Path(str(task["task_relative_path"]))
        if not relative.parts or relative.parts[0] != str(task["split"]):
            relative = Path(str(task["split"])) / relative
        destination = derived_root / "json_2.1.1" / relative / "game.tw-pddl"
        rows.append(derive_game(source, destination, task))

    changed_rows = [row for row in rows if row["changed"]]
    aggregate = fingerprint(
        [{key: row[key] for key in ("task_identity", "source_sha256", "derived_sha256", "changed")} for row in rows]
    )
    manifest = {
        "schema_version": 1,
        "phase_id": "TG6-tracegraph-pddl-derived-repair-v1",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "status": "complete",
        "completed_calls": 40,
        "rows": 40,
        "aggregate_fingerprint": aggregate,
        "schedule": str(schedule_path.relative_to(ROOT)),
        "schedule_sha256": sha256_file(schedule_path),
        "source_data_root": str(data_root),
        "source_files_mutated": False,
        "frozen_schedule_mutated": False,
        "terminal_tg6_artifact_mutated": False,
        "phase0_to_phase6_reuse": False,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "episodes_run": 0,
        "repair_rule": "Only missing target inReceptacle facts are repaired using a synthetic non-openable floor receptacle at the existing objectAtLocation.",
        "synthetic_receptacle": SYNTHETIC_RECEPTACLE,
        "synthetic_receptacle_type": SYNTHETIC_RECEPTACLE_TYPE,
        "task_count": 40,
        "repaired_task_count": len(changed_rows),
        "unchanged_task_count": len(rows) - len(changed_rows),
        "rows_detail": rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "repair_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / "repair.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = (
        "# TraceGraph TG6 Derived PDDL Repair v1\n\n"
        f"Built {len(rows)} derived game files; repaired {len(changed_rows)} target states.\n"
        "The official source files, frozen schedule, and terminal TG6 artifact were not modified.\n"
        "No episodes or network/provider/model/API calls were run.\n"
    )
    (output_root / "report.md").write_text(report, encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, default=SCHEDULE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_root = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    result = build_repair(args.data_root, output_root, args.schedule)
    print(json.dumps({"output_root": str(output_root), "task_count": 40, "repaired_task_count": result["repaired_task_count"], "aggregate_fingerprint": result["aggregate_fingerprint"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
