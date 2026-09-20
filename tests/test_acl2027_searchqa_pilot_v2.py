"""Phase 1B v2 contracts for the PAYG SearchQA pilot."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.run_acl2027_searchqa_pilot import (
    DEFAULT_CONFIG,
    BudgetExceeded,
    ConfigError,
    DashScopePaygProvider,
    DeterministicMockProvider,
    ProviderUsageError,
    _empty_ledger,
    _guard_history,
    build_call_plan,
    build_replicate_manifest,
    build_selectors,
    execute_preflight,
    execute_prepared_call,
    load_searchqa_items,
    prepare_call,
    validate_config,
)


def _protocol():
    config = validate_config(DEFAULT_CONFIG)
    items = load_searchqa_items(config)
    manifest = build_replicate_manifest(config, items)
    plan = build_call_plan(config, manifest)
    return config, items, manifest, plan


def test_v2_payg_contract_and_exact_call_order():
    config, _, manifest, plan = _protocol()

    assert config["model"]["model_id"] == "qwen3.5-flash"
    assert config["model"]["enable_thinking"] is False
    assert config["execution"]["billing_route"] == "pay_as_you_go"
    assert config["execution"]["token_plan_allowed"] is False
    assert config["hard_caps"]["cost_cny"] == "200.00"
    assert len(plan) == 2448
    assert sum(call["stage"] == "evaluation" for call in plan) == 2352
    assert sum(call["stage"] == "guard_probe" for call in plan) == 96
    assert sum(bool(call["fallback"]) for call in plan) == 48
    assert all(call["run_id"].startswith("phase1b-") for call in plan)

    for replicate in manifest["replicates"]:
        rows = [call for call in plan if call["seed"] == replicate["seed"]]
        assert len(rows) == 816
        assert all(call["stage"] == "guard_probe" for call in rows[:32])
        assert all(call["stage"] == "evaluation" for call in rows[32:])


def test_prompt_preparation_matches_real_searchqa_builders():
    from skillopt.envs.searchqa.rollout import _build_system, _build_user

    config, items, manifest, plan = _protocol()
    item_by_id = {item["id"]: item for item in items}
    skill_text = Path(config["_validated"]["skill_path"]).read_text(encoding="utf-8")
    selectors = build_selectors(config, skill_text)
    call = next(
        row
        for row in plan
        if row["stage"] == "evaluation" and row["method"] == "no_skill"
    )
    item = item_by_id[call["item_id"]]

    prepared = prepare_call(
        config, call, item, skill_text, selectors, {}, manifest
    )

    assert prepared["messages"] == [
        {"role": "system", "content": _build_system("")},
        {"role": "user", "content": _build_user(item["question"], item["context"])},
    ]
    assert prepared["effective_skill_policy"] == "none"
    assert prepared["active_skill_chars"] == 0


def test_tfidf_and_moar_are_frozen_deterministic_selectors():
    config = validate_config(DEFAULT_CONFIG)
    skill_text = Path(config["_validated"]["skill_path"]).read_text(encoding="utf-8")
    selectors = build_selectors(config, skill_text)
    query = "Who discovered penicillin?"

    assert selectors["tfidf"].retrieve(query) == selectors["tfidf"].retrieve(query)
    assert selectors["moar"].retrieve(query) == selectors["moar"].retrieve(query)
    assert selectors["tfidf"].rule_set_fingerprint == config["skill"]["rule_set_fingerprint"]
    assert selectors["moar"].rule_set_fingerprint == config["skill"]["rule_set_fingerprint"]
    assert selectors["moar"]._tracker.frozen is True


def test_payg_provider_sends_frozen_request_body():
    captured = {}

    class Usage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 18

    class Message:
        content = "<answer>ok</answer>"
        reasoning_content = ""

    class Response:
        id = "request-test"
        usage = Usage()
        choices = [type("Choice", (), {"message": Message()})()]

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return Response()

    client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": Completions()})()},
    )()
    provider = DashScopePaygProvider(
        api_key="test-only",
        base_url="https://example.invalid/v1",
        model="qwen3.5-flash",
        max_output_tokens=32,
        client=client,
    )

    result = provider.invoke([{"role": "user", "content": "test"}])

    assert result.status == "success"
    assert captured["model"] == "qwen3.5-flash"
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == 32
    assert captured["extra_body"] == {"enable_thinking": False}


def _synthetic_guard(
    method_name: str,
    candidate_scores: list[float],
    cold_scores: list[float],
):
    config = validate_config(DEFAULT_CONFIG)
    seed = config["dataset"]["replicate_seeds"][0]
    probe_ids = [f"probe-{index}" for index in range(8)]
    manifest = {"replicates": [{"seed": seed, "probe_ids": probe_ids}]}
    method = next(row for row in config["methods"] if row["name"] == method_name)
    cold_branch = next(branch for branch in method["guard_probe_branches"] if "cold" in branch)
    completed = {}
    for index, item_id in enumerate(probe_ids):
        for branch, score in (
            ("candidate", candidate_scores[index]),
            (cold_branch, cold_scores[index]),
        ):
            run_id = f"{method_name}-{branch}-{item_id}"
            completed[run_id] = {
                "run_id": run_id,
                "seed": seed,
                "method": method_name,
                "stage": "guard_probe",
                "branch": branch,
                "item_id": item_id,
                "f1": score,
            }
    return _guard_history(
        config,
        seed=seed,
        method_name=method_name,
        completed=completed,
        manifest=manifest,
    )


def test_selective_guard_acceptable_harmful_and_ambiguous_paths():
    method = "global_only_selective_full_confirmation"
    acceptable = _synthetic_guard(method, [0.5] * 8, [0.5] * 8)
    harmful = _synthetic_guard(method, [0.0] * 8, [1.0] * 8)
    ambiguous = _synthetic_guard(method, [0.6, 0.2] * 4, [0.4] * 8)

    assert acceptable["decision"] == "acceptable"
    assert acceptable["first_decisive_round"] == 8
    assert acceptable["effective_skill_policy"] == "tfidf"
    assert harmful["decision"] == "harmful"
    assert harmful["action"] == "reject-fallback-cold"
    assert harmful["effective_skill_policy"] == "none"
    assert ambiguous["decision"] == "ambiguous"
    assert ambiguous["action"] == "abstain-fallback-cold"
    assert ambiguous["effective_skill_policy"] == "none"
    assert acceptable["candidate_state_mutated"] is False
    assert harmful["candidate_state_mutated"] is False
    assert ambiguous["candidate_state_mutated"] is False


def test_reset_comparator_uses_frozen_mean_tolerance():
    method = "global_only_reset_comparator"
    reset = _synthetic_guard(method, [0.4] * 8, [0.5] * 8)
    retain = _synthetic_guard(method, [0.45] * 8, [0.5] * 8)

    assert reset["triggered"] is True
    assert reset["effective_skill_policy"] == "none"
    assert reset["candidate_state_mutated"] is True
    assert retain["triggered"] is False
    assert retain["effective_skill_policy"] == "tfidf"


def test_cny_reservation_refuses_before_provider_invocation(tmp_path):
    config, items, manifest, plan = _protocol()
    constrained = copy.deepcopy(config)
    constrained["hard_caps"]["cost_cny"] = "0.001"
    item = {entry["id"]: entry for entry in items}[plan[0]["item_id"]]
    skill_text = Path(config["_validated"]["skill_path"]).read_text(encoding="utf-8")
    prepared = prepare_call(
        config,
        plan[0],
        item,
        skill_text,
        build_selectors(config, skill_text),
        {},
        manifest,
    )
    provider = DeterministicMockProvider()

    with pytest.raises(BudgetExceeded, match="cost_pico_cny.*before provider invocation"):
        execute_prepared_call(
            constrained,
            plan[0],
            item,
            prepared,
            _empty_ledger(),
            provider,
            tmp_path,
            [],
            mode="dry-run",
        )
    assert provider.invocations == 0


def test_orphan_success_resume_does_not_repeat_provider_call(tmp_path):
    output_dir = tmp_path / "orphan-success"
    first = execute_preflight(output_dir=output_dir, stop_after_new_calls=1)
    assert first["provider_invocations_this_process"] == 1

    (output_dir / "calls.jsonl").write_text("", encoding="utf-8")
    resumed = execute_preflight(output_dir=output_dir, stop_after_new_calls=1)

    assert resumed["completed_logical_calls"] == 1
    assert resumed["provider_invocations_this_process"] == 0
    assert resumed["ledger"]["provider_attempts"] == 1


def test_unknown_usage_journal_permanently_refuses_resume(tmp_path):
    output_dir = tmp_path / "unknown-usage"
    execute_preflight(output_dir=output_dir, stop_after_new_calls=1)
    attempts_path = output_dir / "attempts.jsonl"
    attempt = json.loads(attempts_path.read_text(encoding="utf-8").strip())
    attempt["usage_known"] = False
    attempts_path.write_text(json.dumps(attempt) + "\n", encoding="utf-8")
    (output_dir / "calls.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ProviderUsageError, match="unknown usage"):
        execute_preflight(output_dir=output_dir, stop_after_new_calls=1)


def test_source_fingerprint_mismatch_fails_before_execution(tmp_path):
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["source_fingerprints"]["pilot_runner"]["sha256"] = "0" * 64
    config_path = tmp_path / "bad-source.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ConfigError, match="immutable hash mismatch"):
        validate_config(config_path)


def test_manifest_fingerprints_attempt_journal(tmp_path):
    output_dir = tmp_path / "manifest"
    execute_preflight(output_dir=output_dir, stop_after_new_calls=1)
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))

    assert manifest["attempts_path"].endswith("attempts.jsonl")
    assert len(manifest["attempts_file_sha256"]) == 64
