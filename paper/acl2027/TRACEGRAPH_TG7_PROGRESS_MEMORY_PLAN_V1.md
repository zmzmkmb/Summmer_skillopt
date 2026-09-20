# TraceGraph TG7 Progress-Memory Plan v1

Date: 2026-09-07

## Objective

Test whether the TG6 legal-but-ineffective trajectory failure is reduced by
preserving the task anchor and maintaining an auditable target-directed
progress state derived only from the permitted runtime inputs.

## Runtime boundary

Every condition receives exactly:

```text
observation
historical_actions
admissible_actions
```

The task anchor may only be parsed from the initial `observation` returned by
the environment. No external task description, hidden state, planner state,
PDDL facts, future expert action, evaluation label, or Phase 0-6 artifact may
enter runtime selection.

## Frozen conditions

1. `baseline_first_eligible`: the unchanged TG6 selector.
2. `task_anchor_aware`: preserve the initial observable task anchor and use it
   as a deterministic preference for admissible commands mentioning the
   anchored object or destination.
3. `progress_memory`: preserve the task anchor and maintain a provenance-carrying
   ledger of observed target mentions, attempted actions, state changes, and
   unresolved target steps. Candidate ranking must prefer actions that advance
   the unresolved target ledger, while retaining admissibility and SkillGraph
   constraints.

The anchor and progress ledger are internal state derived from the allowed
runtime observations; they are not hidden labels.

## Design

Use 24 fresh ALFWorld multi-step identities, balanced 12 `valid_seen` and
12 `valid_unseen`, with 8 tasks each from:

- `pick_and_place_simple`;
- `pick_two_obj_and_place`;
- `pick_clean_then_place_in_recep`.

Run all three conditions on each task with one fixed seed, at most 50 steps,
zero retries, and first-hard-invariant stop. The schedule must be disjoint
from TG4, TG6, and every prior TG7 artifact.

## Primary hypothesis

If the main failure is missing target-directed progress representation, then
`progress_memory` should improve task completion and reduce repeated-state
failure relative to the frozen baseline. `task_anchor_aware` may improve
target-surface selection without being sufficient for durable completion.

## Measurements

- episode success and completion before the step limit;
- two-cycle episode rate and cycle-step rate;
- repeated observable snapshot rate;
- target-surface action hit rate as post-hoc diagnostic only;
- unique actions and observable snapshots;
- progress-ledger validity and provenance completeness;
- SkillGraph edge compliance;
- terminal-action admissibility;
- abstention and hard-invariant violations.

## Decision gate

- **Progress-supported:** `progress_memory` gains at least two paired successes
  over baseline, reduces the pooled multi-step two-cycle rate by at least 50%,
  preserves 100% trace validity and admissibility, and has at most 25%
  abstention.
- **Anchor-only:** `task_anchor_aware` improves target-surface hits or success,
  but `progress_memory` adds no further improvement; the missing information
  was primarily loss of the initial task anchor.
- **Representation-limited:** both augmented conditions preserve the runtime
  contract but fail to improve completion, while post-hoc collision classes
  with conflicting goals remain.
- **Negative:** any condition violates input isolation, trace completeness,
  admissibility, or SkillGraph constraints.
- **Inconclusive:** all other outcomes.

## Execution policy

This document authorizes no episode, model, provider, API, network, paid, or
formal-scaling call. Before execution, create a separately versioned
zero-network preflight, freeze the fresh schedule and hashes, run cache-free
regression and zero-step readiness, and obtain exact user authorization bound
to the resulting preflight and runner fingerprints.
