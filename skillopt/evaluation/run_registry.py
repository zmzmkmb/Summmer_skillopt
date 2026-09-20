"""Attach auditable identity metadata to experiment outputs and append a JSONL registry."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from skillopt.evaluation.artifact_audit import (
    baseline_result_fingerprint,
    file_sha256,
    result_fingerprint,
)


def attach_run_metadata(
    payload: dict[str, Any],
    *,
    kind: str,
    seed: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Mutate and return a result payload with schema, run ID, seed, and fingerprint."""
    if kind not in {"formal", "baseline"}:
        raise ValueError(f"Unsupported run kind: {kind}")
    payload["artifact_schema_version"] = 2
    payload["run_id"] = run_id or f"{kind}-{uuid.uuid4().hex}"
    payload["seed"] = int(seed)
    fingerprint = (
        result_fingerprint(payload)
        if kind == "formal"
        else baseline_result_fingerprint(payload)
    )
    payload["result_fingerprint"] = fingerprint
    return payload


def append_run_registry(
    registry_path: str | Path,
    *,
    result_path: str | Path,
    payload: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    """Append one immutable JSONL registry entry after a result file is written."""
    registry_path = Path(registry_path)
    result_path = Path(result_path)
    entry = {
        "artifact_schema_version": int(payload.get("artifact_schema_version", 2)),
        "run_id": str(payload["run_id"]),
        "kind": kind,
        "seed": int(payload["seed"]),
        "model": str(payload.get("target_model", "")),
        "method": str(payload.get("method", "multi-method")),
        "commit": str(payload.get("commit", "")),
        "timestamp": str(payload.get("timestamp", "")),
        "result_path": str(result_path.resolve()),
        "file_sha256": file_sha256(result_path),
        "result_fingerprint": str(payload["result_fingerprint"]),
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry
