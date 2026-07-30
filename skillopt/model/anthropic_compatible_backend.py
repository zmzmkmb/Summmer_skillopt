"""Anthropic-compatible chat backend (DashScope Anthropic endpoint)."""
from __future__ import annotations
import os, time, threading
from typing import Any

from skillopt.model.common import default_model_for_backend

BACKEND_NAME = "anthropic_compatible"
_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/apps/anthropic"
_DEFAULT_MODEL = "qwen3.6-flash"

_config_lock = threading.Lock()
_client_lock = threading.Lock()

OPTIMIZER_BASE_URL = _DEFAULT_BASE_URL
OPTIMIZER_API_KEY = ""
OPTIMIZER_MODEL = _DEFAULT_MODEL
TARGET_BASE_URL = _DEFAULT_BASE_URL
TARGET_API_KEY = ""
TARGET_MODEL = _DEFAULT_MODEL


def _init_from_env():
    global OPTIMIZER_BASE_URL, OPTIMIZER_API_KEY, OPTIMIZER_MODEL
    global TARGET_BASE_URL, TARGET_API_KEY, TARGET_MODEL

    def _role_env(role, key, default):
        rk = f"{role.upper()}_ANTHROPIC_COMPATIBLE_{key}"
        gk = f"ANTHROPIC_COMPATIBLE_{key}"
        return os.environ.get(rk) or os.environ.get(gk) or default

    # Also fall back to OpenAI-compatible env vars for key
    def _key_env(role):
        rk = f"{role.upper()}_OPENAI_COMPATIBLE_API_KEY"
        gk = "OPENAI_COMPATIBLE_API_KEY"
        return os.environ.get(rk) or os.environ.get(gk) or ""

    OPTIMIZER_BASE_URL = _role_env("optimizer", "BASE_URL", _DEFAULT_BASE_URL)
    OPTIMIZER_API_KEY = _key_env("optimizer")
    OPTIMIZER_MODEL = _role_env("optimizer", "MODEL", _DEFAULT_MODEL)
    TARGET_BASE_URL = _role_env("target", "BASE_URL", _DEFAULT_BASE_URL)
    TARGET_API_KEY = _key_env("target")
    TARGET_MODEL = _role_env("target", "MODEL", _DEFAULT_MODEL)


_init_from_env()


def configure_anthropic_compatible(
    *,
    target_base_url=None, target_api_key=None, target_model=None,
    optimizer_base_url=None, optimizer_api_key=None, optimizer_model=None,
):
    global TARGET_BASE_URL, TARGET_API_KEY, TARGET_MODEL
    global OPTIMIZER_BASE_URL, OPTIMIZER_API_KEY, OPTIMIZER_MODEL
    with _config_lock:
        if target_base_url is not None:
            TARGET_BASE_URL = str(target_base_url).rstrip("/")
            os.environ["TARGET_ANTHROPIC_COMPATIBLE_BASE_URL"] = TARGET_BASE_URL
        if target_api_key is not None:
            TARGET_API_KEY = str(target_api_key)
            os.environ["TARGET_ANTHROPIC_COMPATIBLE_API_KEY"] = TARGET_API_KEY
        if target_model is not None:
            TARGET_MODEL = str(target_model)
        if optimizer_base_url is not None:
            OPTIMIZER_BASE_URL = str(optimizer_base_url).rstrip("/")
        if optimizer_api_key is not None:
            OPTIMIZER_API_KEY = str(optimizer_api_key)
        if optimizer_model is not None:
            OPTIMIZER_MODEL = str(optimizer_model)


def set_target_deployment(deployment: str):
    global TARGET_MODEL
    TARGET_MODEL = deployment


def set_optimizer_deployment(deployment: str):
    global OPTIMIZER_MODEL
    OPTIMIZER_MODEL = deployment


def _chat(role, system, user, max_completion_tokens, retries, stage, timeout=None):
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic SDK required: pip install anthropic")

    base = TARGET_BASE_URL if role == "target" else OPTIMIZER_BASE_URL
    key = TARGET_API_KEY if role == "target" else OPTIMIZER_API_KEY
    model = TARGET_MODEL if role == "target" else OPTIMIZER_MODEL

    client = anthropic.Anthropic(base_url=base, api_key=key or "dummy",
                                  timeout=timeout or 300)

    msgs = []
    if system:
        msgs = [{"role": "user", "content": user}]
    else:
        msgs = [{"role": "user", "content": user}]

    kwargs = dict(
        model=model,
        max_tokens=min(max_completion_tokens, 8000),
        messages=[{"role": "user", "content": user}],
        thinking={"type": "disabled"},
    )
    if system:
        kwargs["system"] = system
    if timeout:
        kwargs["timeout"] = timeout

    last_err = None
    for attempt in range(retries):
        try:
            resp = client.messages.create(**kwargs)
            text = ""
            for block in (resp.content or []):
                bt = getattr(block, "type", "")
                if bt == "text":
                    text += getattr(block, "text", "")
                # skip "thinking" blocks from extended thinking models
            usage = {"prompt_tokens": getattr(resp.usage, "input_tokens", 0),
                     "completion_tokens": getattr(resp.usage, "output_tokens", 0)}
            return text, usage
        except Exception as e:
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"Anthropic chat failed after {retries} retries: {last_err}")


def chat_target(system, user, max_completion_tokens=512, retries=2, stage="target",
                reasoning_effort=None, timeout=None):
    del reasoning_effort
    return _chat("target", system, user, max_completion_tokens, retries, stage, timeout)


def chat_optimizer(system, user, max_completion_tokens=16384, retries=5, stage="optimizer",
                   reasoning_effort=None, timeout=None):
    del reasoning_effort
    return _chat("optimizer", system, user, max_completion_tokens, retries, stage, timeout)
