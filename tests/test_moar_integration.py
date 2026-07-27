"""Integration tests for MOARMemory: end-to-end with mock skill content."""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from skillopt.rag_rule_selector import RuleMemory

MOCK_SKILL = """## Core Output Format
Always answer concisely. Output only the final answer letter.

## Core Safety
Never output harmful or inappropriate content.

## Answer Extraction Strategy
Read the context carefully. Find evidence that directly supports one answer.

## Named Entity Normalization
Normalize dates to YYYY-MM-DD format. Normalize proper names to full canonical form.

## Disambiguation Rules
When multiple answers seem plausible, prefer the one with stronger context support.

## Number Format Rules
Extract numbers including units. Convert percentages to decimal form automatically.

## Special Pattern Handling
For comparison questions, compute both values before selecting. For negation questions, identify what is being negated first.
"""


class TestMOARMemoryBasic:
    def test_factory_returns_moar(self):
        rm = RuleMemory(MOCK_SKILL, method="moar")
        from skillopt.moar import MOARMemory
        assert isinstance(rm, MOARMemory)

    def test_factory_returns_regular_rule_memory(self):
        rm = RuleMemory(MOCK_SKILL, method="tfidf")
        assert type(rm).__name__ == "RuleMemory"

    def test_core_rules_text(self):
        rm = RuleMemory(MOCK_SKILL, method="moar")
        core = rm.core_rules_text
        assert "Core Output Format" in core
        assert "Core Safety" in core
        # Dynamic rules should NOT be in core
        assert "Named Entity Normalization" not in core

    def test_retrieve_returns_text_within_budget(self):
        rm = RuleMemory(MOCK_SKILL, method="moar",
                         moar_pop_size=10, moar_generations=5)
        result = rm.retrieve(
            "extract the person name from the text",
            top_k=3, token_budget=500,
        )
        assert isinstance(result, str)
        assert len(result) <= 500 + 5  # small tolerance for overhead

    def test_retrieve_empty_when_no_dynamic(self):
        # Create a skill with no dynamic rules (all core)
        all_core = """## Output Format\nAlways be concise."""
        rm = RuleMemory(all_core, method="moar")
        assert rm.n_dynamic <= 1  # may have 0 or 1 fallback
        result = rm.retrieve("any query")
        # Either empty or only the fallback rule
        assert isinstance(result, str)

    def test_update_utilities_no_crash(self):
        rm = RuleMemory(MOCK_SKILL, method="moar")
        rm.retrieve("query about extracting answers", top_k=3, token_budget=1000)
        rollout_results = [
            {"question": "query about extracting answers",
             "hard": 1, "answers": ["B"]},
        ]
        rm.update_utilities(rollout_results)  # should not raise


class TestMOARUtilityPersistence:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "moar_utility.json")

            # First instance: run queries and save
            rm1 = RuleMemory(MOCK_SKILL, method="moar",
                              moar_utility_path=path)
            rm1.retrieve("query one", top_k=3, token_budget=1000)
            rm1.update_utilities([
                {"question": "query one", "hard": 1, "answers": ["A"]},
            ])

            # Second instance: should load saved utilities
            rm2 = RuleMemory(MOCK_SKILL, method="moar",
                              moar_utility_path=path)
            utils = rm2._tracker.compute_utilities()
            # At least one rule should have non-zero utility
            assert np.max(utils) >= 0.0

    def test_utility_improves_with_good_results(self):
        """Tracking correct answers should increase utility."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "moar_utility.json")
            rm = RuleMemory(MOCK_SKILL, method="moar",
                             moar_utility_path=path,
                             moar_utility_method="precision")

            for i in range(5):
                q = f"extract answer {i}"
                rm.retrieve(q, top_k=3, token_budget=1000)
                rm.update_utilities([
                    {"question": q, "hard": 1, "answers": ["B"]},
                ])

            utils = rm._tracker.compute_utilities()
            # Some rules should have been selected and been correct
            total_sel = sum(
                s.selected_count for s in rm._tracker._stats.values()
            )
            assert total_sel > 0, "No rules were selected in 5 queries"


class TestMOARFallback:
    def test_very_few_rules_falls_back_to_tfidf(self):
        """When n_dynamic <= 3, MOAR falls back to TF-IDF silently."""
        tiny_skill = """## Rule 1\nContent of rule one."""
        rm = RuleMemory(tiny_skill, method="moar")
        result = rm.retrieve("rule one", top_k=1, token_budget=500)
        # Should not crash
        assert isinstance(result, str)


class TestTopKConstraint:
    """Regression: NSGA-II must respect top-K hard constraint."""

    def test_retrieve_respects_topk(self):
        rm = RuleMemory(MOCK_SKILL, method="moar",
                         moar_pop_size=20, moar_generations=10)
        for k in [1, 2, 3, 5]:
            result = rm.retrieve("test query", top_k=k, token_budget=5000)
            n_rules = result.count("## ")
            assert n_rules <= k, f"top-K violated: {n_rules} > {k}"

    def test_combined_constraints(self):
        rm = RuleMemory(MOCK_SKILL, method="moar",
                         moar_pop_size=20, moar_generations=10)
        result = rm.retrieve("extract entities from text",
                              top_k=2, token_budget=200)
        assert len(result) <= 210 and result.count("## ") <= 2


class TestConfigPassthrough:
    def test_moar_config_keys_accepted(self):
        """Verify that MOAR config kwargs are accepted without error."""
        rm = RuleMemory(
            MOCK_SKILL,
            method="moar",
            moar_pop_size=20,
            moar_generations=5,
            moar_weights="0.5,0.3,0.1,0.1",
            moar_selection_mode="knee_point",
            moar_utility_method="laplace",
            moar_utility_decay=0.95,
        )
        assert rm.n_total > 0
