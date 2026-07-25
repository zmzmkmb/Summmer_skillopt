"""RAG-based rule retrieval for dynamic skill construction.

Parses a trained skill markdown into atomic rules, separates core rules
(always active: output format, safety, extraction strategy) from dynamic
rules (content-specific: entity normalization, relation extraction, etc.),
embeds dynamic rules with TF-IDF, and retrieves the top-K most relevant
rules for each query at rollout time.

Zero new dependencies: uses only sklearn + numpy (already in requirements.txt).

Typical usage::

    from skillopt.rag_rule_selector import RuleMemory
    rm = RuleMemory(skill_content, top_k=8, token_budget=2000)
    active = rm.core_rules_text + "\n\n" + rm.retrieve(question)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Rule:
    """One atomic rule parsed from a skill markdown document."""

    index: int
    heading: str
    body: str
    full_text: str
    is_core: bool = False
    weight: float = 1.0  # future: updated by forget-gate
    historical_gain: float = 0.0  # future: per-rule validation contribution
    conflict_score: float = 0.0  # future: conflict detection signal

    def __repr__(self) -> str:
        kind = "CORE" if self.is_core else "DYN"
        return f"Rule({self.index}, {kind}, {self.heading[:60]!r})"


class RuleMemory:
    """Parse, embed, and retrieve rules from a skill markdown document.

    Parameters
    ----------
    skill_content
        Raw markdown content of the skill file.
    top_k
        Default number of dynamic rules to retrieve per query.
    token_budget
        Maximum character length of the concatenated active skill.
    method
        Embedding method: ``"tfidf"`` (default, zero-download) or
        ``"chromadb"`` (semantic, requires one-time model download).
    """

    _CORE_KEYWORDS: ClassVar[list[str]] = [
        "answer format",
        "output format",
        "<answer>",
        "concise answer",
        "answer formatting",
        "safety",
        "core principle",
        "extraction strategy",
    ]

    def __init__(
        self,
        skill_content: str,
        top_k: int = 5,
        token_budget: int = 2000,
        method: str = "tfidf",
    ) -> None:
        self.skill_content = skill_content
        self.top_k = top_k
        self.token_budget = token_budget
        self.method = method

        # Parse
        self._rules: list[Rule] = self._parse_rules(skill_content)

        # Separate
        self._core_rules = [r for r in self._rules if r.is_core]
        self._dynamic_rules = [r for r in self._rules if not r.is_core]

        # Embed dynamic rules
        self._vectorizer: TfidfVectorizer | None = None
        self._rule_matrix: np.ndarray | None = None
        if self._dynamic_rules:
            self._build_embeddings()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def core_rules_text(self) -> str:
        """Concatenated core rules (always active)."""
        if not self._core_rules:
            return ""
        return "\n\n".join(r.full_text for r in sorted(self._core_rules, key=lambda x: x.index))

    @property
    def dynamic_rules(self) -> list[Rule]:
        """List of retrievable dynamic rules."""
        return self._dynamic_rules

    @property
    def n_total(self) -> int:
        return len(self._rules)

    @property
    def n_core(self) -> int:
        return len(self._core_rules)

    @property
    def n_dynamic(self) -> int:
        return len(self._dynamic_rules)

    # ── Retrieval ─────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        token_budget: int | None = None,
    ) -> str:
        """Return top-K dynamic rules most relevant to *query*.

        Returns the concatenated rule texts, truncated at token_budget
        characters (on rule boundaries).
        """
        k = top_k if top_k is not None else self.top_k
        budget = token_budget if token_budget is not None else self.token_budget

        if not self._dynamic_rules or self._vectorizer is None or self._rule_matrix is None:
            return ""

        k = min(k, len(self._dynamic_rules))

        # Vectorize query and score
        query_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self._rule_matrix).flatten()

        # Top-K by similarity
        indices = np.argsort(sims)[::-1][:k]

        # Sort by original index for logical ordering
        selected = sorted(indices, key=lambda i: self._dynamic_rules[i].index)

        # Concatenate with length budget, truncated at rule boundaries.
        # If a single rule exceeds budget, truncate it to fit.
        parts: list[str] = []
        used = 0
        for i in selected:
            text = self._dynamic_rules[i].full_text
            if used + len(text) > budget:
                if parts:
                    break  # already have some rules, stop here
                # First rule alone exceeds budget — truncate it
                text = text[:budget] + "…"
            parts.append(text)
            used += len(text) + 2

        return "\n\n".join(parts)

    # ── Parse ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_rules(skill_content: str) -> list[Rule]:
        """Parse skill markdown into atomic rules.

        Strategy:
        1. Split by ``## `` level-2 headings into sections
        2. Within each section, split by ``### `` into sub-rules
        3. Each (heading, body) pair becomes one Rule
        4. Drop intro preamble (before first ``## ``)
        """
        if not skill_content or not skill_content.strip():
            return []

        # Step 1: split by ## headings
        sections = re.split(r"\n(?=## )", skill_content)

        # Drop preamble before first ## section
        if sections and not sections[0].strip().startswith("##"):
            sections = sections[1:]

        if not sections:
            # No structured headings → whole content as one rule
            return [Rule(
                index=0,
                heading="Full Skill",
                body=skill_content.strip(),
                full_text=skill_content.strip(),
                is_core=False,
            )]

        # Step 2: split each ## section by ### sub-headings
        rules: list[Rule] = []
        idx = 0
        for section in sections:
            subs = re.split(r"\n(?=### )", section)
            for sub in subs:
                lines = sub.strip().split("\n", 1)
                heading = lines[0].strip()
                body = lines[1].strip() if len(lines) > 1 else ""
                full = sub.strip()
                if not body:
                    continue  # empty section
                rules.append(Rule(
                    index=idx,
                    heading=heading,
                    body=body,
                    full_text=full,
                ))
                idx += 1

        # Fallback: no sub-sections found
        if not rules:
            return [Rule(
                index=0,
                heading="Full Skill",
                body=skill_content.strip(),
                full_text=skill_content.strip(),
                is_core=False,
            )]

        # Step 3: classify core vs dynamic
        RuleMemory._classify_core(rules)

        return rules

    @staticmethod
    def _classify_core(rules: list[Rule]) -> None:
        """Set ``is_core`` on rules whose heading/body matches core keywords."""
        for rule in rules:
            combined = (rule.heading + " " + rule.body).lower()
            rule.is_core = any(kw in combined for kw in RuleMemory._CORE_KEYWORDS)

        # Fallback: if nothing classified as core, mark first 3 as core
        if not any(r.is_core for r in rules) and rules:
            for i in range(min(3, len(rules))):
                rules[i].is_core = True

    # ── Embeddings ────────────────────────────────────────────────────────

    def _build_embeddings(self) -> None:
        """Fit TF-IDF vectorizer on dynamic rules and build the rule matrix."""
        texts = [r.full_text for r in self._dynamic_rules]
        self._vectorizer = TfidfVectorizer(
            max_features=2048,
            ngram_range=(1, 2),
            stop_words="english",
        )
        self._rule_matrix = self._vectorizer.fit_transform(texts)
