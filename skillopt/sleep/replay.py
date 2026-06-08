"""SkillOpt-Sleep — Stage 3: replay.

Re-run mined TaskRecords offline under a given (skill, memory) and score
them, producing the (hard, soft) signal SkillOpt's gate consumes.

Single-shot text replay by default. Tasks whose rule judge requires a tool
call (gbrain's `tool_called`) are run through the backend's real tool loop
(attempt_with_tools), so tool use is verified honestly rather than self-reported.
"""
from __future__ import annotations

from typing import List, Tuple

from skillopt.sleep.backend import Backend
from skillopt.sleep.types import ReplayResult, TaskRecord


def _required_tools(task: TaskRecord) -> List[str]:
    """Tool names a rule judge requires (op == 'tool_called')."""
    if task.reference_kind != "rule" or not task.judge:
        return []
    tools = []
    for c in task.judge.get("checks", []) or []:
        if isinstance(c, dict) and c.get("op") == "tool_called" and c.get("arg"):
            tools.append(str(c["arg"]))
    return tools


def replay_one(backend: Backend, task: TaskRecord, skill: str, memory: str) -> ReplayResult:
    tools = _required_tools(task)
    tools_called: List[str] = []
    if tools:
        response, tools_called = backend.attempt_with_tools(task, skill, memory, tools)
    else:
        response = backend.attempt(task, skill, memory)

    # rule judges may need the detected tool calls; score locally when possible
    if task.reference_kind == "rule" and task.judge:
        from skillopt.sleep.judges import score_rule_judge
        hard, soft, rationale = score_rule_judge(task.judge, response, tools_called)
    else:
        hard, soft, rationale = backend.judge(task, response)

    return ReplayResult(
        id=task.id,
        hard=float(hard),
        soft=float(soft),
        response=response,
        fail_reason="" if hard >= 1.0 else (rationale or "below threshold"),
        task_type=(task.tags[0] if task.tags else "task"),
        judge_rationale=rationale,
        tools_called=tools_called,
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
