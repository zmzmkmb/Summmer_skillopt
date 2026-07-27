"""MMLU-Pro rollout — minimalist multiple-choice agent.

The system prompt constrains only the output FORMAT, not the reasoning strategy.
All reasoning and problem-solving methods MUST come from the skill document.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from skillopt.envs.mmlupro.evaluator import evaluate
from skillopt.model import chat_target
from skillopt.prompts import load_prompt


def _build_system(skill_content: str) -> str:
    """Build system prompt: format instructions + skill."""
    if skill_content.strip():
        skill_section = f"## Skill\n{skill_content.strip()}\n\n"
    else:
        skill_section = ""
    return load_prompt("rollout_system", env="mmlupro").format(
        skill_section=skill_section
    )


def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
    max_completion_tokens: int = 16384,
) -> dict:
    item_id = str(item.get("id", ""))
    question = item.get("question", "")
    gold_answers = item.get("answers", [])

    result = {
        "id": item_id,
        "em": 0.0, "f1": 0.0, "hard": 0, "soft": 0.0,
        "predicted_answer": "", "gold_answers": gold_answers,
        "response": "", "fail_reason": "", "agent_ok": False,
    }

    system = _build_system(skill_content)
    user = question  # MMLU-Pro items already have choices embedded in the question string

    try:
        response = ""
        for turn in range(max_turns):
            resp_text, _ = chat_target(
                system=system, user=user,
                max_completion_tokens=max_completion_tokens,
                retries=3, stage="rollout",
                timeout=exec_timeout,
            )
            response = resp_text
        result["response"] = response
        result["agent_ok"] = True

        pred_dir = os.path.join(out_root, "predictions", item_id)
        os.makedirs(pred_dir, exist_ok=True)
        with open(os.path.join(pred_dir, "conversation.json"), "w", encoding="utf-8") as f:
            json.dump([{"type": "message", "content": response}], f, ensure_ascii=False)

        eval_result = evaluate(response, gold_answers)
        result["em"] = eval_result["em"]
        result["f1"] = eval_result["f1"]
        result["predicted_answer"] = eval_result["predicted_answer"]
        result["hard"] = int(eval_result["em"])
        result["soft"] = float(eval_result["f1"])
    except Exception as exc:
        result["fail_reason"] = f"{type(exc).__name__}: {exc}"

    return result


def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 120,
    workers: int = 64,
    max_completion_tokens: int = 16384,
    task_timeout: int = 600,
) -> list[dict]:
    os.makedirs(out_root, exist_ok=True)
    results_path = os.path.join(out_root, "results.jsonl")

    done_ids: set[str] = set()
    existing: list[dict] = []
    if os.path.exists(results_path):
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done_ids.add(str(r["id"]))
                    existing.append(r)
                except Exception:
                    pass

    pending = [it for it in items if str(it["id"]) not in done_ids]
    if not pending:
        return existing

    def _run_one(it):
        return process_one(it, out_root, skill_content, max_turns,
                          exec_timeout, max_completion_tokens)

    results = list(existing)
    with open(results_path, "a", encoding="utf-8") as outf:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_run_one, it): it for it in pending}
            pending_futs = set(futs)
            while pending_futs:
                done, _ = wait(pending_futs, timeout=5, return_when=FIRST_COMPLETED)
                for fut in done:
                    r = fut.result()
                    results.append(r)
                    outf.write(json.dumps(r, ensure_ascii=False) + "\n")
                    outf.flush()
                    pending_futs.discard(fut)

    return results
