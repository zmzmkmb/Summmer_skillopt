from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_acl2027_tracegraph_tg6_pddl_integrity_v1 import inspect_task


def test_audit_flags_target_without_receptacle(tmp_path: Path):
    task = {
        "task_identity": "t1",
        "split": "valid_seen",
        "task_relative_path": "valid_seen/look_at_obj_in_light-BaseballBat-None-DeskLamp-303/trial_x",
    }
    game_dir = tmp_path / "json_2.1.1" / Path(task["task_relative_path"])
    game_dir.mkdir(parents=True)
    problem = """
(define (problem p)
 (:init
  (objectType bat BaseballBatType)
  (objectType lamp DeskLampType)
  (pickupable bat)
  (toggleable lamp)
  (objectAtLocation bat loc1)
  (inReceptacle lamp desk)
 )
 (:goal (and))
)
"""
    (game_dir / "game.tw-pddl").write_text(json.dumps({"pddl_problem": problem}), encoding="utf-8")
    result = inspect_task(tmp_path, task)
    assert "target_object_missing_in_receptacle" in result["issues"]
    assert result["target_pickupable"] == ["bat"]
    assert result["target_in_receptacle"] == []


def test_audit_accepts_container_backed_target(tmp_path: Path):
    task = {
        "task_identity": "t2",
        "split": "valid_seen",
        "task_relative_path": "valid_seen/look_at_obj_in_light-AlarmClock-None-DeskLamp-323/trial_x",
    }
    game_dir = tmp_path / "json_2.1.1" / Path(task["task_relative_path"])
    game_dir.mkdir(parents=True)
    problem = """
(define (problem p)
 (:init
  (objectType clock AlarmClockType)
  (objectType lamp DeskLampType)
  (pickupable clock)
  (toggleable lamp)
  (inReceptacle clock desk)
  (inReceptacle lamp desk)
 )
 (:goal (and))
)
"""
    (game_dir / "game.tw-pddl").write_text(json.dumps({"pddl_problem": problem}), encoding="utf-8")
    result = inspect_task(tmp_path, task)
    assert result["issues"] == []
