#!/usr/bin/env python3
"""Audit a local ALFWorld training root for TraceGraph TG1 provenance only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_train_root(source_root: Path) -> Path:
    root = source_root.expanduser().resolve()
    train_root = root / "json_2.1.1" / "train"
    if not train_root.is_dir():
        raise ValueError(f"missing ALFWorld training directory: {train_root}")
    return train_root


def audit_training_source(source_root: Path) -> dict[str, Any]:
    train_root = resolve_train_root(source_root)
    records: list[dict[str, str]] = []
    for gamefile in sorted(train_root.rglob("game.tw-pddl")):
        relative = gamefile.relative_to(train_root).as_posix()
        if any(marker in relative for marker in ("valid_seen", "valid_unseen")):
            raise ValueError(f"evaluation split leaked into train source: {relative}")
        trajectory = gamefile.with_name("traj_data.json")
        if not trajectory.is_file():
            raise ValueError(f"missing traj_data.json beside training gamefile: {gamefile}")
        try:
            payload = json.loads(trajectory.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid trajectory JSON: {trajectory}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"trajectory JSON must be an object: {trajectory}")
        task_type = str(payload.get("task_type") or "").strip()
        if not task_type:
            raise ValueError(f"training trajectory has no task_type: {trajectory}")
        game_sha = sha256_file(gamefile)
        traj_sha = sha256_file(trajectory)
        trajectory_id = hashlib.sha256(f"{relative}:{game_sha}:{traj_sha}".encode("utf-8")).hexdigest()
        records.append({
            "trajectory_id": trajectory_id,
            "source_split": "train",
            "gamefile_relative_path": relative,
            "gamefile_sha256": game_sha,
            "traj_data_sha256": traj_sha,
            "task_type": task_type,
        })
    if not records:
        raise ValueError(f"no training game.tw-pddl files found under: {train_root}")
    canonical = json.dumps(records, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        "experiment_line": "tracegraph-observable-state-skill-composition",
        "phase_id": "TG1-tracegraph-alfworld-skillbank-preflight-v1",
        "source_root": str(train_root),
        "source_split": "train",
        "trajectory_count": len(records),
        "records": records,
        "aggregate_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "skillbank_records_created": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=os.environ.get("ALFWORLD_DATA", ""))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not str(args.source_root):
        parser.error("--source-root or ALFWORLD_DATA is required")
    audit = audit_training_source(args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VALID: audited {audit['trajectory_count']} ALFWorld training trajectories; no SkillBank records created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())