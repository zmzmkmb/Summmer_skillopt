"""MMLU-Pro evaluator — exact match on option label."""
from __future__ import annotations

import re


def extract_answer(text: str) -> str:
    """Extract the predicted option letter from the model's response."""
    # Look for explicitly stated letter
    matches = re.findall(r'\b([A-J])\b', str(text).strip().upper())
    if matches:
        return matches[-1]
    return "?"


def evaluate(prediction_text: str, gold_answers: list[str]) -> dict:
    predicted = extract_answer(prediction_text)
    gold_letter = str(gold_answers[0]).strip().upper() if gold_answers else "?"
    is_correct = float(predicted == gold_letter)
    return {
        "em": is_correct,
        "f1": is_correct,
        "sub_em": is_correct,
        "predicted_answer": predicted,
        "hard": int(is_correct),
        "soft": is_correct,
        "predicted_label": predicted,
        "gold_label": gold_letter,
    }
