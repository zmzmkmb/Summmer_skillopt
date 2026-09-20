#!/usr/bin/env python3
"""Build the train-only TG9 OpenObject/CloseObject skill extension."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROTOCOL = "tracegraph-tg9-interaction-skillbank-v1"
ALLOWED_ACTIONS = {"OpenObject", "CloseObject"}
FORBIDDEN_FIELDS = {
    "api_action",
    "bbox",
    "images",
    "mask",
    "pddl_params",
    "planner_action",
    "point",
    "raw_traj_data",
    "scene",
    "turk_annotations",
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def canonical_object_type(object_id: str) -> str:
    head = str(object_id or "").split("|", 1)[0]
    value = re.sub(r"[^a-z0-9]+", "", head.lower())
    if not value:
        raise ValueError("interaction action is missing a canonical object type")
    return value


def interaction_action(row: dict[str, Any]) -> dict[str, Any] | None:
    api = row.get("api_action") or {}
    action = str(api.get("action", ""))
    if action not in ALLOWED_ACTIONS:
        return None
    return {
        "action": action,
        "args": [canonical_object_type(str(api.get("objectId", "")))],
    }


def build_records(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_split") != "train":
        raise ValueError("source manifest is not train-only")
    source_root = Path(str(manifest.get("source_root", "")))
    if not source_root.is_dir():
        raise FileNotFoundError(f"missing train source root: {source_root}")

    records: dict[str, dict[str, Any]] = {}
    for source in manifest.get("records", []):
        if source.get("source_split") != "train":
            raise ValueError("source manifest contains a non-train record")
        relative = str(source["gamefile_relative_path"])
        if "valid_seen" in relative or "valid_unseen" in relative:
            raise ValueError("validation split contamination")
        trajectory = source_root / relative.replace("game.tw-pddl", "traj_data.json")
        if sha256(trajectory) != source["traj_data_sha256"]:
            raise ValueError(f"trajectory hash mismatch: {relative}")
        payload = json.loads(trajectory.read_text(encoding="utf-8"))
        for index, low_action in enumerate(payload.get("plan", {}).get("low_actions", [])):
            action = interaction_action(low_action)
            if action is None:
                continue
            record = {
                "canonical_actions": [action],
                "construction_protocol_fingerprint": PROTOCOL,
                "gamefile_sha256": source["gamefile_sha256"],
                "low_action_index": index,
                "source_split": "train",
                "task_type": source["task_type"],
                "traj_data_sha256": source["traj_data_sha256"],
                "trajectory_id": source["trajectory_id"],
            }
            raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            record["skill_id"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if FORBIDDEN_FIELDS.intersection(record):
                raise ValueError("forbidden source field emitted")
            previous = records.get(record["skill_id"])
            if previous is not None and previous != record:
                raise ValueError("conflicting duplicate skill id")
            records[record["skill_id"]] = record
    result = sorted(records.values(), key=lambda row: row["skill_id"])
    if not result:
        raise ValueError("no OpenObject/CloseObject training evidence found")
    if {row["canonical_actions"][0]["action"] for row in result} != ALLOWED_ACTIONS:
        raise ValueError("interaction skill extension lacks an action family")
    return result


def publish(records: list[dict[str, Any]], output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = build_records(args.manifest)
    publish(records, args.output)
    counts = {
        action: sum(row["canonical_actions"][0]["action"] == action for row in records)
        for action in sorted(ALLOWED_ACTIONS)
    }
    print(json.dumps({"records": len(records), "action_counts": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
