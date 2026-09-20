"""Audit local Phase 1F payload materialization without network or model calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def multiset_fingerprint(root: Path) -> str:
    """Fingerprint a materialized tree without rereading multi-GB corpora.

    Core manifests and task CSVs are content-hashed separately. For the large
    document tree, a deterministic path/size inventory is sufficient to detect
    incomplete or structurally changed materialization without a long full read.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit_spreadsheetbench() -> dict[str, Any]:
    split_root = DATA / "spreadsheetbench_id_split"
    data_root = DATA / "spreadsheetbench_verified_400"
    rows = load_json(data_root / "dataset.json")
    by_id = {str(row["id"]): row for row in rows}
    splits: dict[str, list[str]] = {}
    for split in ("train", "val", "test"):
        items = load_json(split_root / split / "items.json")
        splits[split] = [str(item["id"]) for item in items]

    all_ids = {item_id for ids in splits.values() for item_id in ids}
    missing_files: list[dict[str, Any]] = []
    resolved_files = 0
    for split, ids in splits.items():
        for item_id in ids:
            row = by_id.get(item_id)
            if row is None:
                continue
            task_dir = data_root / row["spreadsheet_path"]
            init_files = sorted(task_dir.glob("*_init.xlsx"))
            golden_files = sorted(task_dir.glob("*_golden.xlsx"))
            if not init_files and (task_dir / "initial.xlsx").is_file():
                init_files = [task_dir / "initial.xlsx"]
            if not golden_files and (task_dir / "golden.xlsx").is_file():
                golden_files = [task_dir / "golden.xlsx"]
            if not init_files or not golden_files or not (task_dir / "prompt.txt").is_file():
                missing_files.append(
                    {
                        "split": split,
                        "id": item_id,
                        "spreadsheet_path": row["spreadsheet_path"],
                        "has_init": bool(init_files),
                        "has_golden": bool(golden_files),
                        "has_prompt": (task_dir / "prompt.txt").is_file(),
                    }
                )
            else:
                resolved_files += 1

    split_manifest = split_root / "split_manifest.json"
    dataset = data_root / "dataset.json"
    return {
        "dataset_rows": len(rows),
        "dataset_unique_ids": len(by_id),
        "split_counts": {split: len(ids) for split, ids in splits.items()},
        "split_unique_ids": len(all_ids),
        "missing_dataset_ids": sorted(all_ids - set(by_id)),
        "dataset_ids_not_in_split": sorted(set(by_id) - all_ids),
        "resolved_task_materializations": resolved_files,
        "missing_or_invalid_task_materializations": missing_files,
        "split_manifest_sha256": sha256_file(split_manifest),
        "dataset_sha256": sha256_file(dataset),
        "materialized_file_count": sum(1 for path in data_root.rglob("*") if path.is_file()),
        "materialized_bytes": sum(path.stat().st_size for path in data_root.rglob("*") if path.is_file()),
        "materialized_multiset_sha256": multiset_fingerprint(data_root),
        "ready": not (all_ids - set(by_id)) and not (set(by_id) - all_ids) and not missing_files,
    }


def audit_officeqa() -> dict[str, Any]:
    split_root = DATA / "officeqa_id_split"
    data_root = DATA / "officeqa_verified"
    csv_path = data_root / "officeqa_full.csv"
    manifest = split_root / "split_manifest.json"
    rows: list[dict[str, str]] = []
    fields: list[str] = []
    if csv_path.is_file():
        import csv

        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
    csv_uids = {row.get("uid", "") for row in rows if row.get("uid")}
    split_uids: dict[str, list[str]] = {}
    for split in ("train", "val", "test"):
        items_path = split_root / split / "items.json"
        items = load_json(items_path)
        split_uids[split] = [str(item["uid"]) for item in items]
    all_split_uids = {uid for uids in split_uids.values() for uid in uids}
    duplicate_split_uids = sum(len(uids) - len(set(uids)) for uids in split_uids.values())
    parsed_jsons = list((data_root / "treasury_bulletins_parsed" / "jsons").glob("*.json"))
    return {
        "split_manifest_sha256": sha256_file(manifest),
        "csv_sha256": sha256_file(csv_path) if csv_path.is_file() else None,
        "csv_fields": fields,
        "csv_rows": len(rows),
        "csv_unique_uids": len(csv_uids),
        "split_counts": {split: len(uids) for split, uids in split_uids.items()},
        "split_unique_uids": len(all_split_uids),
        "csv_uids_missing_from_split": sorted(csv_uids - all_split_uids),
        "split_uids_missing_from_csv": sorted(all_split_uids - csv_uids),
        "duplicate_split_uids": duplicate_split_uids,
        "parsed_document_json_count": len(parsed_jsons),
        "materialized_file_count": sum(1 for path in data_root.rglob("*") if path.is_file()),
        "materialized_bytes": sum(path.stat().st_size for path in data_root.rglob("*") if path.is_file()),
        "materialized_multiset_sha256": multiset_fingerprint(data_root) if data_root.is_dir() else None,
        "ready": (
            len(rows) == 246
            and len(csv_uids) == 246
            and all_split_uids == csv_uids
            and duplicate_split_uids == 0
            and len(parsed_jsons) > 0
        ),
    }


def audit() -> dict[str, Any]:
    spreadsheetbench = audit_spreadsheetbench()
    officeqa = audit_officeqa()
    return {
        "analysis": "phase1f_payload_audit_only_no_network_no_model_calls",
        "spreadsheetbench": spreadsheetbench,
        "officeqa": officeqa,
        "ready_for_paired_pilot": spreadsheetbench["ready"] and officeqa["ready"],
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, ensure_ascii=True))
