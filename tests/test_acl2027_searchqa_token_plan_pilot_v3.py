"""Phase 1B v3 contracts for the provider-authorized Token Plan pilot."""
from __future__ import annotations

import copy
import json

import pytest

from scripts.run_acl2027_searchqa_token_plan_pilot import (
    DEFAULT_CONFIG,
    ConfigError,
    DashScopePaygProvider,
    ProviderUsageError,
    _provider_for_mode,
    build_call_plan,
    build_replicate_manifest,
    load_searchqa_items,
    validate_config,
)


def test_v3_authorized_token_plan_contract_and_workload():
    config = validate_config(DEFAULT_CONFIG)
    items = load_searchqa_items(config)
    manifest = build_replicate_manifest(config, items)
    plan = build_call_plan(config, manifest)

    assert config["execution"]["billing_route"] == "token_plan_authorized"
    assert config["execution"]["token_plan_allowed"] is True
    assert config["execution"]["provider_written_permission_attested"] is True
    assert config["model"]["provider"] == "alibaba_cloud_token_plan"
    assert config["model"]["model_id"] == "qwen3.6-flash"
    assert config["model"]["endpoint"] == (
        "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    )
    assert config["hard_caps"]["cost_cny"] == "200.00"
    assert len(plan) == 2448
    assert sum(bool(call["fallback"]) for call in plan) == 48


def test_v3_refuses_missing_written_permission_attestation(tmp_path):
    config = validate_config(DEFAULT_CONFIG)
    modified = copy.deepcopy(config)
    modified.pop("_validated", None)
    modified["execution"]["provider_written_permission_attested"] = False
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(modified), encoding="utf-8")

    with pytest.raises(ConfigError, match="written provider permission"):
        validate_config(path)


def test_v3_live_provider_requires_token_plan_key(monkeypatch):
    config = validate_config(DEFAULT_CONFIG)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-not-token-plan")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", config["model"]["endpoint"])

    with pytest.raises(ProviderUsageError, match="sk-sp-"):
        _provider_for_mode(config, "live")


def test_v3_provider_sends_qwen36_and_disables_thinking():
    captured = {}

    class Usage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 18

    class Message:
        content = "<answer>ok</answer>"
        reasoning_content = ""

    class Response:
        id = "request-token-plan-test"
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
        api_key="sk-sp-test-only",
        base_url="https://example.invalid/v1",
        model="qwen3.6-flash",
        max_output_tokens=32,
        client=client,
    )

    result = provider.invoke([{"role": "user", "content": "test"}])

    assert result.status == "success"
    assert result.request_id == "request-token-plan-test"
    assert (result.input_tokens, result.output_tokens) == (11, 7)
    assert captured["model"] == "qwen3.6-flash"
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == 32
    assert captured["extra_body"] == {"enable_thinking": False}
