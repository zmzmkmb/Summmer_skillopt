"""Per-rule utility tracking with JSON persistence.

Accumulates selection and correctness counts across training steps,
persisting to ``{out_root}/moar_utility.json`` so utilities survive
process restarts and are available to subsequent training runs.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np


@dataclass
class RuleStats:
    """Per-rule selection and correctness counters."""
    selected_count: int = 0
    correct_count: int = 0


class UtilityTracker:
    """Track per-rule historical utility with JSON persistence.

    Parameters
    ----------
    n_rules : int
        Number of dynamic rules being tracked.
    persistence_path : str | None
        JSON file path for save/load.  Auto-generated from out_root if omitted.
    decay : float
        Exponential decay factor applied to historical counts on load
        (1.0 = no decay, 0.95 = 5% decay per save cycle).
    min_count : int
        Minimum selections before a rule gets a non-zero utility
        (Laplace smoothing ensures cold-start rules get a prior).
    """

    def __init__(
        self,
        n_rules: int,
        persistence_path: str | None = None,
        decay: float = 1.0,
        min_count: int = 2,
    ) -> None:
        self.n_rules = n_rules
        self._path = persistence_path
        self._decay = float(decay)
        self._min_count = int(min_count)
        self._stats = [RuleStats() for _ in range(n_rules)]

        if self._path and os.path.exists(self._path):
            self.load()

    # ── Recording ─────────────────────────────────────────────────────────

    def record_selection(
        self,
        selected_indices: list[int],
        correct: bool,
    ) -> None:
        """Record that *selected_indices* were active for a query whose
        outcome was *correct* (True) or not (False).
        """
        for idx in selected_indices:
            if 0 <= idx < self.n_rules:
                self._stats[idx].selected_count += 1
                if correct:
                    self._stats[idx].correct_count += 1

    # ── Utility computation ───────────────────────────────────────────────

    def compute_utilities(self, method: str = "precision") -> np.ndarray:
        """Compute a utility vector of shape ``(n_rules,)``.

        Parameters
        ----------
        method : str
            Scoring method:
            - ``"precision"``: utility = correct / max(selected, 1)
            - ``"laplace"``: utility = (correct + 1) / (selected + 2)
            - ``"idf"``: IDF-style bonus as in rule_utility_rerank.py

        Returns
        -------
        np.ndarray
            Shape ``(n_rules,)`` — values in roughly [0, 1].
        """
        if method == "laplace":
            return np.array([
                (s.correct_count + 1.0) / max(s.selected_count + 2.0, 1.0)
                for s in self._stats
            ])
        elif method == "idf":
            import math
            total = max(max(s.selected_count for s in self._stats), 1)
            util = np.zeros(self.n_rules)
            for i, s in enumerate(self._stats):
                freq = s.selected_count / total if total > 0 else 0.0
                idf = -math.log(max(freq, 0.02))
                util[i] = max(-0.5, min(1.0, idf / 3.0))
            return util
        else:  # "precision" (default)
            return np.array([
                s.correct_count / max(s.selected_count, 1)
                if s.selected_count >= self._min_count else 0.0
                for s in self._stats
            ])

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self) -> None:
        """Write current stats to JSON file."""
        if not self._path:
            return
        data = {
            "n_rules": self.n_rules,
            "decay": self._decay,
            "min_count": self._min_count,
            "rules": [
                {"selected": s.selected_count, "correct": s.correct_count}
                for s in self._stats
            ],
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """Load stats from JSON file (with optional decay)."""
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        rules_data = data.get("rules", [])
        decay_factor = float(data.get("decay", self._decay))

        for i, rd in enumerate(rules_data):
            if i >= self.n_rules:
                break
            # Apply decay to historical counts
            self._stats[i].selected_count = int(
                float(rd.get("selected", 0)) * decay_factor
            )
            self._stats[i].correct_count = int(
                float(rd.get("correct", 0)) * decay_factor
            )

    def reset(self) -> None:
        """Clear all accumulated statistics."""
        self._stats = [RuleStats() for _ in range(self.n_rules)]
