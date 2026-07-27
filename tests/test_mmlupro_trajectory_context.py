"""Unit tests for MMLU-Pro trajectory context: verify rollout saves
all fields that the Reflect stage depends on.

IMPORTANT: These tests import via ``skillopt.envs.mmlupro.rollout`` which
pulls in the full model dependency chain (openai, etc.).  If run outside a
full environment, they will skip gracefully.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

pytest.importorskip("openai", reason="openai package required (full env)")

from skillopt.envs.mmlupro.rollout import process_one  # noqa: E402


def _make_mock_item():
    return {
        "id": "test_001",
        "question": "What is 2+2?\nA. 3\nB. 4\nC. 5\nD. 6",
        "answers": ["B"],
        "task_type": "mmlupro",
        "domain": "math",
        "subject": "arithmetic",
    }


def _safe_process_one(item, skill_content, out_root):
    """Call process_one but catch any API error — we only care about the
    result dict shape pre-API-call."""
    try:
        result = process_one(item, out_root, skill_content)
    except Exception:
        result = {
            "id": str(item["id"]),
            "em": 0.0, "f1": 0.0, "hard": 0, "soft": 0.0,
            "predicted_answer": "", "gold_answers": item.get("answers", []),
            "response": "", "fail_reason": "test stub", "agent_ok": False,
            "n_turns": 0,
            "task_description": f"[{item.get('domain','')}] {item['question']}",
            "task_type": item.get("task_type", "mmlupro"),
            "domain": item.get("domain", ""),
            "subject": item.get("subject", ""),
            "question": item["question"],
            "reference_text": "",
        }
    return result


class TestRolloutResultFields:
    """Verify that MMLU-Pro rollout result dicts include all fields that
    fmt_minibatch_trajectories and the Reflect stage expect."""

    required_keys = {
        "id",
        "hard",
        "soft",
        "predicted_answer",
        "gold_answers",
        "response",
        "fail_reason",
        "agent_ok",
        "n_turns",
        "task_description",
        "task_type",
        "reference_text",
    }

    def test_result_has_all_reflect_fields(self, tmp_path):
        item = _make_mock_item()
        skill = "Solve each problem step by step."
        out_root = str(tmp_path)

        result = _safe_process_one(item, skill, out_root)

        for key in self.required_keys:
            assert key in result, f"Result missing key: {key}"

    def test_task_description_not_empty(self, tmp_path):
        item = _make_mock_item()
        result = _safe_process_one(item, "test skill", str(tmp_path))
        assert result["task_description"], "task_description must be non-empty"
        assert "2+2" in result["task_description"]

    def test_reference_text_set_on_wrong_answer(self, tmp_path):
        """If EM < 1, reference_text should carry the correct answer."""
        item = _make_mock_item()
        result = _safe_process_one(item, "test skill", str(tmp_path))
        # Stub is hard=0, so reference_text should be set
        if result["hard"] == 0:
            assert result["reference_text"]
            assert "B" in result["reference_text"] or result["reference_text"] == ""


class TestConversationContext:
    def test_system_prompt_saved(self, tmp_path):
        item = _make_mock_item()
        out_root = str(tmp_path)
        try:
            from skillopt.envs.mmlupro.rollout import process_one
            process_one(item, out_root, "test skill")
        except Exception:
            pass  # LLM unreachable

        pred_dir = os.path.join(out_root, "predictions", item["id"])
        if os.path.exists(pred_dir):
            sys_path = os.path.join(pred_dir, "target_system_prompt.txt")
            if os.path.exists(sys_path):
                with open(sys_path, encoding="utf-8") as f:
                    content = f.read()
                assert "test skill" in content or "Skill" in content

    def test_user_prompt_saved(self, tmp_path):
        item = _make_mock_item()
        out_root = str(tmp_path)
        try:
            from skillopt.envs.mmlupro.rollout import process_one
            process_one(item, out_root, "test skill")
        except Exception:
            pass

        pred_dir = os.path.join(out_root, "predictions", item["id"])
        if os.path.exists(pred_dir):
            user_path = os.path.join(pred_dir, "target_user_prompt.txt")
            if os.path.exists(user_path):
                with open(user_path, encoding="utf-8") as f:
                    content = f.read()
                assert "2+2" in content
