from __future__ import annotations

import json
from pathlib import Path

from skillopt.evaluation.router_scaling import _enforce_exact_budget, evaluate_library
from skillopt.moar.tokenizer import count_tokens
from skillopt.rag_rule_selector import RuleMemory


LIBRARY = """## Output Format
Return one concise answer.

## Search Person
For person questions, identify the named individual.

## Search Place
For location questions, identify the requested place.

## Distractor Math
Solve an algebra equation.

## Distractor Law
Apply a legal doctrine.
"""


def _manifest(memory: RuleMemory) -> dict:
    return {
        "n_dynamic_rules": memory.n_dynamic,
        "rule_set_fingerprint": memory.rule_set_fingerprint,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "role": "base" if index < 2 else "distractor",
            }
            for index, rule in enumerate(memory.dynamic_rules)
        ],
    }


def test_offline_router_scaling_emits_stable_ids_and_proxy_metrics(tmp_path: Path):
    path = tmp_path / "library.md"
    path.write_text(LIBRARY, encoding="utf-8")
    memory = RuleMemory(LIBRARY)
    items = [
        {"id": "q1", "question": "Who was the named person?"},
        {"id": "q2", "question": "Which place is being requested?"},
    ]
    methods = ["tfidf", "bm25", "greedy-cold", "greedy-utility", "moar"]

    summaries, details = evaluate_library(
        library_path=path,
        library_manifest=_manifest(memory),
        items=items,
        methods=methods,
        utility_path=None,
        top_k=2,
        budget=500,
        seed=7,
        moar_pop_size=4,
        moar_generations=2,
    )

    assert {row["method"] for row in summaries} == set(methods)
    assert all(row["library_size"] == 4 for row in summaries)
    assert all(row["budget_violations"] == 0 for row in summaries)
    assert all(0.0 <= row["base_selection_precision_proxy"] <= 1.0 for row in summaries)
    for rows in details.values():
        assert len(rows) == 2
        assert all(len(row["selected_indices"]) == len(row["selected_rule_ids"]) for row in rows)
        assert all(type(index) is int for row in rows for index in row["selected_indices"])
        assert all(rule_id.startswith("rule-") for row in rows for rule_id in row["selected_rule_ids"])
    json.dumps(details)


def test_selector_fingerprints_are_deterministic(tmp_path: Path):
    path = tmp_path / "library.md"
    path.write_text(LIBRARY, encoding="utf-8")
    memory = RuleMemory(LIBRARY)
    items = [{"id": "q1", "question": "Who is the person?"}]
    kwargs = dict(
        library_path=path,
        library_manifest=_manifest(memory),
        items=items,
        methods=["tfidf", "bm25", "greedy-cold", "moar"],
        utility_path=None,
        top_k=2,
        budget=500,
        seed=11,
        moar_pop_size=4,
        moar_generations=2,
    )

    first, _ = evaluate_library(**kwargs)
    second, _ = evaluate_library(**kwargs)

    assert {
        row["method"]: row["selection_fingerprint"] for row in first
    } == {
        row["method"]: row["selection_fingerprint"] for row in second
    }


def test_exact_budget_guard_uses_rendered_selection_tokens():
    rule_texts = ["alpha " * 40, "beta " * 40, "gamma"]
    budget = count_tokens(rule_texts[0])

    selected = _enforce_exact_budget([0, 1, 2], rule_texts, budget=budget)

    assert selected == [0]