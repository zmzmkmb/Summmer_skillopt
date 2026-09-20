import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_searchqa_readiness_is_local_and_ready():
    audit = json.loads((ROOT / "artifacts/acl2027_phase2_searchqa_payload_readiness_v2/payload_readiness_audit.json").read_text())
    assert audit["recovery"] == "local"
    assert audit["status"] == "ready"
    assert audit["eligible_after_phase1_exclusion"] >= 70
    assert audit["id_mapping"]["passed"] is True
    assert audit["phase1_exclusion_audit"]["passed"] is True
    assert audit["network_calls"] == audit["provider_calls"] == audit["paid_api_calls"] == 0
