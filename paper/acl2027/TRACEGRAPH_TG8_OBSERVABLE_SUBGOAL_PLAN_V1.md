# TraceGraph TG8 Observable-Subgoal Factorial Plan v1

Date: 2026-09-09

## Motivation

TG7 showed that lexical task-anchor targeting can raise target-surface hits
without producing any completed task. TG8 tests whether the missing component
is an observable state-delta/subgoal representation, an anti-cycle controller,
or their interaction.

## Runtime contract

Every selector receives exactly `observation`, `historical_actions`, and
`admissible_actions`. The structured subgoal ledger may mark progress only from
text and action evidence present in those fields. It may not use task files,
PDDL facts, planner state, hidden scene state, expert future actions, labels,
or any Phase 0-6 artifact.

## Factorial conditions

1. `baseline_first_eligible`: existing lexical representation and first
   eligible action.
2. `lexical_progress_memory`: existing lexical anchor/ledger with anti-cycle
   and unresolved-anchor ranking.
3. `observable_subgoal_first_eligible`: structured observable subgoal/state-
   delta ledger with first eligible control.
4. `observable_subgoal_progress_memory`: structured ledger plus anti-cycle and
   unresolved-subgoal ranking.

The structured ledger can mark a subgoal complete only after a deterministic
observable evidence delta. A target-word action without an observable delta is
recorded as false progress rather than completion.

## Schedule and gates

Use 24 fresh multi-step ALFWorld identities, balanced 12 `valid_seen` and 12
`valid_unseen`, with 4 tasks per family and split from the three TG7 families.
Run all four conditions with paired seed `5200 + task ordinal`, at most 50
steps, zero retries, and stop on the first hard invariant violation. The
schedule must be disjoint from TG4, TG6, and TG7 identities.

The primary gate requires the structured representation to gain at least two
paired successes and reduce the pooled two-cycle rate by at least 50% versus
the lexical baseline, while preserving 100% trace validity and admissibility.
Within the structured representation, a controller-only gain supports the
controller hypothesis. If neither factor improves completion and conflicting
goal collision classes remain, the representation/controller limitation is
replicated. All other outcomes are inconclusive.

Primary metrics are success, completion within 50 steps, observable-progress
event rate, false-progress rate, first-progress step, two-cycle rate, repeated
snapshot rate, and unique observable snapshots. Trace validity, terminal
admissibility, ledger validity, provenance completeness, abstention, and
SkillGraph compliance are hard integrity metrics.

This document authorizes no episode, model, provider, API, network, paid, or
formal-scaling call. Execution requires a separately versioned authorized
runner and fresh exact user authorization after this zero-network preflight.
