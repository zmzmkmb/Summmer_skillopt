import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    return json.loads((ROOT / name).read_text())

def test_v2_partition_and_plan_are_complete_and_disjoint():
    audit = load("artifacts/acl2027_phase2_expansion_freeze_v2/partition_audit.json")
    plan = load("artifacts/acl2027_phase2_expansion_freeze_v2/request_plan.json")
    assert audit["status"] == plan["status"] == "ready_for_authorization"
    assert all(all(row.values()) for row in audit["partition_disjointness_matrix"].values())
    assert plan["materialized_logical_requests"] == 710
    assert len({x["logical_call_id"] for x in plan["plan"]}) == 710
    assert len({x["request_hash"] for x in plan["plan"]}) == 710
    assert plan["partition_counts"] == {"calibration": 60, "development_acquisition": 10, "formal_history": 160, "probe": 160, "held_out": 320}
    assert plan["cost_estimate_cny"] == 6.197280
    assert plan["conservative_ceiling_cny"] == 7.50

def test_v2_request_contract_and_hashes():
    plan = load("artifacts/acl2027_phase2_expansion_freeze_v2/request_plan.json")["plan"]
    for item in plan:
        body = item["canonical_request_body"]
        assert body["model_id"] == "qwen3.7-plus"
        assert body["temperature"] == 0
        assert "max_tokens" not in body
        assert item["expected_accounting"]["retries"] == 0
        canonical = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(canonical.encode()).hexdigest() == item["request_hash"]
