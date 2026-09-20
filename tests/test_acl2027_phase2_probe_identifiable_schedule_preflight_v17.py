from pathlib import Path

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_probe_identifiable_schedule_preflight_v17 import (
    ARTIFACT,
    HELD_OUT_GOLD,
    ORIGINAL_SCHEDULE,
    artifact_documents,
    build_schedule,
    load,
    rendered_sha256,
    validate,
)

AUTH_REQUEST = Path("configs/acl2027/phase2_probe_only_authorization_request_v17.json")


def test_v17_identifiable_replacement_schedule_is_ready_but_closed() -> None:
    result = validate()
    assert result["status"] == "ready-for-explicit-authorization"
    assert result["probe_calls"] == result["unique_request_hashes"] == 160
    assert result["task_count"] == 40
    assert result["condition_counts"] == {"cold": 40, "copied_global": 40, "global_only": 40, "contextual_typed_prior": 40}
    assert result["spent_v14_task_excluded"] is True
    assert result["all_logical_ids_new"] is True
    assert result["all_request_hashes_new"] is True
    assert result["global_examples"] == result["typed_examples_per_family"] == 10
    assert result["private_probe_gold_used_for_priors"] is False
    assert result["held_out_gold_used_for_priors"] is False
    assert result["authorization_opened"] is False
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0


def test_v17_conditions_have_distinct_model_visible_prior_semantics() -> None:
    rows, bundles, gold = build_schedule()
    for task in gold:
        task_rows = {r["condition"]: r for r in rows if r["task_id"] == task["task_id"]}
        assert set(task_rows) == {"cold", "copied_global", "global_only", "contextual_typed_prior"}
        assert len({r["prior_payload_sha256"] for r in task_rows.values()}) == 4
        assert task_rows["global_only"]["canonical_request_body"]["messages"][1]["content"] != task_rows["copied_global"]["canonical_request_body"]["messages"][1]["content"]
    assert len(bundles["global"]["examples"]) == 10
    for family in bundles["typed"]:
        assert len(bundles["typed"][family]["examples"]) == 10
    for row in rows:
        body = row["canonical_request_body"]
        assert body["response_format"] == {"type": "json_object"}
        assert body["enable_thinking"] is False
        assert "max_tokens" not in body
        assert 'Required shape: {"answer":"<short answer>"}' in body["messages"][0]["content"]


def test_v17_new_identities_partition_isolation_and_artifact_hashes() -> None:
    rows, bundles, gold = build_schedule()
    old_probe = [row for row in load(ORIGINAL_SCHEDULE)["schedule"] if row["partition"] == "probe"]
    assert not ({row["logical_call_id"] for row in rows} & {row["logical_call_id"] for row in old_probe})
    assert not ({row["request_hash"] for row in rows} & {row["request_hash"] for row in old_probe})
    support_tasks = {example["task_id"] for example in bundles["global"]["examples"]}
    for bundle in bundles["typed"].values():
        support_tasks.update(example["task_id"] for example in bundle["examples"])
    assert not (support_tasks & {task["task_id"] for task in gold})
    assert not (support_tasks & {task["task_id"] for task in load(HELD_OUT_GOLD)})
    assert [row["staged_execution_index"] for row in rows] == list(range(1, 161))
    assert all(row["payload_hash"] == row["canonical_request_body"]["payload_hash"] for row in rows)
    result = validate()
    documents = artifact_documents(rows, bundles, gold)
    assert rendered_sha256(documents["probe_schedule.json"]) == result["bindings"]["probe_schedule_artifact_sha256"]
    assert rendered_sha256(documents["prior_bundles.json"]) == result["bindings"]["prior_bundles_artifact_sha256"]
    assert stable({key: value for key, value in result.items() if key != "aggregate_fingerprint"}) == result["aggregate_fingerprint"]


def test_v17_authorization_request_is_closed_and_artifact_bound() -> None:
    request = load(AUTH_REQUEST)
    manifest = load(ARTIFACT / "run_manifest.json")
    assert request["status"] == "awaiting_fresh_explicit_user_authorization"
    assert request["requested_calls"] == request["max_provider_attempts"] == 160
    assert request["model_id"] == "qwen3.7-plus"
    assert request["temperature"] == request["retries"] == 0
    assert request["max_tokens_present"] is False
    assert request["stage_cost_ceiling_cny"] == request["cumulative_cost_ceiling_cny"] == 7.5
    assert all(value is False for value in request["execution"].values())
    assert request["bindings"]["preflight_aggregate_fingerprint"] == manifest["aggregate_fingerprint"]
    assert request["bindings"]["preflight_manifest_sha256"] == sha256_file(ARTIFACT / "run_manifest.json")
    assert request["bindings"]["preflight_schedule_sha256"] == sha256_file(ARTIFACT / "probe_schedule.json")
    assert request["bindings"]["preflight_prior_bundles_sha256"] == sha256_file(ARTIFACT / "prior_bundles.json")
    assert request["bindings"]["preflight_replacement_gold_sha256"] == sha256_file(ARTIFACT / "replacement_probe_gold.json")
    assert request["user_authorization"]["explicit_user_authorization_required"] is True
    assert request["user_authorization"]["held_out_authorized"] is False
    assert request["user_authorization"]["later_stages_authorized"] is False
    assert request["user_authorization"]["formal_scaling_authorized"] is False
