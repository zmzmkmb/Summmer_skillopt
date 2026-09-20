import json

from scripts import analyze_acl2027_phase3d_specificity_abstention_live_v3 as analysis


def test_phase3d_v3_contract_parser_accepts_frozen_shape():
    planned = analysis.load(analysis.SCHEDULE)["schedule"][2]
    ids = planned["candidate_order"]
    raw = json.dumps({"skill_assessments": [{"skill_id": value, "applicable": True} for value in ids], "selected_skill_id": ids[0], "intermediate_operation": "compare", "final_answer": "answer"})
    parsed, error = analysis.parse_contract(raw, planned)
    assert error is None
    assert parsed["selected_skill_id"] == ids[0]


def test_phase3d_v3_contract_parser_rejects_wrong_candidate_order():
    planned = analysis.load(analysis.SCHEDULE)["schedule"][4]
    ids = list(reversed(planned["candidate_order"]))
    raw = json.dumps({"skill_assessments": [{"skill_id": value, "applicable": True} for value in ids], "selected_skill_id": planned["expected_specificity_selection"], "intermediate_operation": "compare", "final_answer": "answer"})
    parsed, error = analysis.parse_contract(raw, planned)
    assert parsed is None
    assert error == "assessment_identity"
