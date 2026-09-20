from scripts.audit_acl2027_tracegraph_tg6_runtime_integrity_v2 import audit_problem


def _problem(lamp_backed: bool) -> str:
    lamp_fact = "(inReceptacle lamp floor)" if lamp_backed else "(objectAtLocation lamp loc2)"
    return f"""(define (problem p)
(:domain alfred)
(:objects card lamp - object floor desk - receptacle loc1 loc2 - location)
(:init
 (objectType card CreditCardType)
 (objectType lamp FloorLampType)
 (pickupable card)
 (toggleable lamp)
 (inReceptacle card desk)
 {lamp_fact}
)
(:goal (and
 (exists (?o - object ?a - agent) (and (objectType ?o CreditCardType) (holds ?a ?o)))
 (exists (?ot - object) (and (objectType ?ot FloorLampType) (isToggled ?ot)))
))
)"""


def test_audit_detects_unbacked_toggle_target():
    result = audit_problem(_problem(False))
    assert result["runtime_integrity_ready"] is False
    lamp = next(r for r in result["goal_requirements"] if r["goal_type"] == "FloorLampType")
    assert lamp["requires_toggle"] is True
    assert lamp["missing_in_receptacle_objects"] == ["lamp"]


def test_audit_accepts_backed_targets():
    assert audit_problem(_problem(True))["runtime_integrity_ready"] is True
