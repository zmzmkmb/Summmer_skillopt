#!/usr/bin/env python3
"""Real Qwen provider adapter for v3; inert until a fully open authorization passes."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable


class ProviderAdapterError(RuntimeError):
    pass


class QwenProviderAdapter:
    def __init__(self, authorization: dict[str, Any], *, key_source: Callable[[], str | None] | None = None,
                 transport: Callable[[str, dict[str, str], bytes], dict[str, Any]] | None = None):
        if authorization.get("status") != "open" or not all(authorization.get(key) is True for key in (
            "paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open"
        )):
            raise ProviderAdapterError("provider adapter activation denied")
        key_source = key_source or (lambda: os.environ.get("DASHSCOPE_API_KEY"))
        key = key_source()
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
        self.calls += 1
        payload = {"model": body["model_id"], "messages": body["messages"], "temperature": body["temperature"]}
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        raw = self._transport(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers, json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        )
        try:
            choice = raw["choices"][0]["message"]["content"]
            usage = raw["usage"]
            return {
                "content": choice,
                "usage": {"input_tokens": usage["prompt_tokens"], "output_tokens": usage["completion_tokens"], "total_tokens": usage["total_tokens"]},
                "request_id": raw.get("id"),
                "raw_provider_response": raw,
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderAdapterError("provider response schema invalid") from exc
