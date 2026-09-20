import json
from scripts import analyze_acl2027_phase4c_repaired_heldout_live_v2 as analysis

def test_analysis_is_read_only_and_coverage_incomplete():
    analysis.main()
    result = json.loads(analysis.OUT.read_text(encoding="utf-8"))
    assert result["status"] == "coverage_incomplete"
    assert result["completed_rows"] == 395
    assert result["missing_rows"] == 5
    assert result["new_calls_made"] == 0
