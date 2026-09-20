from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.repair_acl2027_tracegraph_tg6_pddl_v1 import derive_game, derive_problem
from scripts.run_acl2027_tracegraph_tg6_pddl_repair_preflight_v1 import validate_derived_pair


def _task(target: str = "BaseballBat") -> dict[str, str]:
    return {
        "task_identity": "t1",
        "split": "valid_seen",
        "task_relative_path": f"valid_seen/look_at_obj_in_light-{target}-None-DeskLamp-303/trial_x",
    }


def _problem(with_receptacle: bool = False) -> str:
    target_fact = "(inReceptacle bat desk)" if with_receptacle else "(objectAtLocation bat loc1)"
    return f"""(define (problem p)
(:domain alfred)
(:objects
 bat - object
 BaseballBatType - otype
 DeskLampType - otype
 desk - receptacle
 loc1 - location
)
(:init
 (objectType bat BaseballBatType)
 (objectType lamp DeskLampType)
 (pickupable bat)
 (toggleable lamp)
 {target_fact}
 (receptacleAtLocation desk loc1)
 (inReceptacle lamp desk)
)
(:goal (and))
)"""


def _write_game(path: Path, problem: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pddl_domain": "(define (domain alfred))",
                "grammar": "grammar",
                "pddl_problem": problem,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_derive_problem_adds_floor_receptacle_without_changing_domain():
    derived, metadata = derive_problem(_problem(), _task())
    assert metadata["changed"] is True
    assert "TraceGraphFloorReceptacle - receptacle" in derived
    assert "(receptacleAtLocation TraceGraphFloorReceptacle loc1)" in derived
    assert "(inReceptacle bat TraceGraphFloorReceptacle)" in derived
    assert "dummy(val1)" not in derived.lower()


def test_valid_source_is_left_byte_for_byte_unchanged(tmp_path: Path):
    task = _task()
    source = tmp_path / "source" / "game.tw-pddl"
    destination = tmp_path / "derived" / "game.tw-pddl"
    _write_game(source, _problem(with_receptacle=True))
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    row = derive_game(source, destination, task)
    assert row["changed"] is False
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert destination.read_bytes() == source.read_bytes()


def test_validate_derived_pair_accepts_repaired_fixture(tmp_path: Path):
    task = _task()
    source = tmp_path / "json_2.1.1" / Path(task["task_relative_path"]) / "game.tw-pddl"
    derived = tmp_path / "derived" / "game.tw-pddl"
    _write_game(source, _problem())
    derive_game(source, derived, task)
    result = validate_derived_pair(source, derived, task)
    assert result["changed"] is True
    assert result["synthetic_facts_present"] is True
