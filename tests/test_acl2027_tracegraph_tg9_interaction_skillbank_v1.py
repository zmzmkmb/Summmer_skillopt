from __future__ import annotations

import json
from pathlib import Path

from scripts.build_acl2027_tracegraph_tg9_interaction_skillbank_v1 import (
    ALLOWED_ACTIONS,
    FORBIDDEN_FIELDS,
    build_records,
    canonical_object_type,
    publish,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts/acl2027_tracegraph_tg1_skillbank_preflight_v1/skillbank_source_manifest.json"


def test_object_type_is_derived_without_runtime_geometry():
    assert canonical_object_type("Drawer|-00.56|+00.45|+00.49") == "drawer"


def test_train_manifest_builds_both_interaction_families():
    records = build_records(MANIFEST)
    assert {row["canonical_actions"][0]["action"] for row in records} == ALLOWED_ACTIONS
    assert all(row["source_split"] == "train" for row in records)
    assert all(not FORBIDDEN_FIELDS.intersection(row) for row in records)
    assert all(len(row["canonical_actions"][0]["args"]) == 1 for row in records)


def test_publish_is_immutable(tmp_path):
    output = tmp_path / "interaction.jsonl"
    records = build_records(MANIFEST)[:3]
    publish(records, output)
    loaded = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert loaded == records
    try:
        publish(records, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("publish must refuse overwrite")
