# TraceGraph TG8 Observable-Subgoal Factorial Plan v2

Date: 2026-09-09

## Status and scope

This v2 supersedes the execution proposal in TG8 v1 but does not mutate the
v1 preflight or schedule. It is a zero-network **pilot design**. Its results
may estimate representation, controller, and interaction effects with
cluster-aware confidence intervals, but may not be described as confirmatory
support or replication.

## Research question

TG7 showed that lexical target-surface selection can improve without task
completion. TG8 v2 asks whether an explicitly observable state-delta ledger
and an anti-cycle controller contribute separate or interacting effects.

## Factorial estimands

Let `R=0` be lexical representation, `R=1` structured observable-subgoal
representation; let `C=0` be first-eligible control and `C=1` progress-memory
control. For every task identity and replicate seed, record binary success and
episode-level two-cycle incidence.

- Representation main effect: `Delta_R = mean[(Y_1,0-Y_0,0) + (Y_1,1-Y_0,1)] / 2`.
- Controller main effect: `Delta_C = mean[(Y_0,1-Y_0,0) + (Y_1,1-Y_1,0)] / 2`.
- Interaction: `Delta_RC = mean[(Y_1,1-Y_1,0) - (Y_0,1-Y_0,0)]`.

The same contrasts are computed for two-cycle incidence, with improvement
defined as a negative difference. Paired cluster bootstrap resamples task
identity clusters and preserves all three replicate seeds and four conditions
within each task. Report point estimates and 95% CIs; no binary claim is made
when a CI crosses zero.

## Frozen conditions and selector contract

1. `baseline_first_eligible`: lexical representation, first eligible action.
2. `lexical_progress_memory`: lexical ledger, anti-cycle/unresolved-anchor
   controller.
3. `observable_subgoal_first_eligible`: structured ledger is updated and
   traced but cannot affect candidate ranking; first eligible action is used.
4. `observable_subgoal_progress_memory`: structured ledger plus the same
   controller logic and tie-break sequence as condition 2.

All four conditions use the same candidate set, canonical action parser,
SkillGraph eligibility test, action-order tie-break, history cap, timeout, and
abstention rule. The only representation factor is ledger contents; the only
controller factor is ranking among the same eligible candidates.

## Observable-subgoal ledger contract

The ledger receives only the three allowed runtime fields. It stores:

- normalized observable snapshot fingerprint;
- action-state fingerprint;
- candidate action family and target tokens;
- an ordered list of unresolved subgoal clauses;
- `progress_event` only when the next observation/admissible-action set differs
  from the prior canonical snapshot after an admissible action;
- `false_progress_event` when an action overlaps a subgoal token but the next
  canonical snapshot is unchanged;
- evidence provenance pointing to `runtime_inputs.observation`,
  `runtime_inputs.historical_actions`, or
  `runtime_inputs.admissible_actions`.

No task file, PDDL state, planner state, expert action, evaluation label, or
private phase artifact can enter the ledger. Unit tests must cover target-word
without state change, state change without target word, repeated snapshots,
failed-action text, and synonymous observation wording.

## Sampling and replication

Select 6 task identities per family-by-split cell using a fixed hash-ranked
stratified sampler. The sampler first maximizes distinct object/receptacle
template keys, then uses the stable hash rank to choose remaining identities.
The resulting pilot has 36 identities: 6 cells x 6 tasks. Use three paired
replicates per identity and all four conditions, for 432 planned rows. The
minimum-5-template cells are retained but reported with cluster-aware CIs and
explicitly treated as pilot evidence.

Use replicate seeds `5200 + 100*replicate_index + task_ordinal`. Randomize
condition order with a frozen hash-derived order, reset the environment before
every row, and record the order and seed in the trace.

## Metrics and invalid-run policy

Primary endpoints are task success and episode-level two-cycle incidence.
Secondary endpoints are observable-progress-event rate, false-progress rate,
first-progress step, repeated-snapshot incidence, unique snapshots, and
subgoal-ledger validity. Report episode-level and transition-level metrics
separately; never pool them into one rate. A hard input/trace/admissibility
violation invalidates the entire 432-row run. Partial rows are retained only
for diagnosis and cannot enter any contrast or gate.

Step budgets are reported at 50 and 75 steps as a censoring sensitivity; the
50-step result remains the primary budget. Record latency, history truncation,
and implementation fingerprints for all conditions.

## Pilot decision rules

- `representation_signal`: `Delta_R` CI excludes zero for success or cycle
  incidence, with the direction preregistered above.
- `controller_signal`: `Delta_C` CI excludes zero in the expected direction.
- `interaction_signal`: `Delta_RC` CI excludes zero and the structured-memory
  contrast is directionally stronger than the lexical-memory contrast.
- `pilot_inconclusive`: all relevant CIs cross zero or integrity is valid but
  the available cluster count is too small for stable estimation.
- `invalid`: any hard invariant, input-isolation, trace, or admissibility
  violation occurs; no scientific gate is applied.

This pilot authorizes no episode, model, provider, API, network, paid, or
formal-scaling call. A separately versioned runner and fresh exact user
authorization are required after v2 selector implementation and readiness.
