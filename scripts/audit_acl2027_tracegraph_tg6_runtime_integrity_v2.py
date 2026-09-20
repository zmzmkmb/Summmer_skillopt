#!/usr/bin/env python3
"""Read-only audit for TextWorld action-precondition coverage in TG6 files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/repair_manifest.json"
TERMINAL = ROOT / "artifacts/acl2027_tracegraph_tg6_repaired_local_execution_runner_v2/result.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg6_runtime_integrity_diagnostic_v2/audit.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def section(problem: str, start: str, end: str) -> str:
    match = re.search(re.escape(start) + r"\b(.*?)" + re.escape(end), problem, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError(f"missing PDDL section: {start}")
    return match.group(1)


def atoms(text: str) -> list[tuple[str, list[str]]]:
    lines = [line.split(";", 1)[0] for line in text.splitlines()]
    clean = "\n".join(lines)
    return [(m.group(1), m.group(2).split()) for m in re.finditer(r"\(([^()\s]+)([^()]*)\)", clean)]


def audit_problem(problem: str) -> dict[str, Any]:
    init = atoms(section(problem, "(:init", "(:goal"))
    goal_marker = re.search(r"\(:goal\b", problem, flags=re.IGNORECASE)
    if not goal_marker:
        raise ValueError("missing PDDL section: (:goal")
    goal = problem[goal_marker.end() :]
    typed = {a[0]: a[1] for p, a in init if p.lower() == "objecttype" and len(a) == 2}
    backed = {a[0] for p, a in init if p.lower() == "inreceptacle" and len(a) >= 2}
    pickupable = {a[0] for p, a in init if p.lower() == "pickupable" and a}
    toggleable = {a[0] for p, a in init if p.lower() == "toggleable" and a}
    locations = {a[0]: a[1] for p, a in init if p.lower() == "objectatlocation" and len(a) == 2}
    goal_types = sorted(set(re.findall(r"\(objectType\s+\?\w+\s+([^\s()]+)", goal, flags=re.IGNORECASE)))
    requirements = []
    for goal_type in goal_types:
        candidates = sorted(n for n, kind in typed.items() if kind.lower() == goal_type.lower())
        requires_pickup = "(holds " in goal.lower() and any(n in pickupable for n in candidates)
        requires_toggle = "(istoggled " in goal.lower() and any(n in toggleable for n in candidates)
        if not (requires_pickup or requires_toggle):
            continue
        eligible = sorted(n for n in candidates if n in backed)
        missing = sorted(n for n in candidates if n in locations and n not in backed and (n in pickupable or n in toggleable))
        requirements.append({"goal_type": goal_type, "requires_pickup": requires_pickup, "requires_toggle": requires_toggle, "candidate_objects": candidates, "eligible_objects": eligible, "missing_in_receptacle_objects": missing, "satisfied": bool(eligible)})
    return {"goal_requirements": requirements, "runtime_integrity_ready": bool(requirements) and all(r["satisfied"] for r in requirements)}


def run(manifest_path: Path = MANIFEST, terminal_path: Path = TERMINAL) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    terminal = read_json(terminal_path)
    rows = []
    for item in manifest.get("rows_detail") or []:
        gamefile = ROOT / str(item["derived_gamefile"]).replace("\\", "/")
        game = read_json(gamefile)
        rows.append({"task_identity": item["task_identity"], "task_relative_path": item["task_relative_path"], "derived_gamefile": str(gamefile.relative_to(ROOT)).replace("\\", "/"), "derived_sha256": sha256(gamefile), **audit_problem(str(game["pddl_problem"]))})
    blocked = [r for r in rows if not r["runtime_integrity_ready"]]
    violation = terminal.get("hard_invariant_violation") or {}
    return {"schema_version": 2, "phase_id": "TG6-tracegraph-runtime-integrity-diagnostic-v2", "experiment_line": "tracegraph-observable-state-skill-composition", "status": "blocked_runtime_integrity" if blocked else "ready_for_textworld_zero_step_preflight", "task_count": len(rows), "ready_task_count": len(rows) - len(blocked), "blocked_task_count": len(blocked), "blocked_task_identities": [r["task_identity"] for r in blocked], "terminal_v2_result": str(terminal_path.relative_to(ROOT)).replace("\\", "/"), "terminal_v2_result_sha256": sha256(terminal_path), "terminal_v2_task_identity": violation.get("task_identity"), "terminal_task_detected_by_audit": violation.get("task_identity") in {r["task_identity"] for r in blocked}, "repair_v1_manifest_sha256": sha256(manifest_path), "rows": rows, "episodes_run": 0, "actions_taken": 0, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "api_calls": 0, "paid_api_calls": 0, "source_files_mutated": False, "repair_v1_artifacts_mutated": False, "terminal_v2_artifact_mutated": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--terminal-result", type=Path, default=TERMINAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite diagnostic output: {output}")
    result = run(args.manifest, args.terminal_result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TG6 runtime-integrity diagnostic: ready={result['ready_task_count']}/{result['task_count']}; blocked={result['blocked_task_count']}; terminal_match={result['terminal_task_detected_by_audit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
