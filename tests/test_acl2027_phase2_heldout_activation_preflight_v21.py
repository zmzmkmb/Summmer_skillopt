from pathlib import Path

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_heldout_activation_preflight_v21 import (
    ARTIFACT,
    CONFIG,
    CONDITIONS,
    HELD_OUT,
    V17_SCHEDULE,
    build_schedule,
    load,
    validate,
)

AUTH = Path("configs/acl2027/phase2_heldout_only_authorization_request_v21.json")


def test_v21_is_zero_network_and_exact_heldout_grid() -> None:
    result = validate()
    assert result["status"] == "ready-for-fresh-held-out-authorization"
    assert result["held_out_calls"] == result["task_count"] * 4 == 320
    assert result["condition_counts"] == {condition: 80 for condition in CONDITIONS}
    assert result["family_counts"] == {family: 64 for family in ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")}
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0
    assert result["authorization_opened"] is False
    assert result["held_out_authorized"] is False


def test_v21_conditions_have_distinct_model_visible_semantics_without_gold() -> None:
    rows, bundles, gold = build_schedule()
    assert len(gold) == 80
    assert not ({row["task_id"] for row in gold} & {row["task_id"] for row in load(V17_SCHEDULE)["schedule"]})
    for task in gold:
        grid = {row["condition"]: row for row in rows if row["task_id"] == task["task_id"]}
        assert set(grid) == set(CONDITIONS)
        assert len({row["prior_payload_sha256"] for row in grid.values()}) == 4
        for row in grid.values():
            body = row["canonical_request_body"]
            assert body["response_format"] == {"type": "json_object"}
            assert body["temperature"] == 0
            assert body["model_id"] == "qwen3.7-plus"
            assert "max_tokens" not in body
            assert '"answers"' not in str(body)
    assert len(bundles["global"]["examples"]) == 10
    assert all(len(bundle["examples"]) == 10 for bundle in bundles["typed"].values())


def test_v21_artifact_and_authorization_are_bound_but_closed() -> None:
    result = validate()
    manifest = load(ARTIFACT / "run_manifest.json")
    request = load(AUTH)
    assert manifest["aggregate_fingerprint"] == result["aggregate_fingerprint"]
    assert request["status"] == "awaiting_fresh_explicit_user_authorization"
    assert request["requested_calls"] == request["max_provider_attempts"] == 320
    assert request["temperature"] == request["retries"] == 0
    assert request["max_tokens_present"] is False
    assert request["stage_cost_ceiling_cny"] == 3.5
    assert request["cumulative_cost_ceiling_cny"] == 7.5
    assert all(value is False for value in request["execution"].values())
    assert request["bindings"]["preflight_aggregate_fingerprint"] == manifest["aggregate_fingerprint"]
    assert request["bindings"]["preflight_config_sha256"] == sha256_file(CONFIG)
    assert request["bindings"]["preflight_manifest_sha256"] == sha256_file(ARTIFACT / "run_manifest.json")
    assert request["bindings"]["preflight_schedule_sha256"] == sha256_file(ARTIFACT / "held_out_schedule.json")
    assert request["bindings"]["preflight_prior_bundles_sha256"] == sha256_file(ARTIFACT / "prior_bundles.json")
    assert request["user_authorization"]["explicit_user_authorization_required"] is True
    assert request["user_authorization"]["held_out_authorized"] is False
    assert request["user_authorization"]["later_stages_authorized"] is False
    assert request["user_authorization"]["formal_scaling_authorized"] is False
    assert CONFIG.exists() and HELD_OUT.exists()
