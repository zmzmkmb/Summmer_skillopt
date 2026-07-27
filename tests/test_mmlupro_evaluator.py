"""Unit tests for MMLU-Pro evaluator: answer extraction and scoring."""
from __future__ import annotations

import pytest

from skillopt.envs.mmlupro.evaluator import evaluate, extract_answer


class TestExtractAnswer:
    def test_single_letter(self):
        assert extract_answer("B") == "B"

    def test_letter_with_context(self):
        assert extract_answer("The answer is B because ...") == "B"

    def test_parenthesized_letter(self):
        assert extract_answer("Final answer: (D)") == "D"

    def test_boxed(self):
        assert extract_answer(r"\boxed{H}") == "H"

    def test_multiple_letters_takes_last(self):
        assert extract_answer("A vs B vs C") == "C"

    def test_lowercase_normalised(self):
        assert extract_answer("the correct choice is a") == "A"

    def test_empty_input(self):
        assert extract_answer("") == "?"

    def test_no_letter(self):
        assert extract_answer("No answer provided") == "?"

    def test_kitchen_sink(self):
        resp = "Let me think... x=5, so A. The answer is A."
        assert extract_answer(resp) == "A"


class TestEvaluate:
    def test_correct_answer(self):
        r = evaluate("B", ["B"])
        assert r["em"] == 1.0
        assert r["hard"] == 1
        assert r["predicted_answer"] == "B"

    def test_wrong_answer(self):
        r = evaluate("B", ["D"])
        assert r["em"] == 0.0
        assert r["hard"] == 0

    def test_case_insensitive_gold(self):
        r = evaluate("B", ["b"])
        assert r["em"] == 1.0

    def test_response_with_reasoning(self):
        r = evaluate("After analysis, the answer is C.", ["C"])
        assert r["hard"] == 1

    def test_last_letter_wins(self):
        r = evaluate("A B C D E", ["E"])
        assert r["hard"] == 1
