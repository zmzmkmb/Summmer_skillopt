from pathlib import Path

from scripts.repair_acl2027_tracegraph_tg6_pddl_v2 import (
    ROOT,
    derive_problem,
    required_floor_objects,
    _resolve_rooted,
)


def _problem(two_lamps: bool = False) -> str:
    lamps = "lamp lamp2 - object" if two_lamps else "lamp - object"
    lamp_types = "(objectType lamp FloorLampType)" + ("\n (objectType lamp2 FloorLampType)" if two_lamps else "")
    lamp_locations = "(objectAtLocation lamp loc2)" + ("\n (objectAtLocation lamp2 loc3)" if two_lamps else "")
    return f"""(define (problem p)
(:domain alfred)
(:objects card - object
 {lamps}
 floor - receptacle
 loc1 loc2 loc3 - location)
(:init
 (objectType card CreditCardType)
 {lamp_types}
 (pickupable card)
 (toggleable lamp)
 {"(toggleable lamp2)" if two_lamps else ""}
 (inReceptacle card floor)
 {lamp_locations}
)
(:goal (and
 (exists (?o - object ?a - agent) (and (objectType ?o CreditCardType) (holds ?a ?o)))
 (exists (?ot - object) (and (objectType ?ot FloorLampType) (isToggled ?ot)))
))
)"""


def test_v2_repairs_toggle_target_too():
    source = _problem()
    assert required_floor_objects(source)[0]["object"] == "lamp"
    derived, metadata = derive_problem(source)
    assert metadata["changed"] is True
    assert "(inReceptacle lamp TraceGraphFloorReceptacle_" in derived


def test_v2_repairs_all_unbacked_goal_candidates():
    derived, metadata = derive_problem(_problem(two_lamps=True))
    assert len(metadata["repaired_objects"]) == 2
    assert derived.count("(inReceptacle lamp ") == 1
    assert derived.count("(inReceptacle lamp2 ") == 1


def test_relative_parent_manifest_is_resolved_from_repo_root():
    relative = Path("artifacts/acl2027_tracegraph_tg6_pddl_derived_repair_v1/repair_manifest.json")
    assert _resolve_rooted(relative) == (ROOT / relative).resolve()
