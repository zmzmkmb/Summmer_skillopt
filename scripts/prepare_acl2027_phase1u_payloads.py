#!/usr/bin/env python3
"""Acquire and audit ACL 2027 Phase 1U payloads without model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import string
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase1u_calibration_payload_readiness_v1.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_select(ids: Iterable[str], seed: str, count: int) -> list[str]:
    ranked = sorted(
        set(ids),
        key=lambda item: hashlib.sha256(f"{seed}:{item}".encode()).hexdigest(),
    )
    if len(ranked) < count:
        raise ValueError(f"need {count} IDs, found {len(ranked)}")
    return ranked[:count]


def safe_extract(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            target = (destination / info.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"unsafe archive member: {info.filename}")
        bundle.extractall(destination)


def download_file(url: str, destination: Path, expected_bytes: int) -> None:
    if destination.exists():
        if destination.stat().st_size == expected_bytes:
            return
        raise ValueError(f"existing partial or unexpected file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "SummerSkillOpt-ACL2027/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    if partial.stat().st_size != expected_bytes:
        raise ValueError(
            f"downloaded {partial.stat().st_size} bytes, expected {expected_bytes}"
        )
    partial.replace(destination)


def normalize_answer(value: str) -> str:
    value = value.lower()
    value = "".join(character for character in value if character not in string.punctuation)
    value = re.sub(r"\b(a|an|the)\b", " ", value)
    return " ".join(value.split())


def answer_exact(prediction: str, record: dict[str, Any], aliases: dict[str, set[str]]) -> bool:
    golds = {str(record["answer"])} | aliases.get(str(record.get("answer_id", "")), set())
    normalized = normalize_answer(prediction)
    return any(normalized == normalize_answer(gold) for gold in golds)


def supporting_exact(prediction: list[list[Any]], record: dict[str, Any]) -> bool:
    def normalized(rows: list[list[Any]]) -> set[tuple[str, int]]:
        return {(str(title).lower(), int(index)) for title, index in rows}

    return normalized(prediction) == normalized(record["supporting_facts"])


def load_aliases(path: Path) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        aliases[str(row["Q_id"])] = {
            str(value) for value in row.get("aliases", []) + row.get("demonyms", [])
        }
    return aliases


def audit_records(records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    required = set(config["required_gold_fields"])
    allowed_types = set(config["allowed_task_types"])
    ids: list[str] = []
    missing_fields = Counter()
    bad_support = 0
    bad_evidence_ids = 0
    bad_answer_ids = 0
    bad_types = 0
    for row in records:
        missing = required - set(row)
        missing_fields.update(missing)
        item_id = str(row.get("_id", ""))
        ids.append(item_id)
        if not str(row.get("answer_id", "")).strip():
            bad_answer_ids += 1
        evidences = row.get("evidences", [])
        evidence_ids = row.get("evidences_id", [])
        if evidence_ids and len(evidences) != len(evidence_ids):
            bad_evidence_ids += 1
        context = {str(title).lower(): sentences for title, sentences in row.get("context", [])}
        for title, index in row.get("supporting_facts", []):
            sentences = context.get(str(title).lower())
            if sentences is None or not isinstance(index, int) or not 0 <= index < len(sentences):
                bad_support += 1
        if row.get("type") not in allowed_types:
            bad_types += 1
    duplicates = len(ids) - len(set(ids))
    return {
        "records": len(records),
        "unique_ids": len(set(ids)),
        "duplicate_ids": duplicates,
        "missing_fields": dict(sorted(missing_fields.items())),
        "invalid_supporting_fact_references": bad_support,
        "evidence_id_length_mismatches": bad_evidence_ids,
        "blank_answer_ids": bad_answer_ids,
        "invalid_task_types": bad_types,
        "task_type_counts": dict(sorted(Counter(str(row.get("type")) for row in records).items())),
        "valid": not any((duplicates, missing_fields, bad_support, bad_evidence_ids, bad_answer_ids, bad_types)),
    }


def materialize_partitions(records: list[dict[str, Any]], config: dict[str, Any], root: Path) -> dict[str, Any]:
    by_id = {str(row["_id"]): row for row in records}
    remaining = set(by_id)
    result: dict[str, Any] = {}
    for name in config["partition_contract"]["order"]:
        contract = config["partition_contract"]["partitions"][name]
        selected = stable_select(remaining, contract["seed"], int(contract["count"]))
        remaining.difference_update(selected)
        payload = []
        for item_id in selected:
            row = by_id[item_id]
            payload.append(
                {
                    "id": item_id,
                    "question": row["question"],
                    "answer": row["answer"],
                    "answer_id": row["answer_id"],
                    "supporting_evidence": row["supporting_facts"],
                    "evidences": row["evidences"],
                    "evidences_id": row["evidences_id"],
                    "context": row["context"],
                    "source_split": "dev",
                    "dataset_task_type": row["type"],
                    "skill_family": config["task_type_contract"]["mapping"][row["type"]],
                }
            )
        path = root / "partitions" / f"{name}.json"
        write_json(path, payload)
        result[name] = {
            "count": len(payload),
            "seed": contract["seed"],
            "ids": selected,
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(path),
        }
    return result


def bind_searchqa(config: dict[str, Any]) -> dict[str, Any]:
    phase1t = read_json(ROOT / config["paths"]["phase1t_audit"])
    selected = set(phase1t["searchqa_design"]["calibration_ids"])
    val_ids = {str(row["id"]) for row in read_json(ROOT / config["paths"]["searchqa_val"])}
    payload_path = ROOT / config["paths"]["searchqa_calibration_payload"]
    if not payload_path.exists():
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("datasets is required to materialize SearchQA") from exc
        dataset = load_dataset(
            config["paths"]["searchqa_dataset"],
            split="validation",
            download_mode="reuse_dataset_if_exists",
        )
        rows = []
        for row in dataset:
            item_id = str(row.get("key", ""))
            if item_id in selected:
                rows.append({
                    "id": item_id,
                    "question": row["question"],
                    "context": row["context"],
                    "answers": row["answers"],
                    "source_split": "validation",
                })
        rows.sort(key=lambda row: row["id"])
        write_json(payload_path, rows)
    payload = read_json(payload_path)
    payload_ids = [str(row.get("id", "")) for row in payload]
    complete = all(
        isinstance(row.get("question"), str)
        and bool(row["question"].strip())
        and isinstance(row.get("context"), str)
        and bool(row["context"].strip())
        and isinstance(row.get("answers"), list)
        and bool(row["answers"])
        for row in payload
    )
    return {
        "calibration_ids": sorted(selected),
        "all_ids_in_val_manifest": selected.issubset(val_ids),
        "payload_path": str(payload_path.relative_to(ROOT)).replace("\\", "/"),
        "payload_sha256": sha256_file(payload_path),
        "payload_rows": len(payload),
        "payload_ids_exact": set(payload_ids) == selected and len(payload_ids) == len(set(payload_ids)),
        "payload_fields_complete": complete,
        "source_dataset": config["paths"]["searchqa_dataset"],
        "admission_policy": "admitted_anchor_gate_is_diagnostic",
    }


def run(config: dict[str, Any], *, acquire: bool) -> dict[str, Any]:
    data_root = ROOT / config["paths"]["data_root"]
    if acquire:
        for spec in config["source"]["mirror_files"].values():
            quoted = urllib.parse.quote(spec["remote_path"], safe="")
            url = config["source"]["transport_mirror_api"].format(quoted_path=quoted)
            download_file(url, data_root / spec["local_path"], int(spec["expected_bytes"]))
    source_files = config["source"]["mirror_files"]
    paths = {name: data_root / spec["local_path"] for name, spec in source_files.items()}
    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"missing {name}: {path}")
        expected = int(source_files[name]["expected_bytes"])
        if path.stat().st_size != expected:
            raise ValueError(f"unexpected byte size for {name}: {path.stat().st_size} != {expected}")
    records = read_json(paths["dev"])
    aliases = load_aliases(paths["id_aliases"])
    record_audit = audit_records(records, config)
    partitions = materialize_partitions(records, config, data_root)
    partition_sets = [set(value["ids"]) for value in partitions.values()]
    pairwise_disjoint = all(
        left.isdisjoint(right)
        for index, left in enumerate(partition_sets)
        for right in partition_sets[index + 1 :]
    )
    fixture = records[0]
    verifier_fixture = {
        "gold_answer_passes": answer_exact(str(fixture["answer"]), fixture, aliases),
        "gold_support_passes": supporting_exact(fixture["supporting_facts"], fixture),
        "wrong_answer_fails": not answer_exact("acl2027-definitely-wrong", fixture, aliases),
        "missing_support_fails": not supporting_exact([], fixture),
    }
    source_manifest = {
        name: {
            "remote_path": source_files[name]["remote_path"],
            "local_path": str(paths[name].relative_to(ROOT)).replace("\\", "/"),
            "bytes": paths[name].stat().st_size,
            "sha256": sha256_file(paths[name]),
        }
        for name in paths
    }
    write_json(data_root / "source_manifest.json", {
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisition_timestamp_excluded_from_scientific_fingerprint": True,
        "normative_repository": config["source"]["normative_repository"],
        "normative_release_url": config["source"]["normative_release_url"],
        "transport_mirror": config["source"]["transport_mirror"],
        "transport_limitation": config["source"]["transport_limitation"],
        "remote_split_inventory": config["source"]["remote_split_inventory"],
        "materialized_files": source_manifest,
    })
    searchqa = bind_searchqa(config)
    checks = {
        "provider_and_paid_execution_closed": not any(
            config["execution"][key]
            for key in ("provider_calls_allowed", "paid_api_allowed", "formal_scaling_allowed", "qwen3_8_max_allowed", "legacy_officeqa_spreadsheetbench_batch_allowed")
        ),
        "searchqa_admitted_and_bound": searchqa["all_ids_in_val_manifest"] and len(searchqa["calibration_ids"]) == 12 and searchqa["payload_rows"] == 12 and searchqa["payload_ids_exact"] and searchqa["payload_fields_complete"] and searchqa["admission_policy"] == "admitted_anchor_gate_is_diagnostic",
        "source_bytes_exact": all(source_manifest[name]["bytes"] == int(source_files[name]["expected_bytes"]) for name in paths),
        "gold_pool_schema_valid": record_audit["valid"],
        "gold_pool_capacity_sufficient": len(records) >= 276,
        "partitions_exact": {name: value["count"] for name, value in partitions.items()} == {"calibration": 12, "history": 120, "development_probe": 24, "held_out_downstream": 120},
        "partitions_pairwise_disjoint": pairwise_disjoint,
        "task_types_frozen": set(record_audit["task_type_counts"]) == set(config["allowed_task_types"]),
        "verifier_fixtures_pass": all(verifier_fixture.values()),
        "claim_limit_explicit": config["decision_gate"]["preflight_does_not_establish_method_claim"],
    }
    return {
        "analysis": "phase1u_payload_materialization_audit",
        "searchqa": searchqa,
        "source_files": source_manifest,
        "remote_split_inventory": config["source"]["remote_split_inventory"],
        "record_audit": record_audit,
        "partitions": partitions,
        "verifier_fixture": verifier_fixture,
        "checks": checks,
        "decision": "payloads_materialized_execution_closed" if all(checks.values()) else "payload_audit_failed_execution_closed",
        "network_scope": "dataset_acquisition_only",
        "provider_calls": 0,
        "paid_api_calls": 0,
    }


def write_artifact(config: dict[str, Any], result: dict[str, Any]) -> None:
    output = ROOT / config["paths"]["artifact_dir"]
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    output.mkdir(parents=True)
    audit_path = output / "payload_audit.json"
    write_json(audit_path, result)
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256_file(CONFIG_PATH),
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": all(result["checks"].values()),
        "dataset_network_calls_only": True,
        "provider_calls": 0,
        "paid_api_calls": 0,
        "runs": [{"run_id": "phase1u_payload_audit", "status": "completed", "result_path": str(audit_path.relative_to(ROOT)).replace("\\", "/"), "file_sha256": sha256_file(audit_path)}],
        "aggregate_fingerprint": sha256_file(audit_path),
    }
    write_json(output / "run_manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if args.acquire == args.audit_only:
        parser.error("choose exactly one of --acquire or --audit-only")
    config = read_json(CONFIG_PATH)
    result = run(config, acquire=args.acquire)
    write_artifact(config, result)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["decision"] == "payloads_materialized_execution_closed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
