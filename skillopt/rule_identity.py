"""Stable identities and fingerprints for parsed skill rules.

Rule positions are convenient within one process but are not durable experiment
identifiers: inserting or reordering a rule changes every downstream index.  The
helpers here derive identities from canonicalized rule text so selections remain
comparable across library orderings and sizes.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable


def normalize_rule_text(text: str) -> str:
    """Return a deterministic representation without changing internal layout."""
    normalized = unicodedata.normalize("NFKC", str(text)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def rule_text_hash(text: str) -> str:
    """Return the full SHA-256 hash of canonicalized rule text."""
    return hashlib.sha256(normalize_rule_text(text).encode("utf-8")).hexdigest()


def stable_rule_id(text: str) -> str:
    """Return a compact content-addressed rule ID stable under reordering."""
    return f"rule-{rule_text_hash(text)[:16]}"


def rule_set_fingerprint(rule_texts: Iterable[str]) -> str:
    """Fingerprint a multiset of rules independently of library ordering."""
    hashes = sorted(rule_text_hash(text) for text in rule_texts)
    payload = json.dumps(hashes, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
