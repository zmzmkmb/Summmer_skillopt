"""Phase 1B v5 formatting-robustness contracts."""
from __future__ import annotations

import json

import pytest

import scripts.run_acl2027_searchqa_token_plan_pilot_v5 as v5


def test_v5_contract_and_fixture_are_frozen():
    config = v5.validate_config(v5.DEFAULT_CONFIG)
    repair = config["formatting_repair"]

    assert config["experiment"].endswith("_v5")
    assert repair["primary_max_output_tokens"] == 256
    assert repair["repair_max_input_tokens"] == 2048
    assert repair["repair_max_output_tokens"] == 64
    assert repair["include_original_question"] is False
    assert repair["include_original_context"] is False
    assert config["hard_caps"]["cost_cny"] == "200.00"


def test_v5_formatting_fixture_uses_only_fabricated_examples():
    config = v5.validate_config(v5.DEFAULT_CONFIG)
    spec = config["formatting_development_fixture"]
    fixture = json.loads((v5.PROJECT_ROOT / spec["path"]).read_text(encoding="utf-8"))

    assert spec["contains_spent_searchqa_content"] is False
    assert len(fixture["cases"]) == 4
    assert v5.strict_extract_answer(fixture["cases"][0]["source_output"]) == "Mercury"
    for case in fixture["cases"][1:3]:
        messages = v5.build_format_repair_messages(case["source_output"])
        joined = "\n".join(message["content"] for message in messages)
        assert "SOURCE_OUTPUT" in joined
        assert "question" not in joined.lower()
        assert v5.strict_extract_answer(case["repair_output"]) == case["expected"]
    with pytest.raises(v5.StrictAnswerError, match="non-empty"):
        v5.build_format_repair_messages("")


def test_v5_provider_honors_per_attempt_output_cap():
    captured = {}

    class Usage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 18

    class Message:
        content = "<answer>ok</answer>"
        reasoning_content = ""

    class Response:
        id = "request-v5-test"
        usage = Usage()
        choices = [type("Choice", (), {"message": Message()})()]

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return Response()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    provider = v5.DashScopePaygProvider(
        api_key="sk-sp-test-only",
        base_url="https://example.invalid/v1",
        model="qwen3.6-flash",
        max_output_tokens=256,
        client=client,
    )

    result = provider.invoke([{"role": "user", "content": "test"}], max_output_tokens=64)

    assert result.status == "success"
    assert captured["max_tokens"] == 64
    assert captured["extra_body"] == {"enable_thinking": False}


def test_v5_format_failure_uses_one_isolated_repair(monkeypatch, tmp_path):
    config = v5.validate_config(v5.DEFAULT_CONFIG)
    responses = [
        v5.LiveAttempt(
            status="success",
            response="The fictional evidence supports Mercury as the final answer.",
            input_tokens=20,
            output_tokens=12,
            request_id="primary-request",
        ),
        v5.LiveAttempt(
            status="success",
            response="<answer>Mercury</answer>",
            input_tokens=35,
            output_tokens=6,
            request_id="repair-request",
        ),
    ]

    class Provider:
        invocations = 0

        def invoke(self, messages, *, max_output_tokens):
            self.invocations += 1
            if self.invocations == 2:
                joined = "\n".join(message["content"] for message in messages)
                assert "SOURCE_OUTPUT" in joined
                assert max_output_tokens == 64
            return responses[self.invocations - 1]

    monkeypatch.setattr(
        v5,
        "_record_from_prepared_attempts",
        lambda call, item, prepared, attempts, mode: {"attempts": attempts},
    )
    call = {
        "run_id": "phase1b-format-fixture",
        "fallback": False,
        "config_fingerprint": "config-fixture",
        "manifest_fingerprint": "manifest-fixture",
    }
    prepared = {"messages": [{"role": "user", "content": "fabricated prompt"}]}
    result = v5.execute_prepared_call(
        config,
        call,
        {"answers": ["Mercury"]},
        prepared,
        v5._empty_ledger(),
        Provider(),
        tmp_path,
        [],
        mode="live",
    )

    assert [attempt["attempt_type"] for attempt in result["attempts"]] == [
        "primary",
        "format_repair",
    ]
    assert result["attempts"][0]["status"] == "failed"
    assert result["attempts"][1]["status"] == "success"


