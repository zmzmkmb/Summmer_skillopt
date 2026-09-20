# TraceGraph TG6 Trajectory Failure-Analysis Implementation Note v1

Date: 2026-09-05

## Status and binding

This note is an executable-definition supplement for the already frozen
trajectory failure-analysis v2 design. It does not modify the v2 plan,
configuration, schedule, or preflight artifact.

- Plan:
  `paper/acl2027/TRACEGRAPH_TG6_TRAJECTORY_FAILURE_ANALYSIS_PLAN_V2.md`
- Plan SHA-256:
  `72cdab4e785f8f47bacea65d8de361e0fbc5afb44bc36c542eac6ab256420802`
- Configuration:
  `configs/acl2027/tracegraph_tg6_trajectory_failure_analysis_preflight_v2.json`
- Configuration SHA-256:
  `224eb90c3b5672c2326da4ebba342a61837ffe5d3d27ad1fbc92234c5f7da535`
- Preflight aggregate fingerprint:
  `b82976f1c5be80bd00d67f4e0397f8a72f4eb56282536864ca649a8f9fe74d07`
- Development schedule SHA-256:
  `8f6b5cf362a9bcfdbc2f2818f676d6016503cbdda635b6b641a18dfeab7919ae`

`execution_authorized=false` remains in force. This note authorizes no
episode, network, provider, model, API, or paid call.

## Why this is the next experiment

The frozen TG6 v4 trace is a valid negative capability result:

- 40/40 episodes reached the 50-step limit;
- 0/40 episodes succeeded;
- every episode contained a two-action alternating cycle;
- every episode used exactly two distinct terminal actions;
- a read-only diagnostic using only `(observation, admissible_actions)` found
  three distinct observable snapshots and 47 repeated snapshot transitions
  per 50-step episode.

The last number is not computed from the existing
`observable_state_fingerprint`, because that audit fingerprint includes the
ever-growing `historical_actions` field. Using that field to measure state
repetition would make a repeated state look new at every step.

Phase 5 remains historical motivation only. Its incompatible-control result
was 0/40 final-answer accuracy, while the evidence-abstain condition selected
no candidate in 40/40 rows and still answered 38/40 correctly. These results
motivate studying conservative selection and downstream behavior, but no
Phase 0-6 artifact may enter the TraceGraph SkillBank, runtime, tuning data,
threshold selection, or evaluation substrate.

## Research question

The v2 pilot tests whether the TG6 v4 failure is primarily:

1. a first-eligible selector-order problem;
2. missing trajectory-level progress control; or
3. an information-sufficiency limit under the observable-input boundary.

The pilot is a mechanism diagnosis, not a new held-out capability claim.

## Frozen scope

- 24 fresh development task identities;
- 12 `valid_seen` and 12 `valid_unseen`;
- 9 direct-cycle replication tasks from
  `look_at_obj_in_light`;
- 15 multi-step transfer tasks from
  `pick_and_place_simple` and
  `pick_two_obj_and_place`;
- three conditions per task, for 72 paired episodes;
- one fixed seed per task reused across all conditions;
- at most 50 steps per episode;
- zero retries;
- stop on the first hard invariant violation.

The primary estimand is the paired change in episode-level two-action-cycle
rate on the nine-task direct-cycle stratum. The transfer stratum is secondary
and must not be pooled into the primary causal claim.

## Runtime boundary

Every selector condition receives exactly:

```text
observation
historical_actions
admissible_actions
```

The following remain forbidden at runtime:

```text
task_description
raw_trajectory
planner_state
pddl_params
scene_state
expert_future_actions
evaluation_label
phase0_to_phase6_artifact
```

No condition may inspect future observations, hidden goal state, PDDL facts,
task identity, private labels, or expert actions.

## Transition fingerprints and diagnostics

Each transition must retain the existing audit fingerprint:

```text
audit_input_fingerprint =
  hash({
    "observation": observation,
    "historical_actions": historical_actions,
    "admissible_actions": admissible_actions
  })
```

This fingerprint proves the complete runtime input boundary and is not the
state-repetition metric.

The runner must additionally compute, without adding any runtime information:

```text
observable_snapshot_fingerprint =
  hash({
    "observation": observation,
    "admissible_actions": admissible_actions
  })
```

The snapshot fingerprint deliberately excludes `historical_actions`, whose
length changes after every action. It is an analysis projection of permitted
inputs, not hidden state.

The runner must also record:

- `action_seen_before`: whether the selected terminal action occurred earlier;
- `skill_changed`: whether the selected skill differs from the previous one;
- `edge_changed`: whether the selected edge differs from the previous one;
- `cycle_triggered`: whether the previous four actions were `a, b, a, b`
  with `a != b`;
- `action_state_fingerprint`: a hash of the observable snapshot and selected
  terminal action.

Definitions:

```text
two_cycle_episode =
  exists i such that actions[i:i+4] == [a, b, a, b] and a != b

two_cycle_rate =
  mean(two_cycle_episode over episodes in the stratum)

repeated_snapshot_rate =
  count(snapshot fingerprint already seen earlier in the episode) / T

repeated_snapshot_episode =
  1 if any snapshot fingerprint repeats, else 0

cycle_step_rate =
  count of action positions participating in a detected two-cycle /
  max(T - 3, 1)
```

The binary episode-level two-cycle rate is the frozen primary metric. The
step-level rate and snapshot metrics are explanatory secondary metrics.

