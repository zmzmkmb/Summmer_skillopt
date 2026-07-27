"""MMLU-Pro task dataloader with schema validation."""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

from skillopt.datasets.base import SPLIT_NAMES, SplitDataLoader

_VALID_OPTIONS = frozenset({chr(c) for c in range(ord("A"), ord("K"))})  # A-J


class MMLUProDataLoader(SplitDataLoader):
    """Loads MMLU-Pro data from split_dir with startup schema validation.

    On :meth:`setup`, validates:
    - ``id`` uniqueness within each split
    - ``question`` is non-empty
    - ``answers[0]`` is a valid A-J letter
    - No item overlap between train/val/test

    Items with a non-letter ``answers[0]`` (e.g. full text answer from
    some official splits) are auto-normalised: the letter key from the
    first answer option is extracted and used as the gold label.
    """

    def load_split_items(self, split_path: str) -> list[dict]:
        items = super().load_split_items(split_path)

        seen_ids: set[str] = set()
        invalid_questions: list[str] = []
        bad_answers: list[str] = []
        cleaned: list[dict] = []

        for it in items:
            item_id = str(it.get("id", ""))
            if not item_id:
                raise ValueError(
                    f"MMLU-Pro item in {split_path} missing 'id' field"
                )
            if item_id in seen_ids:
                raise ValueError(
                    f"Duplicate MMLU-Pro item id '{item_id}' in {split_path}"
                )
            seen_ids.add(item_id)

            question = str(it.get("question", "")).strip()
            if not question:
                invalid_questions.append(item_id)
                continue

            raw_answers = it.get("answers", [])
            if not raw_answers or not str(raw_answers[0]).strip():
                bad_answers.append(item_id)
                continue

            # Normalise: if answers[0] is not a single A-J letter, try to
            # extract the letter from the answer string
            first = str(raw_answers[0]).strip().upper()
            if first not in _VALID_OPTIONS:
                # Some MMLU-Pro splits use full answer text — extract letter
                letters = [c for c in first if c in _VALID_OPTIONS]
                if not letters:
                    bad_answers.append(
                        f"{item_id}: answers[0]={raw_answers[0]!r} (no A-J letter found)"
                    )
                    continue
                # Use the first A-J letter found
                it = dict(it)
                it["answers"] = [letters[0]]
                cleaned.append(it)
            else:
                cleaned.append(it)

        name = os.path.basename(split_path)
        if invalid_questions:
            raise ValueError(
                f"MMLU-Pro {name}: {len(invalid_questions)} items have empty 'question' field. "
                f"First: {invalid_questions[:3]}"
            )
        if bad_answers:
            raise ValueError(
                f"MMLU-Pro {name}: {len(bad_answers)} items have invalid 'answers' field. "
                f"First: {bad_answers[:3]}"
            )

        return cleaned

    def _validate_no_overlap(self) -> None:
        """Check that train/val/test item IDs do not overlap."""
        sets: dict[str, set[str]] = {}
        for split_name in SPLIT_NAMES:
            items = self._splits.get(split_name, [])
            sets[split_name] = {str(it["id"]) for it in items}

        for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
            overlap = sets[a] & sets[b]
            if overlap:
                raise ValueError(
                    f"MMLU-Pro: {a} and {b} share {len(overlap)} item IDs. "
                    f"First: {sorted(overlap)[:5]}"
                )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self._validate_no_overlap()

        # Print summary for logging
        counts = {k: len(v) for k, v in self._splits.items()}
        print(
            f"  [MMLUProDataLoader] validated: "
            + " ".join(f"{k}={v}" for k, v in counts.items())
            + f" (from {self.split_dir})"
        )
