#!/usr/bin/env python3
"""Finalize and audit the zero-network TraceGraph TG6 repair-v2 preflight.

The repair tree is built by ``repair_acl2027_tracegraph_tg6_pddl_v2.py``.
This stage binds that new tree to the already completed zero-step TextWorld
reset evidence without rerunning episodes or modifying the pending source
evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v2"
FORMAL_MANIFEST = FORMAL_ROOT / "repair_manifest.json"
PENDING_MANIFEST = ROOT / "tracegraph_tg6_pddl_derived_repair_v2.pending/repair_manifest.json"
PENDING_ZERO_STEP = ROOT / "tracegraph_tg6_textworld_zero_step_preflight_v2.pending.json"
EVIDENCE = FORMAL_ROOT / "zero_step_evidence.json"
OUTPUT = FORMAL_ROOT / "preflight.json"
REPORT = FORMAL_ROOT / "preflight_report.md"
SCHEDULE = ROOT / "artifacts/acl2027_tracegraph_tg4_heldout_mechanism_preflight_v1/heldout_schedule.json"
PARENT_MANIFEST = ROOT / "artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/repair_manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def validate_source_zero_step(result: dict[str, Any]) -> None:
    if result.get("phase_id") != "TG6-tracegraph-textworld-zero-step-preflight-v2":
        raise ValueError("zero-step evidence phase mismatch")
    if result.get("status") != "passed":
        raise ValueError("zero-step TextWorld reset evidence is not passed")
    if result.get("task_count") != 40 or result.get("passed_task_count") != 40:
        raise ValueError("zero-step evidence does not cover 40/40 tasks")
    if result.get("failed_task_count") != 0:
        raise ValueError("zero-step evidence contains failed tasks")
    for key in ("episodes_run", "actions_taken", "network_calls", "provider_calls", "model_calls", "api_calls", "paid_api_calls"):
        if result.get(key) != 0:
            raise ValueError(f"zero-step evidence has non-zero {key}")
    rows = list(result.get("rows") or [])
    if len(rows) != 40 or len({row.get("task_identity") for row in rows}) != 40:
        raise ValueError("zero-step evidence task identities are incomplete or duplicated")
    if any(row.get("status") != "passed" for row in rows):
        raise ValueError("zero-step evidence contains a non-passed row")


def validate_formal_manifest(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if manifest.get("schema_version") != 2:
        raise ValueError("repair-v2 manifest schema mismatch")
    if manifest.get("phase_id") != "TG6-tracegraph-pddl-derived-repair-v2":
        raise ValueError("repair-v2 manifest phase mismatch")
    if manifest.get("experiment_line") != "tracegraph-observable-state-skill-composition":
        raise ValueError("repair-v2 research line mismatch")
    if manifest.get("task_count") != 40 or manifest.get("repaired_task_count") != 10:
        raise ValueError("repair-v2 manifest must cover 40 tasks and 10 repaired tasks")
    if manifest.get("parent_repair_manifest_sha256") != sha256(PARENT_MANIFEST):
        raise ValueError("repair-v2 parent manifest fingerprint mismatch")
    if manifest.get("schedule_sha256") != sha256(SCHEDULE):
        raise ValueError("repair-v2 schedule fingerprint mismatch")
    if manifest.get("source_files_mutated") is not False:
        raise ValueError("repair-v2 source mutation gate is not false")
    for key in ("episodes_run", "network_calls", "provider_calls", "model_calls", "paid_api_calls"):
        if manifest.get(key) != 0:
            raise ValueError(f"repair-v2 manifest has non-zero {key}")

    schedule = read_json(SCHEDULE)
    tasks = list(schedule.get("tasks") or [])
    rows = list(manifest.get("rows_detail") or [])
    if len(tasks) != 40 or len(rows) != 40:
        raise ValueError("repair-v2 schedule or manifest row count mismatch")
    if [task.get("task_identity") for task in tasks] != [row.get("task_identity") for row in rows]:
        raise ValueError("repair-v2 manifest order does not match frozen schedule")

    formal_root = FORMAL_ROOT / "derived"
    for row in rows:
        gamefile = ROOT / str(row.get("derived_gamefile", "")).replace("\\", "/")
        try:
            gamefile.resolve().relative_to(formal_root.resolve())
        except ValueError as exc:
            raise ValueError(f"derived gamefile escapes formal repair root: {row.get('task_identity')}") from exc
        if not gamefile.is_file() or sha256(gamefile) != row.get("derived_sha256"):
            raise ValueError(f"derived gamefile fingerprint mismatch: {row.get('task_identity')}")
        source = Path(str(row.get("source_gamefile", "")))
        if not source.is_file() or sha256(source) != row.get("source_sha256"):
            raise ValueError(f"source gamefile fingerprint mismatch: {row.get('task_identity')}")
        game = read_json(gamefile)
        if "dummy(val1)" in str(game.get("pddl_problem", "")).lower():
            raise ValueError(f"derived gamefile still contains dummy(val1): {row.get('task_identity')}")
    return rows, {str(row["task_identity"]): row for row in rows}


def finalize() -> dict[str, Any]:
    for path in (FORMAL_MANIFEST, PENDING_MANIFEST, PENDING_ZERO_STEP, SCHEDULE, PARENT_MANIFEST):
        if not path.is_file():
            raise FileNotFoundError(path)
    if OUTPUT.exists() or EVIDENCE.exists():
        raise FileExistsError("repair-v2 preflight output already exists")

    manifest = read_json(FORMAL_MANIFEST)
    rows, row_by_id = validate_formal_manifest(manifest)
    pending_manifest_hash = sha256(PENDING_MANIFEST)
    pending_manifest = read_json(PENDING_MANIFEST)
    if pending_manifest.get("task_count") != 40 or pending_manifest.get("repaired_task_count") != 10:
        raise ValueError("pending repair-v2 manifest does not describe the expected scope")

    source_zero_step = read_json(PENDING_ZERO_STEP)
    validate_source_zero_step(source_zero_step)
    if source_zero_step.get("manifest_sha256") != pending_manifest_hash:
        raise ValueError("zero-step evidence is not bound to the pending repair-v2 manifest")
    evidence_rows = {str(row["task_identity"]): row for row in source_zero_step["rows"]}
    if set(evidence_rows) != set(row_by_id):
        raise ValueError("zero-step evidence task identities do not match formal repair-v2")
    for task_id, row in row_by_id.items():
        if evidence_rows[task_id].get("derived_sha256") != row.get("derived_sha256"):
            raise ValueError(f"zero-step derived hash mismatch: {task_id}")

    evidence = {
        "schema_version": 1,
        "evidence_type": "promoted_exact_zero_step_textworld_result",
        "source_artifact": relative(PENDING_ZERO_STEP),
        "source_artifact_sha256": sha256(PENDING_ZERO_STEP),
        "source_manifest": relative(PENDING_MANIFEST),
        "source_manifest_sha256": pending_manifest_hash,
        "result": source_zero_step,
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest["status"] = "completed_zero_network_textworld_reset_preflight"
    manifest["zero_step_evidence"] = relative(EVIDENCE)
    manifest["zero_step_evidence_sha256"] = sha256(EVIDENCE)
    manifest["pending_source_manifest"] = relative(PENDING_MANIFEST)
    manifest["pending_source_manifest_sha256"] = pending_manifest_hash
    manifest["textworld_reset_status"] = "passed_40_of_40"
    manifest["aggregate_fingerprint"] = fingerprint(
        [
            {
                "task_identity": row["task_identity"],
                "derived_sha256": row["derived_sha256"],
                "changed": bool(row.get("changed")),
                "zero_step_status": evidence_rows[row["task_identity"]]["status"],
            }
            for row in rows
        ]
    )
    FORMAL_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    preflight = {
        "schema_version": 1,
        "phase_id": "TG6-tracegraph-pddl-derived-repair-v2-preflight",
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "status": "completed",
        "repair_manifest": relative(FORMAL_MANIFEST),
        "repair_manifest_sha256": sha256(FORMAL_MANIFEST),
        "zero_step_evidence": relative(EVIDENCE),
        "zero_step_evidence_sha256": sha256(EVIDENCE),
        "pending_source_manifest": relative(PENDING_MANIFEST),
        "pending_source_manifest_sha256": pending_manifest_hash,
        "task_count": 40,
        "repaired_task_count": 10,
        "zero_step_passed_task_count": 40,
        "zero_step_failed_task_count": 0,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "source_files_mutated": False,
        "frozen_schedule_mutated": False,
        "terminal_tg6_artifact_mutated": False,
        "phase0_to_phase6_reuse": False,
        "fresh_execution_authorization_required": True,
        "aggregate_fingerprint": manifest["aggregate_fingerprint"],
    }
    OUTPUT.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# TraceGraph TG6 Derived PDDL Repair v2 Preflight\n\n"
        "Status: `completed`.\n\n"
        "The formal repair-v2 tree covers 40 frozen held-out tasks and repairs "
        "10 goal-required interactive objects. Existing zero-step TextWorld "
        "reset evidence passed 40/40 tasks. This stage ran zero episodes, "
        "took zero actions, and made zero network/provider/model/API calls.\n\n"
        "Episode execution remains closed and requires a separately versioned "
        "execution preflight plus fresh exact user authorization.\n",
        encoding="utf-8",
    )
    return preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = read_json(OUTPUT)
        if result.get("status") != "completed":
            raise ValueError("repair-v2 preflight is not completed")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    result = finalize()
    print(
        json.dumps(
            {
                "output": relative(OUTPUT),
                "status": result["status"],
                "task_count": result["task_count"],
                "repaired_task_count": result["repaired_task_count"],
                "zero_step_passed_task_count": result["zero_step_passed_task_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
