# TraceGraph TG8 Observable-Subgoal Factorial Plan v3

Date: 2026-09-09

## Status

TG8 v3 supersedes the unexecuted v1 and v2 execution proposals. Both earlier
designs ran zero episodes and are retained as immutable design provenance. v3
is a zero-network pilot design and opens no execution authorization.

## Hypothesis and factorial design

TG7 showed legal but ineffective action sequences. v3 tests two factors that
can each change action ranking:

- representation: unresolved lexical task tokens versus an ordered observable
  subgoal ledger;
- controller: greedy progress ranking versus the same ranking with history and
  two-cycle penalties.

The four cells are `lexical_greedy`, `lexical_anti_cycle`,
`observable_subgoal_greedy`, and `observable_subgoal_anti_cycle`. All cells use
the same admissible candidate set, SkillGraph filter, parser, history cap,
timeout, and final deterministic tie-break.

For endpoint `Y`, preregister:

- `Delta_R = mean((Y_SG-Y_LG) + (Y_SA-Y_LA))/2`;
- `Delta_C = mean((Y_LA-Y_LG) + (Y_SA-Y_SG))/2`;
- `Delta_RC = mean((Y_SA-Y_SG) - (Y_LA-Y_LG))`.

Here `L/S` denote lexical/structured representation and `G/A` denote
greedy/anti-cycle control. Compute the contrasts within task and replicate,
then use a paired task-cluster bootstrap with 10,000 resamples and 95%
percentile intervals. Primary endpoints are completion by step 50 and
episode-level two-cycle incidence. Completion by step 75 is sensitivity.

## Selector contract

Lexical score is unresolved task-token overlap with the candidate command.
Structured score is a deterministic tuple containing next-subgoal action-family
match and entity-token overlap. Greedy control ranks by representation score,
admissible-action order, and stable skill ID. Anti-cycle control uses the same
representation score followed by unseen-action and outside-detected-cycle
preferences, then the same final tie-break.

The structured grammar is limited to the three frozen task families as parsed
from the initial observation:

- simple placement: locate object, pick up object, locate destination, put;
- two-object placement: repeat locate, pick up, locate destination, put twice;
- clean then place: locate object, pick up, locate sink basin, clean, locate
  destination, put.

At each next step, a pending subgoal is completed only when the previous
selected action matches its action family/entity and the canonical observable
snapshot changes. A matching action without snapshot change is false progress.
The trace records the pending action, before/after fingerprints, evidence
source, completed subgoal IDs, and unresolved ordered subgoals.

Runtime selection receives exactly `observation`, `historical_actions`, and
`admissible_actions`. Static operation grammar is versioned code, not an
episode-specific input. Task files, PDDL/planner/scene state, expert future
actions, evaluation labels, and Phase 0-6/TG6/TG7 private metadata are banned.

## Sampling and frozen rows

Use five distinct object/receptacle templates from each of six
family-by-split cells, selected by stable SHA-256 rank. Select one task identity
per template, for 30 tasks total: 15 `valid_seen`, 15 `valid_unseen`, and 10 per
family. Only identities used in executed TG4/TG6/TG7 work are excluded.
Unexecuted TG8 v1/v2 schedules may be reused because no actions, episodes, or
outcomes exist for them; their hashes remain bound as design provenance.

Use three paired replicate seeds and four conditions, totaling 360 rows. The
schedule must materialize every row, seed, and a hash-derived condition order.
Each row resets a new environment. Run at most 75 steps, with step 50 as the
primary censoring landmark.

## Metrics and decision

Report success/completion and two-cycle incidence at episode level. Report
progress, false progress, repeated snapshots, and action diversity separately
at transition level. Also report first-progress step, ledger validity,
provenance completeness, trace validity, terminal admissibility, latency, and
history truncation.

This remains a pilot: a contrast whose cluster-bootstrap CI excludes zero is a
`signal`, not confirmatory proof. If all CIs cross zero, report
`pilot_inconclusive`. Any runtime-input, trace, SkillGraph, or admissibility
violation makes the whole factorial run `invalid`; partial data cannot enter
scientific contrasts.

Before any readiness run, the selector must pass synthetic and train-only
fixtures for target-word/no-delta false progress, delta/no-target nonprogress,
repeated snapshots, failed-action text, synonym normalization, condition
separation, and exact input isolation. A separately versioned runner and fresh
exact authorization are required for all 360 episode rows.
