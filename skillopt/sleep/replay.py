"""SkillOpt-Sleep — Stage 3: replay.

Re-run mined TaskRecords offline under a given (skill, memory) and score
them, producing the (hard, soft) signal SkillOpt's gate consumes.

For Phase 1 the replay is "mock mode": a sandboxed single-shot attempt via
the chosen backend (MockBackend = deterministic; AnthropicBackend = real).
"fresh" worktree replay is Phase 3 and is intentionally not wired here.
"""
from __future__ import annotations

from typing import List, Tuple

from skillopt.sleep.backend import Backend
from skillopt.sleep.types import ReplayResult, TaskRecord


def replay_one(backend: Backend, task: TaskRecord, skill: str, memory: str) -> ReplayResult:
    response = backend.attempt(task, skill, memory)
    hard, soft, rationale = backend.judge(task, response)
    return ReplayResult(
        id=task.id,
        hard=float(hard),
        soft=float(soft),
        response=response,
        fail_reason="" if hard >= 1.0 else (rationale or "below threshold"),
        task_type=(task.tags[0] if task.tags else "task"),
        judge_rationale=rationale,
    )


def replay_batch(
    backend: Backend,
    tasks: List[TaskRecord],
    skill: str,
    memory: str,
) -> List[Tuple[TaskRecord, ReplayResult]]:
    return [(t, replay_one(backend, t, skill, memory)) for t in tasks]


def aggregate_scores(pairs: List[Tuple[TaskRecord, ReplayResult]]) -> Tuple[float, float]:
    if not pairs:
        return 0.0, 0.0
    hard = sum(r.hard for _t, r in pairs) / len(pairs)
    soft = sum(r.soft for _t, r in pairs) / len(pairs)
    return hard, soft
