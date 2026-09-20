from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.acl2027_phase2_token_plan_provider_adapter_v6 import (
    TOKEN_PLAN_ENDPOINT,
    ProviderAdapterError,
    QwenTokenPlanProviderAdapter,
)
from scripts.run_acl2027_phase2_token_plan_route_preflight_v6 import CONFIG, PreflightError, build_manifest, load, validate_config


def test_route_preflight_is_closed_and_binds_terminal_v5() -> None:
    manifest = build_manifest()
    assert manifest["status"] == "preflight-passed-closed"
    assert manifest["route"]["endpoint"].startswith("https://token-plan.cn-beijing.maas.aliyuncs.com/")
    assert manifest["v5_ledger_sha256"]
    assert all(value == 0 for value in manifest["counters"].values())


def test_route_drift_is_rejected() -> None:
    config = deepcopy(load(CONFIG))
    config["token_plan_route"]["endpoint"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    with pytest.raises(PreflightError):
        validate_config(config)


def test_adapter_uses_token_plan_endpoint_and_omits_max_tokens() -> None:
    observed: dict[str, object] = {}

    def transport(url: str, headers: dict[str, str], data: bytes) -> dict[str, object]:
        observed.update(url=url, headers=headers, payload=json.loads(data))
        return {"id": "request-1", "choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}

    auth = {"status": "open", "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True}
    adapter = QwenTokenPlanProviderAdapter(auth, key_source=lambda: "sk-test", transport=transport)
    result = adapter({"model_id": "qwen3.7-plus", "messages": [{"role": "user", "content": "x"}], "temperature": 0})
    assert observed["url"] == TOKEN_PLAN_ENDPOINT
    assert observed["headers"] == {"Authorization": "Bearer sk-test", "Content-Type": "application/json"}
    assert observed["payload"] == {"model": "qwen3.7-plus", "messages": [{"role": "user", "content": "x"}], "temperature": 0, "enable_thinking": False}
    assert result["usage"]["total_tokens"] == 5


def test_adapter_rejects_closed_or_drifted_requests() -> None:
    with pytest.raises(ProviderAdapterError):
        QwenTokenPlanProviderAdapter({"status": "closed", "paid_api_allowed": False, "provider_calls_allowed": False, "qwen_authorization_open": False}, key_source=lambda: "sk-test")
    auth = {"status": "open", "paid_api_allowed": True, "provider_calls_allowed": True, "qwen_authorization_open": True}
    adapter = QwenTokenPlanProviderAdapter(auth, key_source=lambda: "sk-test", transport=lambda *_: {})
    with pytest.raises(ProviderAdapterError):
        adapter({"model_id": "qwen3.7-plus", "messages": [], "temperature": 0, "max_tokens": 1})
