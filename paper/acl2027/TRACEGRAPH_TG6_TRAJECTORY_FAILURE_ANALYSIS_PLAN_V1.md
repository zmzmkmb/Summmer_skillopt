# TraceGraph TG6 Trajectory Failure-Analysis Plan v1

Date: 2026-09-05

## Position in the paper

TG6 v4 established that the repair-v2 local environment and the observable
trace contract can execute end to end. It also produced 0/40 successes on the
frozen held-out set. Every episode reached 50 steps, abstention was 0/40, and
the recorded terminal actions contained only two distinct actions per episode,
often alternating between two locations.

This result is frozen evidence. It must not be used to tune a selector or to
choose held-out tasks. The next experiment isolates the cause of this failure
on a fresh development split.

## Research objective

Determine whether the TG6 v4 failure is primarily:

1. a local selector-order problem that creates repeated action-state cycles;
2. a missing trajectory-level progress controller; or
3. an information-sufficiency limit caused by removing task description and
   hidden goal information from runtime inputs.

The experiment is diagnostic and mechanistic. It does not assume that reducing
loops will improve task success.

## Frozen scope

- 24 new development tasks: 12 `valid_seen` and 12 `valid_unseen`
- Task family: `look_at_obj_in_light`
- Every task is disjoint from the TG4 held-out schedule and TG6 v4 result
- Three paired conditions: current baseline, history-aware anti-cycle, and
  observable-progress-aware selector
- 72 planned episode rows
- 50 steps per episode, zero retries, stop on the first hard invariant
  violation
- One fixed seed per task reused across all three conditions
- Runtime inputs remain exactly `observation`, `historical_actions`, and
  `admissible_actions`
- No provider, model, API, network, Phase 0-6, Phase 6, WebShop, other-model,
  or other-dataset use

## Hypotheses

### H1: Selector-order loop

The first eligible admissible action is repeatedly selected even when recent
history shows that the resulting action-state pattern is not productive.
The anti-cycle ablation should reduce the pre-registered two-cycle rate.

### H2: Missing trajectory control

Even after suppressing immediate cycles, the system may still lack a
task-level progress signal. The progress-aware ablation should increase
observable novelty and skill/edge transitions without violating admissibility.

### H3: Observable-state insufficiency

Some tasks may have conflicting goals despite identical allowed-input histories.
Such cases cannot be resolved by selector tuning under the declared runtime
contract. The indistinguishable-goal audit is post-hoc diagnostic only and
cannot feed goal metadata into any runtime condition.

## Metrics and gate

Primary metrics are episode success, 50-step completion, two-cycle rate,
repeated-state rate, unique actions, unique observable states, skill switches,
abstention, and trace validity. Results are paired by task and seed.

The mechanism-positive gate requires at least one trajectory ablation to cut
two-cycle rate by 50% or more relative to baseline, stay at or below 25%
abstention, preserve 100% trace validity, and gain at least two paired
successes. If loops improve but success remains at most 1/24 and the
indistinguishable-goal audit finds conflicting goals, the result is
observability-limited. Failure to reduce loops or any invariant violation is
negative. Everything else is inconclusive.

## Interpretation boundary

The v4 held-out result remains a single frozen negative capability result for
the implemented selector on the original 40 tasks. The new development pilot
may explain that result but cannot revise it, relabel it, or authorize a new
held-out claim. A new held-out experiment would require a separately
versioned preflight, a new task schedule, and fresh exact authorization.

## Deliverables

1. Zero-network preflight and schedule audit.
2. Paired development runner with three explicitly versioned selector
   conditions.
3. Per-transition trace audit showing allowed inputs, admissible terminal
   actions, skill/edge choices, and cycle diagnostics.
4. Failure-mode report separating loop control, trajectory progress, and
   observability insufficiency.

The design is frozen before any development episode execution. This document
does not authorize the 72-row pilot.
