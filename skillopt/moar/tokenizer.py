"""Token counting wrapper for MOAR cost estimation.

Uses tiktoken (lightweight, no model download) for fast offline token counting.
Defaults to cl100k_base (GPT-4 / Qwen2-compatible encoding).

Journal usage: replace ``len(rule_text)`` character counts with actual token counts
in FeatureCache.token_costs.
"""
from __future__ import annotations

import tiktoken


class TokenCounter:
    """Lightweight token counter wrapping tiktoken.

    Parameters
    ----------
    encoding_name : str
        tiktoken encoding name.  ``"cl100k_base"`` is the default and works
        well as an approximation for Qwen / GPT-4 family models.
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._encoding_name = encoding_name
        self._enc = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        """Return the number of tokens in *text*."""
        return len(self._enc.encode(text, disallowed_special=()))

    def count_batch(self, texts: list[str]) -> list[int]:
        """Return token counts for a batch of texts."""
        return [len(tokens) for tokens in
                self._enc.encode_batch(texts, disallowed_special=())]

    @property
    def encoding_name(self) -> str:
        return self._encoding_name


# Singleton for module-level reuse
_counter: TokenCounter | None = None


def get_counter(encoding: str = "cl100k_base") -> TokenCounter:
    """Return (or create) a cached TokenCounter."""
    global _counter
    if _counter is None or _counter.encoding_name != encoding:
        _counter = TokenCounter(encoding)
    return _counter


def count_tokens(text: str) -> int:
    """Convenience: count tokens in a single string."""
    return get_counter().count(text)


def count_tokens_batch(texts: list[str]) -> list[int]:
    """Convenience: count tokens in a batch of strings."""
    return get_counter().count_batch(texts)
