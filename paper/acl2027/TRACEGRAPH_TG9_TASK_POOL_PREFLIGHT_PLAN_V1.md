# TraceGraph TG9 Task-Pool and Preflight Plan v1

Date: 2026-09-18

## Purpose

TG9 tests why the TG8 observable-subgoal controller failed every two-object
placement task. This document freezes the local two-object task population,
its prior-exposure labels, and the future 2 x 2 row schedule. It is a
zero-network design preflight: it runs no environment episode, takes no
action, and grants no readiness or execution authorization.

## Population and exposure labels

The eligible population is every ALFWorld `pick_two_obj_and_place` identity in
local `valid_seen` and `valid_unseen` for which both `traj_data.json` and
`game.tw-pddl` exist. Identity is
`sha256(split + ":" + task_relative_path)`. The expected population is 41
identities.

Prior execution is reconstructed only from completed TG6, TG7, and TG8 result
rows. The 10 TG8 two-object identities are frozen as `diagnosis_only` and may
be used for trace diagnosis or selector development, never as TG9 validation
outcomes. Sixteen earlier TG6/TG7 two-object identities are also excluded from
validation. The remaining 15 never-executed identities form one indivisible
internal-validation set; none is consumed for selector tuning.

Prior TG8 v1-v4 schedules are audited separately from execution. Thirteen of
the 15 validation identities appeared in an earlier zero-execution schedule;
two did not appear in any prior TG8 schedule. The former are marked
`schedule_contaminated`, and the latter `prior_schedule_identity_blind`.
Because only two identities satisfy the stricter label, TG9 is internal
mechanism validation, not a blind confirmatory experiment.

## Factorial schedule

The four frozen conditions are:

1. `type_level_current_coverage`
2. `instance_bound_current_coverage`
3. `type_level_open_close_coverage`
4. `instance_bound_open_close_coverage`

Factor A changes only the progress representation: a type-level ledger versus
instance-bound object slots. Factor B changes only SkillBank action coverage:
the current coverage versus audited `OpenObject`/`CloseObject` coverage. The
candidate eligibility, anti-cycle controller, deterministic tie-breaks,
runtime inputs, and all other rules must remain fixed in the later runner.
Explicit second-round subgoal re-entry is an instance-binding behavior and a
mechanism outcome, not an independent TG9 factor.

All 15 validation identities receive three paired deterministic seeds and all
four conditions, producing 180 materialized rows. The task identity is the
independent unit; repeated seeds are reproducibility checks and never increase
the statistical sample size. Condition position is assigned by deterministic
cyclic Latin rotation and must be balanced to 11 or 12 rows per
condition-position cell.

## Outcomes and interpretation

The frozen default primary endpoint is completion of both placements by step
50, matching the environment behavior observed in TG8. Completion by step 75
is unavailable unless a later readiness artifact proves that the environment
genuinely supports 75 action steps before formal execution. Mechanism outcomes must
include first-object placement, second-round re-entry, acquisition of a
distinct second instance, second-object placement, identity collisions,
OpenObject/CloseObject eligibility and selection, two-cycle incidence, ledger
validity, trace validity, and terminal admissibility.

Any later result must report all 15 tasks together and separately disclose the
13 schedule-contaminated and two prior-schedule-identity-blind cases. It must
not call the set blind, held-out confirmatory, or statistically independent at
the 180-row level.

## Execution boundary

Runtime selection may receive exactly `observation`, `historical_actions`, and
`admissible_actions`. Task descriptions, trajectories, PDDL, scene/planner
state, environment object identifiers, expert actions, evaluation labels, and
private TG metadata are forbidden runtime inputs. Network, provider, model,
API, paid calls, Phase 0-6 reuse, WebShop, other models, and other datasets
remain closed.

This preflight records 41 eligible identities, 15 validation tasks, 180
materialized rows, zero completed calls, zero episodes, and zero actions. A
separately versioned selector, readiness artifact, runner, immutable hashes,
and fresh exact user authorization are required before any execution.
