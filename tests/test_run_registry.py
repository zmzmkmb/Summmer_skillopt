"""Tests for experiment run identity and JSONL registry output."""
from __future__ import annotations

import json
from pathlib import Path

from skillopt.evaluation.run_registry import attach_run_metadata, append_run_registry


def test_attach_and_append_baseline_run_metadata(tmp_path: Path):
    payload = {
        "method": "bm25",
        "target_model": "model-x",
        "commit": "abc123",
        "timestamp": "2026-08-06T00:00:00Z",
        "per_question": [{
            "sample_id": "q1",
            "hard": 1,
            "predicted": "A",
            "selected_indices": [0],
        }],
    }
    attach_run_metadata(payload, kind="baseline", seed=43, run_id="run-test")
    assert payload["seed"] == 43
    assert payload["run_id"] == "run-test"
    assert len(payload["result_fingerprint"]) == 64

    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    registry_path = tmp_path / "registry.jsonl"
    entry = append_run_registry(
        registry_path, result_path=result_path, payload=payload, kind="baseline"
    )
    stored = json.loads(registry_path.read_text(encoding="utf-8"))
    assert stored == entry
    assert stored["run_id"] == "run-test"
    assert stored["file_sha256"]
