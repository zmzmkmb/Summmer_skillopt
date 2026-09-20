#!/usr/bin/env python3
"""Token Plan transport for a future separately authorized Phase 2 run."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable


TOKEN_PLAN_ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"


class ProviderAdapterError(RuntimeError):
    pass


class QwenTokenPlanProviderAdapter:
    def __init__(
        self,
        authorization: dict[str, Any],
        *,
        key_source: Callable[[], str | None] | None = None,
        transport: Callable[[str, dict[str, str], bytes], dict[str, Any]] | None = None,
    ):
        if authorization.get("status") != "open" or not all(
            authorization.get(key) is True
            for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")
        ):
            raise ProviderAdapterError("provider adapter activation denied")
        key = (key_source or (lambda: os.environ.get("DASHSCOPE_API_KEY")))()
        if not key:
            raise ProviderAdapterError("provider API key missing")
        self._key = key
        self._transport = transport or self._urlopen_transport
        self.calls = 0

    @staticmethod
    def _urlopen_transport(url: str, headers: dict[str, str], data: bytes) -> dict[str, Any]:
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - separately authorized route only
            return json.loads(response.read().decode("utf-8"))

    def __call__(self, body: dict[str, Any]) -> dict[str, Any]:
        if "max_tokens" in body or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0:
            raise ProviderAdapterError("request route/model/temperature drift")
        self.calls += 1
        payload = {
            "model": body["model_id"],
            "messages": body["messages"],
            "temperature": body["temperature"],
            "enable_thinking": False,
        }
        raw = self._transport(
            TOKEN_PLAN_ENDPOINT,
            {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        )
        try:
            choice = raw["choices"][0]["message"]["content"]
            usage = raw["usage"]
            return {
                "content": choice,
                "usage": {
                    "input_tokens": usage["prompt_tokens"],
                    "output_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                },
                "request_id": raw.get("id"),
                "raw_provider_response": raw,
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderAdapterError("provider response schema invalid") from exc
