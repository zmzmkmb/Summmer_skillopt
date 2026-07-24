"""Validation gate — accept / reject candidate skills.

Analogous to validation-based early stopping and model selection in neural
network training: compares the candidate's score against the current and
best scores, then returns an accept/reject decision.

The trainer owns side-effects (cache lookup, rollout, printing, state
mutation).  This module is the pure decision function.

Metric selection
----------------
Three gate metrics are supported:

* ``"hard"`` (default, backward-compatible):
  Compare candidate vs current/best using *hard* exact-match accuracy.
* ``"soft"``:
  Compare using *soft* per-item score (F1 / partial credit / etc.).
  Use this when a small held-out selection set has too few items for
  hard accuracy to be sensitive to incremental skill improvements.
* ``"mixed"``:
  Compare using a weighted average ``(1 - w) * hard + w * soft``.
  ``w`` is configurable via ``mixed_weight`` (default ``0.5``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GateAction = Literal["accept_new_best", "accept", "reject", "annealing_accept"]
GateMetric = Literal["hard", "soft", "mixed"]


@dataclass(frozen=True)
class GateResult:
    """Immutable outcome of the validation gate."""

    action: GateAction
    current_skill: str
    current_score: float
    best_skill: str
    best_score: float
    best_step: int


def compute_semantic_density(
    skill_content: str,
    leading_words: list[str] | None = None,
) -> float:
    """Compute the semantic density of leading words in a skill document."""
    if not skill_content or not skill_content.strip():
        return 0.0
    if leading_words is None:
        leading_words = [
            "MUST", "ALWAYS", "NEVER", "ONLY", "CRITICAL", "IMPORTANT",
            "RESOLVE", "PREFER", "ENSURE", "STRICT", "VERIFY"
        ]
    
    # Strip metadata comments to focus purely on instruction text
    skill = skill_content
    for start, end in [
        ("<!-- SLOW_UPDATE_START -->", "<!-- SLOW_UPDATE_END -->"),
        ("<!-- APPENDIX_START -->", "<!-- APPENDIX_END -->")
    ]:
        while True:
            s_idx = skill.find(start)
            if s_idx == -1:
                break
            e_idx = skill.find(end, s_idx)
            if e_idx == -1:
                skill = skill[:s_idx] + skill[s_idx + len(start):]
                break
            skill = skill[:s_idx] + skill[e_idx + len(end):]

    import re
    words = re.findall(r'[a-zA-Z0-9]+', skill.lower())
    if not words:
        return 0.0
    
    leading_set = {w.lower() for w in leading_words}
    leading_count = sum(1 for w in words if w in leading_set)
    return leading_count / len(words)


def select_gate_score(
    hard: float,
    soft: float,
    metric: GateMetric = "hard",
    mixed_weight: float = 0.5,
    *,
    skill_content: str = "",
    use_semantic_density: bool = False,
    semantic_density_weight: float = 0.05,
    leading_words: list[str] | None = None,
) -> float:
    """Project (hard, soft) onto a single comparison metric.

    Parameters
    ----------
    hard, soft
        Aggregate hard / soft scores from a rollout batch (both 0..1).
    metric
        Which metric to compare on.
    mixed_weight
        For ``"mixed"``: weight given to ``soft``. Must be in ``[0, 1]``.
        Ignored for ``"hard"`` / ``"soft"``.
    skill_content
        The raw skill document content.
    use_semantic_density
        Whether to adjust the score based on semantic density of leading words.
    semantic_density_weight
        Scaling weight for the semantic density bonus.
    leading_words
        Optional custom list of high-influence words to prioritize.
    """
    if metric == "hard":
        score = float(hard)
    elif metric == "soft":
        score = float(soft)
    elif metric == "mixed":
        w = max(0.0, min(1.0, float(mixed_weight)))
        score = (1.0 - w) * float(hard) + w * float(soft)
    else:
        raise ValueError(
            f"unknown gate metric {metric!r}; expected 'hard', 'soft', or 'mixed'"
        )

    if use_semantic_density:
        density = compute_semantic_density(skill_content, leading_words)
        score += float(semantic_density_weight) * density

    return score


def evaluate_gate(
    candidate_skill: str,
    cand_hard: float,
    current_skill: str,
    current_score: float,
    best_skill: str,
    best_score: float,
    best_step: int,
    global_step: int,
    *,
    cand_soft: float = 0.0,
    metric: GateMetric = "hard",
    mixed_weight: float = 0.5,
    use_semantic_density: bool = False,
    semantic_density_weight: float = 0.05,
    leading_words: list[str] | None = None,
) -> GateResult:
    """Pure gate decision: compare candidate score to current/best.

    Parameters
    ----------
    candidate_skill
        The candidate skill content being evaluated.
    cand_hard, cand_soft
        Aggregate hard / soft scores of the candidate on the selection set.
    current_skill, current_score
        The currently-active skill and its *metric-space* score.
    best_skill, best_score, best_step
        The best-so-far skill, its *metric-space* score, and the step
        at which it was accepted.
    global_step
        Current global training step (recorded if a new best is accepted).
    cand_soft
        Soft score of the candidate; only consulted when ``metric != "hard"``.
        Defaults to ``0.0`` for backward compatibility with callers that
        previously passed only ``cand_hard``.
    metric
        Which metric to compare on. Defaults to ``"hard"`` to preserve
        the original gate behavior.
    mixed_weight
        Weight on ``soft`` when ``metric == "mixed"``.
    use_semantic_density
        Whether to adjust the score based on semantic density of leading words.
    semantic_density_weight
        Scaling weight for the semantic density bonus.
    leading_words
        Optional custom list of high-influence words to prioritize.

    Returns
    -------
    GateResult
        Updated state; the caller decides what to do with it (print,
        mutate trainer state, log, etc.).
    """
    cand_score = select_gate_score(
        cand_hard,
        cand_soft,
        metric,
        mixed_weight,
        skill_content=candidate_skill,
        use_semantic_density=use_semantic_density,
        semantic_density_weight=semantic_density_weight,
        leading_words=leading_words,
    )

    if cand_score > current_score:
        if cand_score > best_score:
            return GateResult(
                action="accept_new_best",
                current_skill=candidate_skill,
                current_score=cand_score,
                best_skill=candidate_skill,
                best_score=cand_score,
                best_step=global_step,
            )
        return GateResult(
            action="accept",
            current_skill=candidate_skill,
            current_score=cand_score,
            best_skill=best_skill,
            best_score=best_score,
            best_step=best_step,
        )
    return GateResult(
        action="reject",
        current_skill=current_skill,
        current_score=current_score,
        best_skill=best_skill,
        best_score=best_score,
        best_step=best_step,
    )


# ── Annealing temperature schedule ──────────────────────────────────────────

def compute_temperature(
    step: int,
    total_steps: int,
    T0: float = 0.02,
    cooling_rate: float = 0.92,
    T_min: float = 0.001,
) -> float:
    """Exponential cooling schedule for simulated annealing.

    Parameters
    ----------
    step
        Current step index (0-based).
    total_steps
        Total steps in the training run.
    T0
        Initial temperature. Units are in gate-score space (0..1).
        Default 0.02 ≈ 4 selection items out of 200.
    cooling_rate
        Per-step multiplicative decay. Lower = faster cooling.
        0.92 → T halves roughly every 8 steps.
    T_min
        Floor temperature. Annealing effectively off below this.
    """
    import math

    # Exponential decay with a minimum floor
    T = T0 * (cooling_rate ** step)

    # Linear ramp-down in the last 20% of steps to ensure near-zero at end
    warm_frac = 0.8
    if step >= warm_frac * total_steps and total_steps > 0:
        remaining = total_steps - int(warm_frac * total_steps)
        if remaining > 0:
            pos = step - int(warm_frac * total_steps)
            ramp = 1.0 - (pos / remaining)
            T = T * max(0.0, ramp)

    return max(T_min, T)


def _metropolis_accept(
    candidate_score: float,
    current_score: float,
    temperature: float,
) -> bool:
    """Metropolis criterion: accept a worse candidate with probability.

    p = exp((candidate - current) / T)

    Returns True if the worse candidate should be accepted.
    """
    import math
    import random

    if temperature <= 1e-9:
        return False
    delta = candidate_score - current_score  # negative
    p = math.exp(delta / temperature)
    return random.random() < p


# ── Gate with simulated annealing ──────────────────────────────────────────

def evaluate_gate_with_annealing(
    candidate_skill: str,
    cand_hard: float,
    current_skill: str,
    current_score: float,
    best_skill: str,
    best_score: float,
    best_step: int,
    global_step: int,
    temperature: float,
    *,
    cand_soft: float = 0.0,
    metric: GateMetric = "hard",
    mixed_weight: float = 0.5,
    use_semantic_density: bool = False,
    semantic_density_weight: float = 0.05,
    leading_words: list[str] | None = None,
) -> GateResult:
    """Gate decision with simulated annealing for exploration.

    Extends ``evaluate_gate`` with a Metropolis-criterion acceptance path:
    when ``candidate_score <= current_score`` but the gap is small relative
    to the current temperature, the candidate may still be accepted as the
    new *current* skill (but NOT as the new *best* skill).  This lets the
    optimizer escape local optima that the strict gate would trap it in.

    Key invariants
    --------------
    * ``best_skill`` / ``best_score`` are **never** updated on an
      annealing accept — only on genuine ``accept_new_best``.
    * ``current_skill`` / ``current_score`` are always kept in sync.
    * When temperature drops to zero the gate behaves identically to
      ``evaluate_gate``.

    Parameters are the same as ``evaluate_gate``, plus ``temperature``.
    """
    cand_score = select_gate_score(
        cand_hard,
        cand_soft,
        metric,
        mixed_weight,
        skill_content=candidate_skill,
        use_semantic_density=use_semantic_density,
        semantic_density_weight=semantic_density_weight,
        leading_words=leading_words,
    )

    # 1) Genuine improvement — same as strict gate
    if cand_score > current_score:
        if cand_score > best_score:
            return GateResult(
                action="accept_new_best",
                current_skill=candidate_skill,
                current_score=cand_score,
                best_skill=candidate_skill,
                best_score=cand_score,
                best_step=global_step,
            )
        return GateResult(
            action="accept",
            current_skill=candidate_skill,
            current_score=cand_score,
            best_skill=best_skill,
            best_score=best_score,
            best_step=best_step,
        )

    # 2) Not an improvement — try annealing
    if _metropolis_accept(cand_score, current_score, temperature):
        # Annealing accept: explore worse territory BUT keep best_skill safe
        return GateResult(
            action="annealing_accept",
            current_skill=candidate_skill,
            current_score=cand_score,
            best_skill=best_skill,
            best_score=best_score,
            best_step=best_step,
        )

    # 3) Reject
    return GateResult(
        action="reject",
        current_skill=current_skill,
        current_score=current_score,
        best_skill=best_skill,
        best_score=best_score,
        best_step=best_step,
    )