## Selector conditions

All conditions use the same candidate generation, SkillBank, SkillGraph edge
construction, admissibility checks, fallback policy, trace schema, seed, and
environment files. Only the selector tie-breaking policy changes.

### Baseline: `baseline_first_eligible`

Use the TG6 v4 rule exactly:

1. preserve the environment-provided admissible-action order;
2. find the first admissible command with at least one train-derived matching
   skill;
3. select the lowest stable skill ID for that command;
4. use the existing first permitted edge;
5. if no eligible command exists, use the first non-`help` admissible command,
   or the first admissible command if necessary.

### Ablation A: `history_aware_anti_cycle`

Use the same candidate generation as the baseline. Before selecting:

1. detect a two-action cycle from the last four executed actions;
2. if no cycle is detected, apply the baseline rule;
3. if a cycle is detected, rank eligible commands by:
   - terminal command not belonging to the detected pair first;
   - original admissible-action order second;
   - stable skill ID third;
4. if every eligible command belongs to the detected pair, fall back to the
   baseline rule.

This condition tests whether explicit recent-history control is sufficient to
break the observed loop while preserving admissibility.

### Ablation B: `observable_progress_aware`

Use the same cycle trigger and candidate set. When a cycle is detected, rank
candidate command/skill pairs lexicographically by:

1. terminal command not seen earlier in the episode;
2. matching skill ID different from the previous selected skill;
3. terminal command not belonging to the detected cycle pair;
4. original admissible-action order;
5. stable skill ID.

The first three terms are descending Boolean preferences; the final two terms
are ascending deterministic tie-breakers. If no candidate is available after
the ranking, use the baseline fallback. No future state is predicted and no
hidden goal is consulted.

The edge is then rebuilt using the selected skill and the existing permitted
edge construction. `edge_changed` is measured, but it cannot override
admissibility or the frozen SkillGraph contract.

## Measurements and reporting

For every condition report:

- episode success;
- completion within 50 steps;
- two-cycle episode rate;
- cycle-step rate;
- repeated snapshot episode rate;
- repeated snapshot rate;
- unique terminal-action count;
- unique observable-snapshot count;
- skill-switch count;
- edge-switch count;
- abstention rate;
- terminal-action admissibility;
- trace validity;
- hard-invariant violations.

Report each metric:

1. overall;
2. direct-cycle versus transfer stratum;
3. task family;
4. `valid_seen` versus `valid_unseen`;
5. selector condition.

The primary comparison is each ablation against the baseline on the same task
and seed. With only nine direct-cycle identities, exact paired counts and
per-task traces are primary; any confidence interval or permutation result is
descriptive and cannot replace the frozen decision gate.

## Decision and interpretation

Apply the v2 frozen gate unchanged:

- **Mechanism-positive:** a trajectory ablation reduces direct-cycle
  two-cycle rate by at least 50%, has at most 25% abstention across all 24
  tasks, preserves 100% trace validity, and gains at least two successes over
  baseline across the paired 24-task set.
- **Observability-limited:** a trajectory ablation reduces direct-cycle
  two-cycle rate by at least 50%, neither ablation exceeds one success out of
  24, and the post-hoc indistinguishable-goal audit finds an allowed-input
  equivalence class with conflicting goals.
- **Negative:** neither ablation reduces the primary two-cycle rate by 50%, or
  any admissibility, trace, or input-isolation invariant fails.
- **Inconclusive:** all other outcomes.

The post-hoc indistinguishable-goal audit may use private task metadata only
after execution. It must never alter a selector, gate, task choice, or
runtime trace.

## Causal-resolution limit and follow-up

The three-condition v2 pilot is sufficient to answer:

> Can history or observable-progress heuristics break the reproduced loop
> without violating the observable runtime contract?

It is not sufficient by itself to identify whether the cause is specifically
candidate-list order or the absence of trajectory memory, because both
ablations can change the selected action after a loop appears.

If v2 is mechanism-positive or shows a large loop reduction, the next
experiment must be a fresh zero-network 2x2 attribution design on new task
identities:

| Candidate-order policy | Trajectory control | Purpose |
|---|---|---|
| first-eligible | none | exact baseline |
| order-neutral | none | isolate list-order effect |
| first-eligible | history/progress control | isolate trajectory control |
| order-neutral | history/progress control | test interaction |

The order-neutral policy must be frozen before execution and use only the
current admissible-action list, for example a stable hash order or a fixed
reversal rule, never task identity or hidden state. This follow-up requires a
new versioned config, new task schedule, new preflight, and fresh exact
authorization. It is not included in the current 72-row authorization scope.

## Execution sequence

1. Keep the v2 plan, config, schedule, and preflight immutable.
2. Implement a separately versioned local runner using the exact definitions
   in this note.
3. Run zero-step readiness over all 24 selected task identities.
4. Run cache-free selector, trace, admissibility, cycle, and input-isolation
   tests.
5. Run handoff validation and update the experiment checkpoint.
6. Obtain exact authorization bound to both the v2 preflight and the new
   runner.
7. Execute exactly 72 development episodes.
8. Audit all traces and compute the frozen gate.
9. Write a failure-mode report; only then decide whether a new held-out phase
   is justified.

No provider, model, API, network, Phase 0-6, Phase 6, WebShop, other-model,
or other-dataset action is authorized by this note.
