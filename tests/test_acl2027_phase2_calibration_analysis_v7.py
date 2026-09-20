from scripts.analyze_acl2027_phase2_calibration_v7 import build_diagnostic


def test_plain_text_diagnostic_cannot_override_strict_gate() -> None:
    result = build_diagnostic()
    assert result["status"] == "non_gating_diagnostic_only"
    assert result["scientific_gate_override_allowed"] is False
    assert result["strict_contract_valid"] == result["strict_answer_correct"] == 0
    assert result["plain_text_outputs"] == 60
    assert result["exact_plain_answer"] <= result["gold_answer_contained"] <= 60
    assert sum(item["rows"] for item in result["per_family"].values()) == 60
