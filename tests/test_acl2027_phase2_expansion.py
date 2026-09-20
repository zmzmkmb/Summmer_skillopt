from __future__ import annotations
import hashlib, json
from pathlib import Path
from scripts.prepare_acl2027_phase2_expansion import CONFIG, ROOT, build, digest, selector

def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))

def test_selector_and_source_hashes_are_deterministic():
    c = config(); a = build(c); b = build(c)
    assert a["source_dataset_manifest"]["hash"] == b["source_dataset_manifest"]["hash"]
    assert selector("probe", "fact_retrieval", c["seed"], "x") == selector("probe", "fact_retrieval", c["seed"], "x")
    assert len(selector("probe", "fact_retrieval", c["seed"], "x")) == 64

def test_b_arithmetic_and_cost():
    c = config(); r = c["request_plan_contract"]
    assert r["calibration_calls"] + r["history_max_attempts"] + r["probe_calls"] + r["held_out_calls"] == 710
    assert round(sum(r["cost_components_cny"].values()), 6) == r["cost_estimate_cny"] == 6.197280
    assert r["zero_retry_worst_case_physical_attempts"] == 710

def test_blocked_plan_has_no_materialized_requests():
    a = build(config())
    assert a["status"] == "blocked_preflight"
    assert all(not rows for p in a["partitions"].values() for rows in p.values())
    assert a["network_calls"] == a["provider_calls"] == a["paid_api_calls"] == 0

def test_contract_and_stage_gates():
    c = config()
    assert c["model"]["retries"] == 0 and c["model"]["max_tokens_present"] is False
    assert c["coverage_gate"]["minimum_independent_verified_supports_per_family"] == 8
    assert c["coverage_gate"]["probe_and_held_out_allowed_only_if_passed"] is True
    assert "request_hash_drift" in c["request_plan_contract"]["hard_stops"]
    assert "non_prefix_resume" in c["request_plan_contract"]["hard_stops"]
    assert not any("1AA" in x or "1AB" in x for x in c["stages"].values())

def test_exclusion_and_type_mapping_audit():
    a = build(config()); e = a["phase1_exclusion_audit"]
    assert e["passed"] and e["phase1_2wiki_partition_ids_are_excluded"] and e["spent_searchqa_ids_are_excluded"]
    assert set(a["coverage_audit"]["type_to_skill_family"].values()) == {"attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference"}
