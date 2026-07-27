"""Per-rule utility tracking with JSON persistence and stable rule IDs.

Accumulates selection and correctness counts across training steps,
persisting to ``{out_root}/moar_utility.json`` so utilities survive
process restarts and are available to subsequent training runs.

Uses ``rule_id + text_hash`` as stable identifiers so utilities are
not invalidated when the rule list is reordered or extended.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import numpy as np


def _hash_rule_text(text: str) -> str:
    """Stable 12-char hex hash of a rule's full text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _make_rule_id(index: int, heading: str) -> str:
    """Generate a stable rule_id from index and heading."""
    # e.g. "D00" for first dynamic rule
    return f"D{index:02d}"


@dataclass
class RuleStats:
    """Per-rule selection and correctness counters."""
    rule_id: str = ""
    text_hash: str = ""
    selected_count: int = 0
    correct_count: int = 0


class UtilityTracker:
    """Track per-rule historical utility with JSON persistence.

    Parameters
    ----------
    persistence_path : str | None
        JSON file path for save/load.  Auto-generated from out_root if omitted.
    decay : float
        Exponential decay factor applied to historical counts on load
        (1.0 = no decay, 0.95 = 5% decay per save cycle).
    min_count : int
        Minimum selections before a rule gets a non-zero utility
        (Laplace smoothing ensures cold-start rules get a prior).
    frozen : bool
        If True, ``record_selection`` is a no-op (test-set isolation).
    """

    def __init__(
        self,
        persistence_path: str | None = None,
        decay: float = 1.0,
        min_count: int = 2,
        frozen: bool = False,
    ) -> None:
        self._path = persistence_path
        self._decay = float(decay)
        self._min_count = int(min_count)
        self.frozen = frozen  # test-set isolation: no-op when True
        # Indexed by (text_hash → stats)
        self._stats: dict[str, RuleStats] = {}
        # Current rule mapping: list_index → text_hash
        self._rule_hashes: list[str] = []
        self._rule_ids: list[str] = []

        if self._path and os.path.exists(self._path):
            self.load()

    # ── Rule registration ──────────────────────────────────────────────

    def register_rules(self, rule_texts: list[str]) -> None:
        """Register the current rule set. Call when RuleMemory is initialised.

        Computes hashes and reconciles with previously-saved stats.
        """
        self._rule_hashes = []
        self._rule_ids = []
        for i, text in enumerate(rule_texts):
            h = _hash_rule_text(text)
            self._rule_hashes.append(h)
            self._rule_ids.append(_make_rule_id(i, text[:40].replace("\n", " ")))
            if h not in self._stats:
                self._stats[h] = RuleStats(
                    rule_id=self._rule_ids[-1],
                    text_hash=h,
                )

    @property
    def n_rules(self) -> int:
        return len(self._rule_hashes)

    # ── Recording ──────────────────────────────────────────────────────

    def record_selection(
        self,
        selected_indices: list[int],
        correct: bool,
    ) -> None:
        """Record that *selected_indices* were active for a query.

        No-op when ``frozen=True`` (test-set isolation).
        """
        if self.frozen:
            return
        for idx in selected_indices:
            if 0 <= idx < len(self._rule_hashes):
                h = self._rule_hashes[idx]
                self._stats[h].selected_count += 1
                if correct:
                    self._stats[h].correct_count += 1

    # ── Utility computation ────────────────────────────────────────────

    def compute_utilities(self, method: str = "precision") -> np.ndarray:
        """Compute a utility vector of shape ``(n_rules,)``.

        Parameters
        ----------
        method : str
            Scoring method: ``"precision"``, ``"laplace"``, or ``"idf"``.

        Returns
        -------
        np.ndarray
            Shape ``(n_rules,)`` — values in roughly [0, 1].
        """
        n = len(self._rule_hashes)
        if method == "laplace":
            return np.array([
                (self._stats[h].correct_count + 1.0) / max(
                    self._stats[h].selected_count + 2.0, 1.0)
                if h in self._stats else 0.5
                for h in self._rule_hashes
            ])
        elif method == "idf":
            import math
            total = max(
                max((s.selected_count for s in self._stats.values()), default=0),
                1,
            )
            util = np.zeros(n)
            for i, h in enumerate(self._rule_hashes):
                if h not in self._stats:
                    continue
                s = self._stats[h]
                freq = s.selected_count / total if total > 0 else 0.0
                idf = -math.log(max(freq, 0.02))
                util[i] = max(-0.5, min(1.0, idf / 3.0))
            return util
        else:  # "precision" (default)
            return np.array([
                (self._stats[h].correct_count / max(
                    self._stats[h].selected_count, 1))
                if h in self._stats
                and self._stats[h].selected_count >= self._min_count
                else 0.0
                for h in self._rule_hashes
            ])

    # ── Persistence ────────────────────────────────────────────────────

    def save(self) -> None:
        """Write current stats to JSON file (keyed by text_hash)."""
        if not self._path:
            return
        data = {
            "decay": self._decay,
            "min_count": self._min_count,
            "frozen": self.frozen,
            "rules": {
                h: {
                    "rule_id": s.rule_id,
                    "text_hash": s.text_hash,
                    "selected": s.selected_count,
                    "correct": s.correct_count,
                }
                for h, s in self._stats.items()
            },
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """Load stats from JSON file (keyed by text_hash, with optional decay)."""
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        rules_data = data.get("rules", {})
        decay_factor = float(data.get("decay", self._decay))

        for h, rd in rules_data.items():
            self._stats[h] = RuleStats(
                rule_id=str(rd.get("rule_id", "")),
                text_hash=str(rd.get("text_hash", h)),
                selected_count=int(float(rd.get("selected", 0)) * decay_factor),
                correct_count=int(float(rd.get("correct", 0)) * decay_factor),
            )

    def reset(self) -> None:
        """Clear all accumulated statistics."""
        self._stats.clear()
