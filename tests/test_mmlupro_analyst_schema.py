"""Unit tests for MMLU-Pro analyst output schema compatibility.

Ensures the analyst prompt's expected output format matches what reflect.py
actually parses.  Bug 2 (output protocol mismatch) cannot regress.
"""
from __future__ import annotations

import json
import re

import pytest

from skillopt.prompts import load_prompt
from skillopt.utils import extract_json


# ── Helper: simulate what reflect.py does ──────────────────────────────────

def _simulate_reflect_parse(response_text: str) -> dict | None:
    """Replicate the exact parsing logic from reflect.py:run_error_analyst_minibatch."""
    result = extract_json(response_text)
    if not result:
        return None
    if "patch" in result:
        return result
    return None


# ── Good outputs (match the prompt schema) ─────────────────────────────────

GOOD_ERROR_RESPONSE = """
{
  "batch_size": 4,
  "failure_summary": [
    {"failure_type": "knowledge_gap", "count": 4, "description": "Missing legal doctrine"}
  ],
  "patch": {
    "reasoning": "All failures stem from lack of legal knowledge.",
    "edits": [
      {"op": "append", "content": "## Legal Reasoning\\n- For criminal law, check intent."},
      {"op": "insert_after", "target": "## Rules", "content": "- Verify jurisdiction"},
      {"op": "replace", "target": "old rule", "content": "corrected rule"},
      {"op": "delete", "target": "wrong statement"}
    ]
  }
}
"""

GOOD_SUCCESS_RESPONSE = """
{
  "batch_size": 3,
  "success_summary": [
    {"pattern": "Systematic elimination of distractors", "count": 3}
  ],
  "patch": {
    "reasoning": "Successes all use elimination strategy.",
    "edits": [
      {"op": "append", "content": "## Strategy\\n- Eliminate obviously wrong options first."}
    ]
  }
}
"""

# ── Bad outputs (the format that caused Bug 2) ─────────────────────────────

BAD_ARRAY_FORMAT = """
[
  {"op": "add", "content": "## Legal Reasoning\\nNew rule", "anchor": "## End", "rationale": "Missing domain knowledge"}
]
"""


class TestAnalystSchema:
    def test_good_error_response_has_patch_key(self):
        """The correct format must pass reflect.py parsing."""
        result = _simulate_reflect_parse(GOOD_ERROR_RESPONSE)
        assert result is not None, "Valid error response must be parsed"
        assert "patch" in result
        assert result["patch"]["reasoning"]

    def test_good_success_response_has_patch_key(self):
        result = _simulate_reflect_parse(GOOD_SUCCESS_RESPONSE)
        assert result is not None, "Valid success response must be parsed"
        assert "patch" in result

    def test_bad_array_format_is_rejected(self):
        """Regression test: the old JSON array format must NOT silently
        pass as valid (it was the root cause of Bug 2)."""
        result = _simulate_reflect_parse(BAD_ARRAY_FORMAT)
        assert result is None, (
            "JSON array format must be rejected! "
            "This is the Bug 2 regression check."
        )

    def test_empty_json_fails(self):
        assert _simulate_reflect_parse("{}") is None

    def test_patch_without_edits_still_valid(self):
        """A well-formed patch that deliberately has zero edits is valid."""
        resp = '{"batch_size":0,"failure_summary":[],"patch":{"reasoning":"no issues","edits":[]}}'
        result = _simulate_reflect_parse(resp)
        assert result is not None
        assert result["patch"]["edits"] == []


class TestPromptSchemaConsistency:
    """Verify that the analyst prompts describe the correct output format."""

    def test_error_prompt_mentions_patch_key(self):
        prompt = load_prompt("analyst_error", env="mmlupro")
        assert '"patch"' in prompt or '"patch":' in prompt, (
            "analyst_error.md must instruct the model to output a 'patch' key"
        )

    def test_success_prompt_mentions_patch_key(self):
        prompt = load_prompt("analyst_success", env="mmlupro")
        assert '"patch"' in prompt or '"patch":' in prompt, (
            "analyst_success.md must instruct the model to output a 'patch' key"
        )

    def test_neither_prompt_mentions_flat_array(self):
        """Neither prompt should describe the old array-only format (top-level
        JSON array as the entire response).  Patch-level ``"edits": [...]`` is
        fine — that's the correct SkillOpt format."""
        error = load_prompt("analyst_error", env="mmlupro")
        success = load_prompt("analyst_success", env="mmlupro")
        for name, text in [("analyst_error", error), ("analyst_success", success)]:
            stripped = text.strip()
            # The old Bug 2 format was a top-level JSON array: [{op, content, ...}]
            # The new correct format has "patch": {"edits": [{op, ...}]} — nested.
            # Only flag if the ENTIRE response example is an inline JSON array.
            assert not re.search(
                r'^\s*\[\s*\{\s*"op"\s*:', stripped, re.MULTILINE
            ), f"{name}.md STILL describes the old top-level array format! Bug 2 regression."


class TestSkillDeduplication:
    """Verify that _strip_skill_section removes skill content from prompts.

    Imported inline to avoid pulling in the openai dependency chain."""

    @staticmethod
    def _strip_skill_section(text):
        import re
        text = re.sub(r'\n*## Skill\n.*?(?=\n## |\Z)', '', text, flags=re.DOTALL)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def test_skill_block_removed(self):
        text = "You are answering a question.\n\n## Skill\nsecret skill\n\n## Answer Format\nOnly output: B"
        result = self._strip_skill_section(text)
        assert "## Answer Format" in result
        assert "secret skill" not in result
        assert "## Skill" not in result

    def test_skill_at_end(self):
        text = "Instructions\n\n## Skill\nonly skill here\n"
        result = self._strip_skill_section(text)
        assert "only skill here" not in result
        assert "Instructions" in result

    def test_no_skill_section_passthrough(self):
        text = "Just instructions, no skill section."
        result = self._strip_skill_section(text)
        assert result == text

    def test_current_skill_occurs_once_contract(self):
        """Document the contract: after dedup, analyst should see only one
        'Current Skill' and zero per-trajectory skill sections.
        This test documents the expected behaviour, not enforced by code."""
        # The contract:
        # - run_error_analyst_minibatch adds one '## Current Skill' header
        # - _strip_skill_section removes all per-trajectory '## Skill' blocks
        # - Therefore the skill should appear exactly once in the analyst input
        pass  # documented assertion, not runtime-checkable without full pipeline