def _prepared_fixture():
    return {
        "messages": [{"role": "user", "content": "fabricated prompt"}],
        "prompt_fingerprint": "prompt-fixture",
        "system_prompt_sha256": "system-fixture",
        "user_prompt_sha256": "user-fixture",
        "active_skill_sha256": "skill-fixture",
        "active_skill_chars": 0,
        "effective_skill_policy": "none",
        "selected_rule_indices": [],
        "selected_rule_ids": [],
        "guard_provenance": None,
    }


def _call_fixture():
    return {
        "run_id": "phase1b-v5-fixture",
        "fallback": False,
        "config_fingerprint": "config-fixture",
        "manifest_fingerprint": "manifest-fixture",
        "stage": "evaluation",
        "seed": 1,
        "method": "cold",
    }


def test_v5_provider_paces_request_start_times():
    clock = [10.0]
    sleeps = []

    class Usage:
        prompt_tokens = 2
        completion_tokens = 1
        total_tokens = 3

    class Message:
        content = "<answer>ok</answer>"
        reasoning_content = ""

    class Response:
        id = "request-paced"
        usage = Usage()
        choices = [type("Choice", (), {"message": Message()})()]

    class Completions:
        def create(self, **kwargs):
            return Response()

    def monotonic():
        return clock[0]

    def sleeper(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    provider = v5.DashScopePaygProvider(
        api_key="sk-sp-test-only",
        base_url="https://example.invalid/v1",
        model="qwen3.6-flash",
        max_output_tokens=256,
        min_request_interval_seconds=1.0,
        client=client,
        monotonic=monotonic,
        sleeper=sleeper,
    )
    provider.invoke([{"role": "user", "content": "one"}])
    clock[0] += 0.25
    provider.invoke([{"role": "user", "content": "two"}])
    assert sleeps == [0.75]


def test_v5_content_rejection_is_terminal_and_conservatively_accounted(tmp_path):
    config = v5.validate_config(v5.DEFAULT_CONFIG)

    class Provider:
        invocations = 0

        def invoke(self, messages, *, max_output_tokens):
            self.invocations += 1
            return v5.LiveAttempt(
                status="failed",
                response="",
                input_tokens=0,
                output_tokens=0,
                error="BadRequestError: rejected",
                usage_known=False,
                request_id="chatcmpl-fixture-inspection",
                provider_error_code="data_inspection_failed",
                provider_error_id="chatcmpl-fixture-inspection",
                http_status=400,
            )

    attempts = []
    record = v5.execute_prepared_call(
        config, _call_fixture(), {"answers": ["Mercury"]}, _prepared_fixture(),
        v5._empty_ledger(), Provider(), tmp_path, attempts, mode="live",
    )
    assert record["outcome"] == "provider_rejected"
    assert record["em"] == record["f1"] == record["sub_em"] == 0.0
    assert len(attempts) == 1
    assert attempts[0]["token_accounting"] == "conservative_full_envelope"
    assert attempts[0]["total_tokens"] == 8192 + 256


def test_v5_429_uses_registered_backoff_then_succeeds(tmp_path):
    config = v5.validate_config(v5.DEFAULT_CONFIG)

    class Provider:
        invocations = 0
        sleeps = []

        def sleep(self, seconds):
            self.sleeps.append(seconds)

        def invoke(self, messages, *, max_output_tokens):
            self.invocations += 1
            if self.invocations == 1:
                return v5.LiveAttempt(
                    status="failed", response="", input_tokens=0, output_tokens=0,
                    error="RateLimitError", usage_known=False,
                    provider_error_code="Throttling.RateQuota", http_status=429,
                )
            return v5.LiveAttempt(
                status="success", response="<answer>Mercury</answer>",
                input_tokens=12, output_tokens=4, request_id="request-success",
            )

    provider = Provider()
    attempts = []
    record = v5.execute_prepared_call(
        config, _call_fixture(), {"answers": ["Mercury"]}, _prepared_fixture(),
        v5._empty_ledger(), provider, tmp_path, attempts, mode="live",
    )
    assert record["parse_status"] == "valid"
    assert provider.sleeps == [2.0]
    assert [attempt["attempt_type"] for attempt in attempts] == ["primary", "primary_retry"]
    assert attempts[0]["token_accounting"] == "conservative_full_envelope"