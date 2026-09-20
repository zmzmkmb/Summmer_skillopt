import json

from scripts import analyze_acl2027_phase3d_specificity_abstention_contract_diagnostic_v3_1 as diagnostic


def test_mapping_shape_is_normalized_only_for_non_gating_diagnostic():
    row = diagnostic.strict.load(diagnostic.strict.SCHEDULE)["schedule"][4]
    raw = json.dumps({"skill_assessments": {candidate_id: {"skill_id": candidate_id, "applicable": True} for candidate_id in row["candidate_order"]}, "selected_skill_id": row["expected_specificity_selection"], "intermediate_operation": "compare", "final_answer": "answer"})
    parsed, error = diagnostic.tolerant_parse(raw, row)
    assert error is None
    assert [item["skill_id"] for item in parsed["skill_assessments"]] == row["candidate_order"]
    strict_parsed, strict_error = diagnostic.strict.parse_contract(raw, row)
    assert strict_parsed is None
    assert strict_error == "assessment_length"
