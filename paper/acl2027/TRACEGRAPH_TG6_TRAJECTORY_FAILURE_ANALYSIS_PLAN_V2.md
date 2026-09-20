# TraceGraph TG6 Trajectory Failure-Analysis Plan v2

Date: 2026-09-05

## Reason for the revision

The v1 design requested 12 fresh `look_at_obj_in_light` tasks from each
evaluation split. The local paired source contains only 2 fresh `valid_seen`
and 7 fresh `valid_unseen` identities after excluding the frozen TG4 schedule
and the TG6 v4 result. The v1 preflight therefore stopped before writing a
schedule. This v2 preserves the direct failure mode instead of silently
reducing the sample or substituting an unregistered task family.

## Research objective

Determine whether the TG6 v4 failure is primarily:

1. a first-eligible selector-order problem that creates repeated action-state
   cycles;
2. a missing trajectory-level progress controller; or
3. an information-sufficiency limit caused by the declared observable-input
   boundary.

The primary diagnostic uses every fresh task remaining in the same
`look_at_obj_in_light` family. A secondary transfer stratum tests whether the
same trajectory controls behave similarly on two fresh multi-step families.

## Frozen development scope

- 24 fresh paired task identities:
  - 9 direct-cycle replication tasks: 2 `valid_seen`, 7 `valid_unseen`
  - 15 multi-step transfer tasks: 10 `valid_seen`, 5 `valid_unseen`
- Transfer-family quotas:
  - `pick_and_place_simple`: 5 seen, 2 unseen
  - `pick_two_obj_and_place`: 5 seen, 3 unseen
- Every identity is disjoint from the TG4 held-out schedule and TG6 v4
  result.
- Three paired conditions produce 72 episode rows.
- Each episode has at most 50 steps, zero retries, and stops on the first hard
  invariant violation.
- One fixed seed per task is reused across all three conditions.
- Runtime inputs remain exactly `observation`, `historical_actions`, and
  `admissible_actions`.

## Conditions

### Baseline: `baseline_first_eligible`

The current TG6 v4 selector is frozen unchanged. It selects the first eligible
admissible action under the existing SkillGraph contract.

### Ablation A: `history_aware_anti_cycle`

Recent action history and observable-state fingerprints are used to penalize
recently repeated action-state cycles. The selected action must still be
admissible and every trace field must remain complete.

### Ablation B: `observable_progress_aware`

After detecting a cycle, the selector prefers observable novelty and
skill/edge changes using only the three permitted runtime inputs. It does not
receive task descriptions, hidden goals, planner state, labels, or future
expert actions.

## Variables and controls

The independent variable is selector condition. Task identity, split, seed,
SkillBank, derived environment files, step budget, retry policy, and runtime
input boundary are controlled. Family is a preregistered analysis stratum, not
an unreported pooled treatment.

The main paired comparison is each ablation versus the baseline on the same
task and seed. The primary claim is based on the direct-cycle stratum; the
multi-step stratum is reported as transfer evidence only.

## Measurements

Report episode success, completion at the 50-step limit, two-cycle rate,
repeated-state rate, unique actions, unique observable states, skill switches,
abstention, admissibility, trace validity, and hard-invariant violations.
Report all metrics overall and by stratum, family, split, and condition.

The post-hoc indistinguishable-goal audit may use private task metadata only to
diagnose information sufficiency. It cannot feed goal information into any
runtime selector or change the frozen gate.

## Decision gate

- **Mechanism-positive:** on the direct-cycle stratum, an ablation reduces
  two-cycle rate by at least 50%; across all 24 tasks it has at most 25%
  abstention, 100% trace validity, and at least two paired successes over the
  baseline.
- **Observability-limited:** the direct-cycle two-cycle rate falls by at least
  50%, but neither ablation exceeds 1/24 total success and the
  indistinguishable-goal audit finds conflicting goals under identical allowed
  inputs.
- **Negative:** neither ablation reduces the primary two-cycle rate by 50%, or
  any admissibility, trace, or input-isolation invariant fails.
- **Inconclusive:** all other outcomes.

The gate is diagnostic. It does not revise the frozen TG6 v4 result and does
not authorize a new held-out claim.

## Execution sequence

1. Run the zero-network v2 preflight and freeze the 24-task schedule.
2. Run cache-free regression tests and the handoff validator.
3. Register the completed preflight and checkpoint in `experiment_state.json`.
4. Create a separately versioned local runner that implements the three frozen
   conditions and performs a zero-step environment-readiness check.
5. Obtain fresh exact user authorization bound to the v2 preflight and runner.
6. Execute 72 paired development episodes locally.
7. Audit traces, compute the frozen gate, write a failure-mode report, and
   update the checkpoint.
8. Only if the diagnostic evidence warrants it, design a new held-out phase.

No provider, model, API, network, Phase 0-6, Phase 6, WebShop, other-model, or
other-dataset action is authorized by this plan.
