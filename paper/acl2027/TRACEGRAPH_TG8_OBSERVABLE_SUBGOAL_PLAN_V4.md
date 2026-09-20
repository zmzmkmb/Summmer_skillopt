# TraceGraph TG8 Observable-Subgoal Factorial Plan v4

Date: 2026-09-09

## Purpose

TG8 v4 is the execution-candidate design that supersedes the unexecuted v1-v3
proposals. It preserves v3's identifiable `lexical/structured x
greedy/anti-cycle` pilot, while repairing global template uniqueness,
condition-position balance, and zero-execution accounting.

## Experimental factors and contrasts

The four conditions are `lexical_greedy`, `lexical_anti_cycle`,
`observable_subgoal_greedy`, and `observable_subgoal_anti_cycle`. The
representation score changes between lexical and structured conditions in both
controller branches. The anti-cycle factor adds only history/cycle preferences
after the representation score. Candidate eligibility and final tie-breaks are
otherwise identical.

For success and episode-level two-cycle incidence, compute within-task,
within-replicate representation, controller, and difference-in-differences
interaction contrasts. Use paired task-cluster bootstrap with 10,000 resamples
and 95% percentile intervals. This is pilot evidence; an interval excluding
zero is a signal, not confirmatory proof.

## Observable-subgoal contract

The structured grammar covers simple placement, two-object placement, and
clean-then-place tasks parsed from the initial observation. It produces ordered
locate, pick-up, operation, destination, and put subgoals. A pending subgoal is
completed only when the selected action matches its family/entity and the next
canonical observation-plus-admissible-actions snapshot changes. A matching
action without a snapshot change is recorded as false progress.

Selection receives exactly `observation`, `historical_actions`, and
`admissible_actions`. Static versioned grammar is allowed; task files, PDDL,
planner/scene state, expert future actions, evaluation labels, and private
phase metadata are prohibited.

## Sampling and order

Exclude every identity used by executed TG4, TG6, or TG7 work. The unexecuted
TG8 v1-v3 schedules ran zero episodes/actions/calls and are bound as design
provenance rather than treated as spent behavioral samples.

Select five templates per family-by-split cell, with all 30 template keys
globally unique. For each selected template choose one task identity by stable
SHA-256 rank. Use three paired seeds per task and four conditions, materializing
360 rows. Hash-rank the 90 task-replicate blocks, assign cyclic Latin rotations
0-3, and require every condition-position count to be 22 or 23.

Each row uses a fresh environment reset, runs at most 75 steps, and records
completion by step 50 as primary and by step 75 as sensitivity. A first hard
runtime-input, trace, SkillGraph, or terminal-admissibility violation stops the
run and invalidates all partial scientific contrasts.

## Execution boundary

The design manifest distinguishes planned/materialized rows from executed
calls: 360 planned rows, 360 materialized rows, zero completed calls, zero
episodes, and zero actions. Readiness remains closed until the selector and its
adversarial fixtures pass. Episode execution requires a separately versioned
authorized runner and fresh exact user authorization.
