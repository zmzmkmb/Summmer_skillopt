"""Tests for TraceGraph TG1 local ALFWorld training-source auditing."""
from __future__ import annotations

import json

import pytest

from scripts.audit_acl2027_tracegraph_tg1_alfworld_source_v1 import audit_training_source


def write_training_trajectory(root, name="pick_and_place"):
    directory = root / "json_2.1.1" / "train" / name / "episode_001"
    directory.mkdir(parents=True)
    (directory / "game.tw-pddl").write_text("game", encoding="utf-8")
    (directory / "traj_data.json").write_text(json.dumps({"task_type": name}), encoding="utf-8")


def test_audit_training_source_emits_provenance_without_skillbank(tmp_path):
    write_training_trajectory(tmp_path)
    audit = audit_training_source(tmp_path)
    assert audit["source_split"] == "train"
    assert audit["trajectory_count"] == 1
    assert audit["skillbank_records_created"] == 0
    assert audit["records"][0]["task_type"] == "pick_and_place"


def test_audit_rejects_missing_adjacent_trajectory(tmp_path):
    directory = tmp_path / "json_2.1.1" / "train" / "task"
    directory.mkdir(parents=True)
    (directory / "game.tw-pddl").write_text("game", encoding="utf-8")
    with pytest.raises(ValueError, match="missing traj_data.json"):
        audit_training_source(tmp_path)


def test_audit_requires_training_root(tmp_path):
    with pytest.raises(ValueError, match="missing ALFWorld training directory"):
        audit_training_source(tmp_path)