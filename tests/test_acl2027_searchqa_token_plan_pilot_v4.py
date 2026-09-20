"""Phase 1B v4 formatting-robustness contracts."""
from __future__ import annotations

import json

import pytest

import scripts.run_acl2027_searchqa_token_plan_pilot_v4 as v4


def test_v4_contract_and_fixture_are_frozen():
    config = v4.validate_config(v4.DEFAULT_CONFIG)
    repair = config["formatting_repair"]

    assert config["experiment"].endswith("_v4")
    assert repair["primary_max_output_tokens"] == 256
    assert repair["repair_max_input_tokens"] == 2048
    assert repair["repair_max_output_tokens"] == 64
    assert repair["include_original_question"] is False
    assert repair["include_original_context"] is False
    assert config["hard_caps"]["cost_cny"] == "200.00"


def test_v4_formatting_fixture_uses_only_fabricated_examples():
    config = v4.validate_config(v4.DEFAULT_CONFIG)
    spec = config["formatting_development_fixture"]
    fixture = json.loads((v4.PROJECT_ROOT / spec["path"]).read_text(encoding="utf-8"))

    assert spec["contains_spent_searchqa_content"] is False
    assert len(fixture["cases"]) == 4
    assert v4.strict_extract_answer(fixture["cases"][0]["source_output"]) == "Mercury"
    for case in fixture["cases"][1:3]:
        messages = v4.build_format_repair_messages(case["source_output"])
        joined = "\n".join(message["content"] for message in messages)
        assert "SOURCE_OUTPUT" in joined
        assert "question" not in joined.lower()
        assert v4.strict_extract_answer(case["repair_output"]) == case["expected"]
    with pytest.raises(v4.StrictAnswerError, match="non-empty"):
        v4.build_format_repair_messages("")


def test_v4_provider_honors_per_attempt_output_cap():
    captured = {}

    class Usage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 18

    class Message:
        content = "<answer>ok</answer>"
        reasoning_content = ""

    class Response:
        id = "request-v4-test"
        usage = Usage()
        choices = [type("Choice", (), {"message": Message()})()]

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return Response()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    provider = v4.DashScopePaygProvider(
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


def test_v4_format_failure_uses_one_isolated_repair(monkeypatch, tmp_path):
    config = v4.validate_config(v4.DEFAULT_CONFIG)
    responses = [
        v4.LiveAttempt(
            status="success",
            response="The fictional evidence supports Mercury as the final answer.",
            input_tokens=20,
            output_tokens=12,
            request_id="primary-request",
        ),
        v4.LiveAttempt(
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
        v4,
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
    result = v4.execute_prepared_call(
        config,
        call,
        {"answers": ["Mercury"]},
        prepared,
        v4._empty_ledger(),
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
