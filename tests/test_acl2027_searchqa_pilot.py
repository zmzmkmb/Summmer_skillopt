"""Legacy-compatible tests for the ACL 2027 SearchQA pilot runner."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.run_acl2027_searchqa_pilot import (
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    BudgetExceeded,
    DeterministicMockProvider,
    ProviderUsageError,
    ResumeError,
    StrictAnswerError,
    TokenPlanProvider,
    _empty_ledger,
    assert_execution_allowed,
    build_call_plan,
    build_replicate_manifest,
    execute_mock_call,
    execute_preflight,
    load_searchqa_items,
    summary_fingerprint,
    strict_extract_answer,
    validate_config,
)


def _protocol():
    config = validate_config(DEFAULT_CONFIG)
    items = load_searchqa_items(config)
    manifest = build_replicate_manifest(config, items)
    plan = build_call_plan(config, manifest)
    return config, items, manifest, plan


def test_frozen_protocol_validates_and_has_expected_workload():
    config, items, manifest, plan = _protocol()

    assert len(items) == 1400
    assert len(config["methods"]) == 7
    assert len(manifest["replicates"]) == 3
    assert len(plan) == 2448
    assert sum(bool(call["fallback"]) for call in plan) == 48
    assert config["_validated"]["config_sha256"] == (
        "d92783337f3d8a13be55fe714e6b2b1ddf7f3b6fb5aada18f8aba9f14e82b895"
    )


def test_strict_answer_parser_accepts_exactly_one_nonempty_answer():
    assert strict_extract_answer("Reasoning\n<answer>  Ada Lovelace  </answer>") == "Ada Lovelace"


@pytest.mark.parametrize(
    "response",
    [
        "Ada Lovelace",
        "<answer></answer>",
        "<answer>one</answer><answer>two</answer>",
        "<answer>missing close",
        "missing open</answer>",
        "<answer>outer <answer>inner</answer></answer>",
    ],
)
def test_strict_answer_parser_rejects_invalid_formats(response):
    with pytest.raises(StrictAnswerError):
        strict_extract_answer(response)


def test_replicate_manifests_are_deterministic_disjoint_and_method_paired():
    config, items, manifest_a, plan_a = _protocol()
    manifest_b = build_replicate_manifest(config, items)
    plan_b = build_call_plan(config, manifest_b)

    assert manifest_a == manifest_b
    assert plan_a == plan_b

    all_selected: list[str] = []
    for replicate in manifest_a["replicates"]:
        assert len(replicate["probe_ids"]) == 8
        assert len(replicate["evaluation_ids"]) == 112
        all_selected.extend(replicate["probe_ids"])
        all_selected.extend(replicate["evaluation_ids"])
    assert len(all_selected) == 360
    assert len(set(all_selected)) == 360

    first_seed = manifest_a["replicates"][0]
    expected_eval_ids = first_seed["evaluation_ids"]
    for method in config["methods"]:
        actual = [
            call["item_id"]
            for call in plan_a
            if call["seed"] == first_seed["seed"]
            and call["method"] == method["name"]
            and call["stage"] == "evaluation"
        ]
        assert actual == expected_eval_ids


def test_live_mode_refuses_while_paid_permission_is_false():
    config = validate_config(DEFAULT_CONFIG)
    with pytest.raises(PermissionError, match="paid_api_allowed is false"):
        assert_execution_allowed("live", config)


def test_token_plan_provider_extracts_exact_usage_without_network():
    class Usage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 18

    class Message:
        content = "<answer>ok</answer>"

    class Choice:
        message = Message()

    class Response:
        usage = Usage()
        choices = [Choice()]

    class Completions:
        def create(self, **kwargs):
            assert kwargs["model"] == "qwen3.6-flash"
            assert kwargs["max_tokens"] == 32
            return Response()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    provider = TokenPlanProvider(
        api_key="test-only",
        base_url="https://example.invalid/v1",
        model="qwen3.6-flash",
        max_output_tokens=32,
        client=Client(),
    )
    result = provider.invoke([{"role": "user", "content": "test"}])
    assert result.status == "success"
    assert result.response == "<answer>ok</answer>"
    assert (result.input_tokens, result.output_tokens) == (11, 7)


def test_token_plan_provider_disables_hidden_sdk_retries(monkeypatch):
    captured = {}

    class Client:
        pass

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return Client()

    monkeypatch.setattr(
        "scripts.run_acl2027_searchqa_pilot.OpenAI",
        fake_openai,
    )
    provider = TokenPlanProvider(
        api_key="test-only",
        base_url="https://example.invalid/v1/",
        model="qwen3.6-flash",
        max_output_tokens=32,
    )

    assert isinstance(provider.client, Client)
    assert captured["base_url"] == "https://example.invalid/v1"
    assert captured["max_retries"] == 0


def test_provider_marks_missing_or_inconsistent_usage_unknown():
    class Usage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 99

    class Response:
        usage = Usage()
        choices = [type("Choice", (), {"message": type("Message", (), {"content": "x"})()})()]

    client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": type("Completions", (), {"create": lambda self, **kwargs: Response()})()})()},
    )()
    provider = TokenPlanProvider(
        api_key="test-only",
        base_url="https://example.invalid/v1",
        model="qwen3.6-flash",
        max_output_tokens=32,
        client=client,
    )
    result = provider.invoke([{"role": "user", "content": "test"}])
    assert result.status == "failed"
    assert result.usage_known is False
    assert "ProviderUsageError" in result.error


def test_mock_retry_and_fallback_are_visible_and_exact():
    config, items, _, plan = _protocol()
    items_by_id = {item["id"]: item for item in items}
    skill_text = Path(config["_validated"]["skill_path"]).read_text(encoding="utf-8")

    retry_call = next(
        call for call in plan if DeterministicMockProvider.should_retry(call["run_id"])
    )
    retry_ledger = _empty_ledger()
    retry_provider = DeterministicMockProvider()
    retry_record = execute_mock_call(
        config,
        retry_call,
        items_by_id[retry_call["item_id"]],
        skill_text,
        retry_ledger,
        retry_provider,
    )
    assert retry_record["provider_attempts"] == 2
    assert retry_record["failed_attempts"] == 1
    assert retry_record["retry_count"] == 1
    assert retry_record["attempts"][0]["status"] == "failed"
    assert retry_record["attempts"][0]["input_tokens"] > 0
    assert retry_ledger["provider_attempts"] == 2
    assert retry_ledger["provider_attempts"] == (
        retry_ledger["successful_attempts"] + retry_ledger["failed_attempts"]
    )
    assert retry_ledger["total_tokens"] == (
        retry_ledger["input_tokens"] + retry_ledger["output_tokens"]
    )

    fallback_call = next(call for call in plan if call["fallback"])
    fallback_ledger = _empty_ledger()
    fallback_record = execute_mock_call(
        config,
        fallback_call,
        items_by_id[fallback_call["item_id"]],
        skill_text,
        fallback_ledger,
        DeterministicMockProvider(),
    )
    assert fallback_record["fallback"] is True
    assert fallback_ledger["fallback_calls"] == 1


def test_budget_failure_occurs_before_mock_provider_invocation():
    config, items, _, plan = _protocol()
    constrained = copy.deepcopy(config)
    constrained["hard_caps"]["provider_attempts"] = 0
    item = {entry["id"]: entry for entry in items}[plan[0]["item_id"]]
    skill_text = Path(config["_validated"]["skill_path"]).read_text(encoding="utf-8")
    provider = DeterministicMockProvider()

    with pytest.raises(BudgetExceeded, match="before provider invocation"):
        execute_mock_call(
            constrained,
            plan[0],
            item,
            skill_text,
            _empty_ledger(),
            provider,
        )
    assert provider.invocations == 0


def test_resume_skips_exact_run_ids_and_bad_jsonl_fails_fast(tmp_path):
    output_dir = tmp_path / "resume"
    first = execute_preflight(output_dir=output_dir, stop_after_new_calls=5)
    second = execute_preflight(output_dir=output_dir, stop_after_new_calls=5)

    assert first["completed_logical_calls"] == 5
    assert second["completed_logical_calls"] == 10
    assert second["new_calls_this_invocation"] == 5
    assert second["provider_invocations_this_process"] >= 5

    with (output_dir / "calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")
    with pytest.raises(ResumeError, match="bad JSONL"):
        execute_preflight(output_dir=output_dir, stop_after_new_calls=1)


def test_resume_manifest_fingerprint_mismatch_fails_fast(tmp_path):
    output_dir = tmp_path / "mismatch"
    execute_preflight(output_dir=output_dir, stop_after_new_calls=1)
    manifest_path = output_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["config_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResumeError, match="config_fingerprint mismatch"):
        execute_preflight(output_dir=output_dir, stop_after_new_calls=1)


def test_direct_cli_entrypoint_can_import_project_package(tmp_path):
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_acl2027_searchqa_pilot.py"),
            "--out-dir",
            str(tmp_path / "cli"),
            "--stop-after-new-calls",
            "1",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["completed_logical_calls"] == 1
    assert summary["ledger"]["paid_calls"] == 0


def test_summary_fingerprint_excludes_invocation_local_resume_fields():
    first = {
        "status": "completed",
        "completed_logical_calls": 2448,
        "new_calls_this_invocation": 2448,
        "provider_invocations_this_process": 2576,
    }
    resumed = {
        **first,
        "new_calls_this_invocation": 0,
        "provider_invocations_this_process": 0,
    }
    assert summary_fingerprint(first) == summary_fingerprint(resumed)
