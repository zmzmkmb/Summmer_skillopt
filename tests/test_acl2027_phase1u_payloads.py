from __future__ import annotations

import json
import zipfile
from copy import deepcopy

import pytest

from scripts.prepare_acl2027_phase1u_payloads import (
    CONFIG_PATH,
    answer_exact,
    audit_records,
    normalize_answer,
    read_json,
    safe_extract,
    stable_select,
    supporting_exact,
)


def test_phase1u_execution_keeps_all_model_routes_closed() -> None:
    config = read_json(CONFIG_PATH)
    execution = config["execution"]
    assert execution["dataset_network_allowed"]
    assert not execution["provider_calls_allowed"]
    assert not execution["paid_api_allowed"]
    assert not execution["formal_scaling_allowed"]
    assert not execution["qwen3_8_max_allowed"]


def test_stable_select_is_deterministic_and_unique() -> None:
    ids = ["c", "a", "b", "a"]
    first = stable_select(ids, "seed", 3)
    assert first == stable_select(reversed(ids), "seed", 3)
    assert len(first) == len(set(first)) == 3


def test_safe_extract_rejects_path_traversal(tmp_path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="unsafe archive member"):
        safe_extract(archive, tmp_path / "out")


def test_answer_and_support_verifiers_are_strict() -> None:
    record = {
        "answer": "The Example",
        "answer_id": "Q1",
        "supporting_facts": [["Title", 1]],
    }
    aliases = {"Q1": {"An Alias"}}
    assert normalize_answer("the Example!") == "example"
    assert answer_exact("example", record, aliases)
    assert answer_exact("alias", record, aliases)
    assert not answer_exact("different", record, aliases)
    assert supporting_exact([["title", 1]], record)
    assert not supporting_exact([["title", 0]], record)


def test_record_audit_rejects_duplicate_and_bad_support() -> None:
    config = read_json(CONFIG_PATH)
    base = {
        "_id": "same",
        "question": "q",
        "answer": "a",
        "supporting_facts": [["T", 1]],
        "context": [["T", ["only"]]],
        "evidences": [["s", "r", "o"]],
        "type": "comparison",
        "answer_id": "Q1",
        "evidences_id": [["Q2", "r", "Q3"]],
    }
    result = audit_records([base, deepcopy(base)], config)
    assert result["duplicate_ids"] == 1
    assert result["invalid_supporting_fact_references"] == 2
    assert not result["valid"]


def test_config_matches_phase1t_frozen_partition_contract() -> None:
    config = read_json(CONFIG_PATH)
    phase1t = read_json(config_path("configs/acl2027/phase1t_heldout_deployment_identifiability_v1.json"))
    frozen = phase1t["substrates"]["2WikiMultiHopQA"]["partition_selector"]
    current = config["partition_contract"]["partitions"]
    assert current["calibration"] == {"count": frozen["calibration_count"], "seed": frozen["seeds"]["calibration"]}
    assert current["history"] == {"count": frozen["history_count"], "seed": frozen["seeds"]["history"]}
    assert current["development_probe"] == {"count": frozen["development_probe_count"], "seed": frozen["seeds"]["development_probe"]}
    assert current["held_out_downstream"] == {"count": frozen["held_out_downstream_count"], "seed": frozen["seeds"]["held_out_downstream"]}


def test_searchqa_contract_requires_full_payload() -> None:
    config = read_json(CONFIG_PATH)
    assert config["paths"]["searchqa_dataset"] == "lucadiliello/searchqa"
    assert config["paths"]["searchqa_calibration_payload"].endswith("calibration.json")
    assert "question, context, and answer payloads" in config["decision_gate"]["pass"]


def test_task_type_mapping_is_metadata_bound_and_semantic() -> None:
    config = read_json(CONFIG_PATH)
    contract = config["task_type_contract"]
    assert contract["source"] == "dataset type metadata frozen before model responses"
    assert contract["mapping"] == {
        "comparison": "attribute_comparison",
        "inference": "relation_inference",
        "compositional": "entity_bridge",
        "bridge_comparison": "bridge_attribute_comparison",
    }


def config_path(relative: str):
    return CONFIG_PATH.parents[2] / relative
