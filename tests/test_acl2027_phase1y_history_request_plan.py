import json
from pathlib import Path

from scripts.materialize_acl2027_phase1y_history_requests import build, read

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase1y_history_request_plan_v1.json"


def test_final_plan_is_exactly_ten_and_leakage_free():
    result = build(read(CONFIG))
    assert result["request_count"] == 10
    assert result["counts_by_family"] == {"SearchQA": 2, "2WikiMultiHopQA": 8}
    assert len({row["request_hash"] for row in result["plan"]}) == 10
    assert all(row["retries"] == 0 and row["max_tokens_present"] is False for row in result["plan"])
    assert all(row["provenance"]["partition"] == "history" for row in result["plan"])
    assert all(row["payload_sha256"] for row in result["plan"])


def test_plan_is_deterministic_and_contract_is_frozen():
    left = build(read(CONFIG))
    right = build(read(CONFIG))
    assert left == right
    assert len(left["hard_stops"]) == 7
    assert "exact append-only prefix" in left["resume"]
    assert left["cost_ceiling_cny"] > 0
    assert left["cost_ceiling_cny"] < 1
    search = [r for r in left["plan"] if r["task_family"] == "SearchQA"]
    assert all(r["task_type"] == "single_hop_qa" for r in search)
    assert all(all(ord(ch) < 128 for m in r["request"]["messages"] for ch in m["content"]) for r in search)
