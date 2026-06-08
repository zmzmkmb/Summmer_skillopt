"""SkillOpt-Sleep — Stage 4: consolidate (one SkillOpt epoch).

This is the core that makes nightly evolution *safe*: it proposes bounded
edits from replayed failures, applies them to a candidate skill/memory, then
**gates** the candidate on a held-out slice of the user's own tasks. Only a
candidate that strictly improves the held-out score is accepted — exactly the
SkillOpt validation gate, reused verbatim from ``skillopt.evaluation.gate``.

Reused from the main SkillOpt package (import-light, no `openai` needed):
  * skillopt.evaluation.gate.evaluate_gate / select_gate_score
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from skillopt.sleep.backend import Backend
from skillopt.sleep.memory import apply_edits
from skillopt.sleep.replay import aggregate_scores, replay_batch
from skillopt.sleep.types import EditRecord, ReplayResult, TaskRecord


# Reuse the real SkillOpt gate. This module imports cleanly without `openai`.
try:
    from skillopt.evaluation.gate import evaluate_gate, select_gate_score
    _HAVE_REPO_GATE = True
except Exception:  # pragma: no cover - fallback keeps engine standalone
    _HAVE_REPO_GATE = False

    def select_gate_score(hard, soft, metric="hard", mixed_weight=0.5):  # type: ignore
        if metric == "hard":
            return float(hard)
        if metric == "soft":
            return float(soft)
        w = max(0.0, min(1.0, float(mixed_weight)))
        return (1 - w) * float(hard) + w * float(soft)


@dataclass
class ConsolidationResult:
    accepted: bool
    gate_action: str
    baseline_score: float
    candidate_score: float
    new_skill: str
    new_memory: str
    applied_edits: List[EditRecord]
    rejected_edits: List[EditRecord]
    holdout_baseline: float
    holdout_candidate: float


def _split(tasks: List[TaskRecord]) -> Tuple[List[TaskRecord], List[TaskRecord]]:
    replay = [t for t in tasks if t.split == "replay"]
    holdout = [t for t in tasks if t.split == "holdout"]
    # be robust if a split is empty
    if not replay:
        replay = tasks
    if not holdout:
        holdout = tasks
    return replay, holdout


def consolidate(
    backend: Backend,
    tasks: List[TaskRecord],
    skill: str,
    memory: str,
    *,
    edit_budget: int = 4,
    gate_metric: str = "mixed",
    gate_mixed_weight: float = 0.5,
    evolve_skill: bool = True,
    evolve_memory: bool = True,
    night: int = 1,
) -> ConsolidationResult:
    """Run one consolidation epoch: reflect -> bounded edit -> gate.

    Skill and memory are evolved in sequence (skill first if both enabled),
    each behind the same held-out gate, so each document only changes when it
    demonstrably helps on the user's held-out tasks.
    """
    replay_tasks, holdout_tasks = _split(tasks)

    # ── baseline on held-out slice (the gate reference) ──────────────────
    base_pairs = replay_batch(backend, holdout_tasks, skill, memory)
    base_hard, base_soft = aggregate_scores(base_pairs)
    base_score = select_gate_score(base_hard, base_soft, gate_metric, gate_mixed_weight)

    # ── reflect over replay-split failures/successes ─────────────────────
    train_pairs = replay_batch(backend, replay_tasks, skill, memory)
    failures = [(t, r) for (t, r) in train_pairs if r.hard < 1.0]
    successes = [(t, r) for (t, r) in train_pairs if r.hard >= 1.0]

    cand_skill, cand_memory = skill, memory
    all_applied: List[EditRecord] = []
    all_rejected: List[EditRecord] = []

    def _gate_apply(doc: str, edits: List[EditRecord], which: str) -> str:
        nonlocal cand_skill, cand_memory, base_score, all_applied, all_rejected
        if not edits:
            return doc
        new_doc, applied = apply_edits(doc, edits)
        if not applied:
            return doc
        # evaluate candidate on the held-out slice
        trial_skill = new_doc if which == "skill" else cand_skill
        trial_memory = new_doc if which == "memory" else cand_memory
        pairs = replay_batch(backend, holdout_tasks, trial_skill, trial_memory)
        h, s = aggregate_scores(pairs)
        cand_score = select_gate_score(h, s, gate_metric, gate_mixed_weight)
        if cand_score > base_score:
            base_score = cand_score
            all_applied.extend(applied)
            return new_doc
        all_rejected.extend(applied)
        return doc

    if evolve_skill:
        edits = backend.reflect(
            failures, successes, cand_skill, cand_memory,
            edit_budget=edit_budget, evolve_skill=True, evolve_memory=False,
        )
        cand_skill = _gate_apply(cand_skill, edits, "skill")

    if evolve_memory:
        # re-evaluate failures under the (possibly improved) skill
        train_pairs2 = replay_batch(backend, replay_tasks, cand_skill, cand_memory)
        failures2 = [(t, r) for (t, r) in train_pairs2 if r.hard < 1.0]
        successes2 = [(t, r) for (t, r) in train_pairs2 if r.hard >= 1.0]
        edits_m = backend.reflect(
            failures2, successes2, cand_skill, cand_memory,
            edit_budget=edit_budget, evolve_skill=False, evolve_memory=True,
        )
        cand_memory = _gate_apply(cand_memory, edits_m, "memory")

    # ── final gate decision (use the repo gate for the canonical action) ──
    final_pairs = replay_batch(backend, holdout_tasks, cand_skill, cand_memory)
    final_hard, final_soft = aggregate_scores(final_pairs)
    final_score = select_gate_score(final_hard, final_soft, gate_metric, gate_mixed_weight)

    if _HAVE_REPO_GATE:
        gate = evaluate_gate(
            candidate_skill=cand_skill,
            cand_hard=final_hard,
            current_skill=skill,
            current_score=select_gate_score(base_hard, base_soft, gate_metric, gate_mixed_weight),
            best_skill=skill,
            best_score=select_gate_score(base_hard, base_soft, gate_metric, gate_mixed_weight),
            best_step=night - 1,
            global_step=night,
            cand_soft=final_soft,
            metric=gate_metric,
            mixed_weight=gate_mixed_weight,
        )
        action = gate.action
    else:
        action = "accept" if final_score > base_soft else "reject"

    accepted = bool(all_applied) and final_score > select_gate_score(
        base_hard, base_soft, gate_metric, gate_mixed_weight
    )

    return ConsolidationResult(
        accepted=accepted,
        gate_action=action,
        baseline_score=select_gate_score(base_hard, base_soft, gate_metric, gate_mixed_weight),
        candidate_score=final_score,
        new_skill=cand_skill if accepted else skill,
        new_memory=cand_memory if accepted else memory,
        applied_edits=all_applied,
        rejected_edits=all_rejected,
        holdout_baseline=base_hard,
        holdout_candidate=final_hard,
    )
