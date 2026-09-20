import json
from pathlib import Path

from scripts.prepare_acl2027_phase1y_verified_history import (
    CONFIG,
    build_audit,
    build_request_plan,
    load_partitions,
    read_json,
)


def test_phase1y_config_is_zero_network_and_bound():
    config = read_json(CONFIG)
    assert config["execution"]["provider_calls_allowed"] is False
    assert config["execution"]["network_calls_allowed"] is False
    assert config["future_request_contract"]["retries"] == 0
    assert config["future_request_contract"]["max_tokens_present"] is False


def test_partition_bindings_and_isolation():
    config = read_json(CONFIG)
    audit = build_audit(config)
    assert audit["checks"]["partition_isolation"]
    assert audit["checks"]["spent_searchqa_ids_are_excluded"]
    assert audit["partition_inventory"]["2WikiMultiHopQA:history"]["count"] == 120
    assert audit["partition_inventory"]["SearchQA:history"]["count"] == 120
    assert audit["partition_inventory"]["SearchQA:probe"]["count"] == 24
    assert audit["partition_inventory"]["SearchQA:held_out"]["count"] == 120


def test_gold_records_are_rejected_and_candidates_empty():
    audit = build_audit(read_json(CONFIG))
    assert audit["verified_trajectories"] == 0
    assert audit["typed_candidates"] == 0
    assert audit["checks"]["gold_not_trajectory"]
    assert audit["checks"]["family_type_coverage_audited"]
    assert audit["checks"]["candidate_contract_coverage_met"] is False
    assert audit["decision"] == "negative_materialization_no_verified_history_phase1z_blocked"


def test_ids_and_request_plan_are_deterministic():
    config = read_json(CONFIG)
    first = build_audit(config)
    second = build_audit(config)
    assert first["future_request_plan"]["plan_sha256"] == second["future_request_plan"]["plan_sha256"]
    assert first["future_request_plan"]["plan"] == second["future_request_plan"]["plan"]
    records = first["candidate_records"]
    assert len({row["candidate_id"] for row in records}) == len(records)
    assert len({row["trajectory_id"] for row in records}) == len(records)


def test_minimum_call_derivation_is_not_legacy_estimate():
    audit = build_audit(read_json(CONFIG))
    plan = audit["future_request_plan"]
    assert plan["minimum_cross_family_history_successes"] == 10
    assert plan["freezeable_2wiki_attempts"] == 8
    assert plan["unfreezeable_searchqa_attempts"] == 2
    assert plan["exact_authorizable_history_attempts_now"] == 0
    assert plan["phase1z_exact_minimum_calls"] is None
    assert plan["phase1z_legacy_unoptimized_upper_bound_calls"] == 1152
    assert plan["phase1z_executable_now"] is False


def test_phase1x_replay_is_visible_but_calibration_excluded():
    audit = build_audit(read_json(CONFIG))
    replay = audit["source_discovery"]["phase1x_source_replay"]
    assert len(replay) == 24
    assert all(not row["admitted"] for row in replay)
    assert all("calibration_id_excluded" in row["rejection_reasons"] for row in replay)
    assert all(row["replay"]["status"] == "replayed" for row in replay)
    assert all(row["replay"]["matches_recorded"] is True for row in replay)
