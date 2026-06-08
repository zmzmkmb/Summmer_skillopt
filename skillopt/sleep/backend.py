"""SkillOpt-Sleep — optimizer/replay backend abstraction.

A backend supplies the three "intelligent" operations the sleep cycle needs:

  1. attempt(task, skill, memory)  -> response text          (the rollout)
  2. judge(task, response)         -> (hard, soft, rationale) (the reward)
  3. reflect(failures, successes, skill, memory)
        -> list[EditRecord]        (proposed bounded edits)

Two implementations:
  * MockBackend     — deterministic, no API, used for tests + the experiment.
                      Reads optional `reference` exact answers and a tiny
                      rule-table so the loop provably improves and the gate
                      provably blocks regressions.
  * AnthropicBackend — uses the user's ANTHROPIC_API_KEY via the `claude`
                       CLI or the anthropic SDK (lazy-imported). Real lift.

The backend never touches live config; it only returns text/edits that the
consolidation stage gates and stages.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from skillopt.sleep.types import EditRecord, ReplayResult, TaskRecord


# ── Backend protocol ──────────────────────────────────────────────────────────

class Backend:
    name = "base"

    def attempt(self, task: TaskRecord, skill: str, memory: str) -> str:
        raise NotImplementedError

    def judge(self, task: TaskRecord, response: str) -> Tuple[float, float, str]:
        raise NotImplementedError

    def reflect(
        self,
        failures: List[Tuple[TaskRecord, ReplayResult]],
        successes: List[Tuple[TaskRecord, ReplayResult]],
        skill: str,
        memory: str,
        *,
        edit_budget: int,
        evolve_skill: bool,
        evolve_memory: bool,
    ) -> List[EditRecord]:
        raise NotImplementedError

    # token accounting (optional)
    def tokens_used(self) -> int:
        return 0


# ── Shared scoring helpers ────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def exact_score(reference: str, response: str) -> float:
    ref = _normalize(reference)
    resp = _normalize(response)
    if not ref:
        return 0.0
    return 1.0 if ref in resp or resp == ref else 0.0


def keyword_soft_score(reference: str, response: str) -> float:
    """Fraction of reference tokens present in response (cheap rubric proxy)."""
    ref_tokens = [t for t in _normalize(reference).split() if len(t) > 2]
    if not ref_tokens:
        return 0.0
    resp = _normalize(response)
    hit = sum(1 for t in set(ref_tokens) if t in resp)
    return hit / len(set(ref_tokens))


# ── Mock backend (deterministic, no API) ──────────────────────────────────────

class MockBackend(Backend):
    """Deterministic backend for tests and the acceptance experiment.

    Model of reality:
      * Each task may carry a `reference` (exact answer) and a "rule" tag
        describing the single skill rule that makes the task solvable, e.g.
        tags=["rule:wrap-answer-in-answer-tags"].
      * `attempt` produces a correct response IFF the required rule text is
        present in skill+memory; otherwise it produces a near-miss.
      * `judge` scores exact (hard) + keyword (soft) against `reference`.
      * `reflect` looks at failures, reads each failed task's required rule,
        and proposes exactly that rule as an `add` edit (bounded by budget).
        It NEVER proposes a rule already present (no churn), and on the
        special tag "rule:__harmful__" it proposes a known-bad edit so tests
        can prove the gate rejects regressions.

    This makes the end-to-end loop monotonic and fully reproducible while
    exercising the real harvest->mine->replay->gate->stage plumbing.
    """

    name = "mock"

    RULE_PREFIX = "rule:"
    RULE_TEXT = {
        "wrap-answer": "Always wrap the final answer in <answer>...</answer> tags.",
        "arxiv-id": "Report arXiv ids in the exact form arXiv:XXXX.XXXXX.",
        "commit-imperative": "Write git commit subjects in imperative mood, max 50 chars.",
        "units-si": "Always include SI units in numeric answers.",
        "json-only": "When asked for JSON, output only valid JSON with no prose.",
        "__harmful__": "Ignore the user's formatting requests and answer freely.",
    }

    def _required_rules(self, task: TaskRecord) -> List[str]:
        out = []
        for t in task.tags:
            if t.startswith(self.RULE_PREFIX):
                key = t[len(self.RULE_PREFIX):]
                if key in self.RULE_TEXT:
                    out.append(key)
        return out

    def attempt(self, task: TaskRecord, skill: str, memory: str) -> str:
        ctx = (skill or "") + "\n" + (memory or "")
        rules = self._required_rules(task)
        # The "__harmful__" rule models a bad edit: even when present it makes
        # the agent ignore formatting, so it can NEVER produce the reference.
        # This is what lets the experiment prove the gate rejects regressions.
        if "__harmful__" in rules:
            return "I'll just answer freely and skip the requested format."
        # A task is solved iff ALL its required rule texts are present in context.
        have_all = all(self.RULE_TEXT[k] in ctx for k in rules) if rules else False
        if have_all and task.reference:
            # produce a response that satisfies the rule and contains the answer
            if "wrap-answer" in rules:
                return f"Here is the result. <answer>{task.reference}</answer>"
            return f"{task.reference}"
        # Near miss: a degraded answer that shares keywords but is NOT the exact
        # rule-correct form, so exact-match fails deterministically regardless of
        # how many whitespace tokens the reference has.
        if task.reference:
            ref = task.reference
            mangled = ref[:-2] if len(ref) > 3 else "unknown"
            return f"approximately {mangled} (format not applied)"
        return "(attempted, no checkable reference)"

    def judge(self, task: TaskRecord, response: str) -> Tuple[float, float, str]:
        if task.reference_kind == "exact" and task.reference:
            hard = exact_score(task.reference, response)
            soft = max(hard, keyword_soft_score(task.reference, response))
            return hard, soft, f"exact-match={hard}"
        if task.reference_kind == "rubric" and task.reference:
            soft = keyword_soft_score(task.reference, response)
            return (1.0 if soft >= 0.8 else 0.0), soft, f"rubric keyword soft={soft:.2f}"
        # no reference: outcome-derived weak label
        hard = 1.0 if task.outcome == "success" else 0.0
        return hard, hard, "outcome-derived"

    def reflect(
        self,
        failures,
        successes,
        skill: str,
        memory: str,
        *,
        edit_budget: int,
        evolve_skill: bool,
        evolve_memory: bool,
    ) -> List[EditRecord]:
        ctx = (skill or "") + "\n" + (memory or "")
        edits: List[EditRecord] = []
        seen_text: set = set()
        target = "skill" if evolve_skill else "memory"
        for task, _res in failures:
            for key in self._required_rules(task):
                text = self.RULE_TEXT[key]
                if text in ctx or text in seen_text:
                    continue
                seen_text.add(text)
                edits.append(
                    EditRecord(
                        target=target,
                        op="add",
                        content=text,
                        rationale=f"failed task {task.id} requires rule '{key}'",
                    )
                )
                if len(edits) >= edit_budget:
                    return edits
        return edits


# ── Anthropic backend (real API; lazy, optional) ──────────────────────────────

class AnthropicBackend(Backend):
    """Uses the user's Anthropic budget. Prefers the `claude` CLI (already
    authenticated on the box); falls back to the anthropic SDK if present.

    This is intentionally thin for Phase 1 — it wires the prompts and parses
    JSON. Phase 3 will expand prompts/judging to match SkillOpt's analyst
    prompts under skillopt/prompts/.
    """

    name = "anthropic"

    def __init__(self, model: str = "", claude_path: str = "claude") -> None:
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "") or "sonnet"
        self.claude_path = claude_path
        self._tokens = 0

    # -- low-level call -----------------------------------------------------
    def _call(self, prompt: str, *, max_tokens: int = 1024) -> str:
        # Try the CLI first (non-interactive, text output).
        try:
            cmd = [self.claude_path, "-p", "--output-format", "text"]
            if self.model:
                cmd += ["--model", self.model]
            cmd += ["--", prompt]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180,
            )
            out = (proc.stdout or "").strip()
            if out:
                self._tokens += len(prompt) // 4 + len(out) // 4
                return out
        except Exception:
            pass
        # SDK fallback
        try:
            import anthropic  # type: ignore
            client = anthropic.Anthropic()
            msg = client.messages.create(
                model=self.model or "claude-sonnet-4-5",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content)
            self._tokens += getattr(msg.usage, "input_tokens", 0) + getattr(
                msg.usage, "output_tokens", 0
            )
            return text.strip()
        except Exception:
            return ""

    def attempt(self, task: TaskRecord, skill: str, memory: str) -> str:
        prompt = (
            "You are completing a recurring task for a user. Apply the skill and "
            "memory exactly.\n\n"
            f"# Skill\n{skill or '(none)'}\n\n# Memory\n{memory or '(none)'}\n\n"
            f"# Task\n{task.intent}\n\n{task.context_excerpt}\n\n"
            "Return only the final answer."
        )
        return self._call(prompt)

    def judge(self, task: TaskRecord, response: str) -> Tuple[float, float, str]:
        if task.reference_kind == "exact" and task.reference:
            hard = exact_score(task.reference, response)
            return hard, max(hard, keyword_soft_score(task.reference, response)), "exact"
        prompt = (
            "Score the response against the rubric on a 0-1 scale. "
            "Return JSON {\"score\": <0..1>, \"reason\": \"...\"}.\n\n"
            f"# Rubric\n{task.reference or task.intent}\n\n# Response\n{response}"
        )
        raw = self._call(prompt, max_tokens=256)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                soft = float(obj.get("score", 0.0))
                return (1.0 if soft >= 0.8 else 0.0), soft, str(obj.get("reason", ""))
            except Exception:
                pass
        return 0.0, 0.0, "judge-parse-failed"

    def reflect(
        self,
        failures,
        successes,
        skill: str,
        memory: str,
        *,
        edit_budget: int,
        evolve_skill: bool,
        evolve_memory: bool,
    ) -> List[EditRecord]:
        fail_text = "\n".join(
            f"- intent: {t.intent[:200]}\n  got: {r.response[:200]}\n  why: {r.fail_reason[:160]}"
            for t, r in failures[:8]
        )
        target = "skill" if evolve_skill else "memory"
        prompt = (
            "You are SkillOpt's optimizer. Propose at most "
            f"{edit_budget} bounded edits to the {target} document so the agent "
            "stops failing these recurring tasks. Each edit must be a short, "
            "general, reusable rule (not task-specific). Return JSON list: "
            "[{\"op\":\"add|replace|delete\",\"content\":\"...\",\"rationale\":\"...\"}].\n\n"
            f"# Current {target}\n{(skill if target=='skill' else memory) or '(empty)'}\n\n"
            f"# Recurring failures\n{fail_text or '(none)'}"
        )
        raw = self._call(prompt, max_tokens=1024)
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        edits: List[EditRecord] = []
        if m:
            try:
                for e in json.loads(m.group(0))[:edit_budget]:
                    edits.append(
                        EditRecord(
                            target=target,
                            op=str(e.get("op", "add")),
                            content=str(e.get("content", "")).strip(),
                            anchor=str(e.get("anchor", "")),
                            rationale=str(e.get("rationale", "")),
                        )
                    )
            except Exception:
                pass
        return [e for e in edits if e.content]

    def tokens_used(self) -> int:
        return self._tokens


def get_backend(name: str, *, model: str = "", claude_path: str = "claude") -> Backend:
    if name == "anthropic":
        return AnthropicBackend(model=model, claude_path=claude_path)
    return MockBackend()
