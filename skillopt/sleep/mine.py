"""SkillOpt-Sleep — Stage 2: mine.

Turn :class:`SessionDigest` objects into :class:`TaskRecord` training units.

Two miners:
  * heuristic_mine  — deterministic, no API. Detects retry chains (a prompt
    re-asked after negative feedback => the early attempt failed), extracts
    the user's recurring intents, and labels outcomes from feedback signals.
  * llm_mine        — optional; uses an optimizer backend to produce richer
    TaskRecords with checkable references. Falls back to heuristic on error.

The heuristic miner is what makes the whole cycle runnable offline and is the
basis of the deterministic experiment.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, List, Optional

from skillopt.sleep.types import SessionDigest, TaskRecord


def _tid(project: str, intent: str) -> str:
    h = hashlib.sha256((project + "::" + intent).encode("utf-8")).hexdigest()[:12]
    return "task_" + h


def _short(text: str, n: int = 600) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + " …"


def _looks_negative(signals: List[str]) -> bool:
    return any(s.startswith("neg:") for s in signals)


def _looks_positive(signals: List[str]) -> bool:
    return any(s.startswith("pos:") for s in signals)


def heuristic_mine(
    digests: List[SessionDigest],
    *,
    max_tasks: int = 40,
) -> List[TaskRecord]:
    """Deterministic miner — no API calls.

    Strategy:
      * Each session with >=1 real user prompt yields one TaskRecord whose
        intent is the FIRST substantive prompt (the original ask).
      * Outcome is inferred:
          - negative feedback present and no later positive  -> "fail"
          - positive feedback present                         -> "success"
          - re-asks (multiple user turns) without resolution  -> "mixed"
          - otherwise                                         -> "unknown"
      * attempted_solution = the last assistant final (what was produced).
      * reference_kind defaults to "none"; the consolidation step will use a
        rubric judge for these. (Exact refs are added by the experiment data
        or by the LLM miner when it can derive a checkable answer.)
    """
    tasks: List[TaskRecord] = []
    for d in digests:
        if not d.user_prompts:
            continue
        intent = d.user_prompts[0]
        if len(intent.strip()) < 8:
            continue
        if _looks_positive(d.feedback_signals) and not _looks_negative(d.feedback_signals):
            outcome = "success"
        elif _looks_negative(d.feedback_signals):
            outcome = "fail"
        elif d.n_user_turns >= 3:
            outcome = "mixed"
        else:
            outcome = "unknown"

        attempted = d.assistant_finals[-1] if d.assistant_finals else ""
        context = ""
        if len(d.user_prompts) > 1:
            # later prompts often carry the corrective detail / real constraints
            context = "Follow-up constraints from the same session:\n- " + "\n- ".join(
                _short(p, 200) for p in d.user_prompts[1:4]
            )
        tags = []
        if d.tools_used:
            tags.append("tools:" + "+".join(d.tools_used[:4]))
        if d.git_branch:
            tags.append("branch:" + d.git_branch)

        tasks.append(
            TaskRecord(
                id=_tid(d.project, intent),
                project=d.project,
                intent=_short(intent, 800),
                context_excerpt=_short(context, 600),
                attempted_solution=_short(attempted, 600),
                outcome=outcome,
                reference_kind="none",
                reference="",
                tags=tags,
                source_sessions=[d.session_id],
            )
        )
        if len(tasks) >= max_tasks:
            break
    return tasks


def dedup_tasks(tasks: List[TaskRecord]) -> List[TaskRecord]:
    """Merge tasks sharing an id (same project+intent across sessions)."""
    by_id: dict = {}
    for t in tasks:
        if t.id in by_id:
            ex = by_id[t.id]
            ex.source_sessions = list(dict.fromkeys(ex.source_sessions + t.source_sessions))
            # prefer a resolved outcome if either session resolved it
            order = {"success": 3, "fail": 2, "mixed": 1, "unknown": 0}
            if order.get(t.outcome, 0) > order.get(ex.outcome, 0):
                ex.outcome = t.outcome
        else:
            by_id[t.id] = t
    return list(by_id.values())


def assign_splits(
    tasks: List[TaskRecord],
    *,
    holdout_fraction: float = 0.34,
    seed: int = 42,
) -> List[TaskRecord]:
    """Deterministically split tasks into replay (train) / holdout (test).

    Uses a stable hash of the task id so the same task always lands in the
    same split across nights (a fixed held-out gate, like SkillOpt's D_sel).
    """
    for t in tasks:
        bucket = int(hashlib.sha256((str(seed) + t.id).encode()).hexdigest(), 16) % 100
        t.split = "holdout" if bucket < int(holdout_fraction * 100) else "replay"
    # guarantee both splits non-empty when possible
    splits = {t.split for t in tasks}
    if len(tasks) >= 2 and "holdout" not in splits:
        tasks[-1].split = "holdout"
    if len(tasks) >= 2 and "replay" not in splits:
        tasks[0].split = "replay"
    return tasks


def mine(
    digests: List[SessionDigest],
    *,
    max_tasks: int = 40,
    holdout_fraction: float = 0.34,
    seed: int = 42,
    llm_miner: Optional[Callable[[List[SessionDigest]], List[TaskRecord]]] = None,
) -> List[TaskRecord]:
    """Top-level miner. Uses ``llm_miner`` if provided, else heuristic."""
    tasks: List[TaskRecord] = []
    if llm_miner is not None:
        try:
            tasks = llm_miner(digests) or []
        except Exception:
            tasks = []
    if not tasks:
        tasks = heuristic_mine(digests, max_tasks=max_tasks)
    tasks = dedup_tasks(tasks)
    tasks = assign_splits(tasks, holdout_fraction=holdout_fraction, seed=seed)
    return tasks
