#!/usr/bin/env python3
"""Frozen deterministic response parser and private-gold verifier for Phase 2 v3."""
from __future__ import annotations

import hashlib
import json
import string
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_GOLD_PARTITIONS = frozenset({"formal_history", "probe"})


class VerificationError(RuntimeError):
    pass


def stable(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_answer(value: str) -> str:
    value = value.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in value.split() if token not in {"a", "an", "the"})


def parse_response(raw_response: Any) -> dict[str, str]:
    if not isinstance(raw_response, str):
        raise VerificationError("raw response must be text")
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise VerificationError("response parser failed") from exc
    if not isinstance(payload, dict) or set(payload) != {"answer"}:
        raise VerificationError("response schema must contain exactly answer")
    answer = payload["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise VerificationError("response answer must be non-empty text")
    return {"answer": answer}


def load_gold(partition: str, *, root: Path = ROOT) -> tuple[dict[str, dict[str, Any]], Path]:
    if partition not in ALLOWED_GOLD_PARTITIONS:
        raise VerificationError(f"gold access forbidden for partition: {partition}")
    path = root / "data/searchqa_phase2_verified" / f"{partition}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        task_id = str(row.get("task_id", ""))
        answers = row.get("answers") if row.get("task_family") == "SearchQA" else [row.get("answer")]
        if not task_id or not isinstance(answers, list) or not answers or not all(isinstance(x, str) and x.strip() for x in answers):
            raise VerificationError("private gold record is malformed")
        if task_id in indexed:
            raise VerificationError("duplicate task in private gold")
        indexed[task_id] = {
            **row,
            "answers": answers,
            "_frozen_payload_sha256": stable(row),
        }
    return indexed, path


def verify_response(raw_response: Any, gold: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_response(raw_response)
    expected = {normalize_answer(value) for value in gold["answers"]}
    answer_correct = normalize_answer(parsed["answer"]) in expected
    return {
        "parsed_response": parsed,
        "answer_correct": answer_correct,
        "verifier_confirmed_success": answer_correct,
    }
