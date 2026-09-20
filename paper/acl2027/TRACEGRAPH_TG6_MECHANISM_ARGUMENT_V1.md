# TraceGraph TG6 Mechanism Argument v1

Date: 2026-09-07

## Purpose

This note revises the ACL 2027 argument after the completed Phase 5
admission/grounding study and the TraceGraph TG6 trajectory-failure audit. It
does not modify any frozen experiment artifact and does not treat Phase 0-6
records as TraceGraph data.

The central distinction is:

```text
validity      != usefulness
safety        != progress
selection     != grounding
exploration   != completion
```

## Unified Research Problem

An agent may produce a response or action that is syntactically valid,
admissible, and locally defensible while still failing to make durable
progress toward the task objective. The research problem is therefore not
only whether a skill can be selected safely, but whether the selected skill
changes the agent's state in a target-directed way that remains auditable over
time.

This gives the paper a two-layer argument:

1. **Reuse layer:** historical experience must pass identity, scope, admission,
   evidence, and answer-level checks.
2. **Control layer:** a legally admissible skill composition must maintain a
   target-directed progress representation; avoiding immediate repetition or
   increasing action novelty is insufficient.

Phase 5 motivates the first layer. TraceGraph is the independent mechanism
study of the second layer. The relationship is conceptual, not a claim that
Phase 5 caused the TG6 failure.

## Evidence Bridge

| Layer | Frozen evidence | What it supports | What it does not support |
|---|---|---|---|
| Phase 5 admission/grounding | 240/240 contract-valid rows; 203/240 evidence sets resolved; 188/240 final answers correct; incompatible control 0/40 correct | Contract validity, evidence resolution, and final answer quality are distinct endpoints; incompatible priors can systematically corrupt answers | General accuracy improvement from typed priors or a universal safety guarantee |
| TG6 trajectory diagnostic | 72/72 episodes; 0/72 successes; 100% trace validity; 100% terminal-action admissibility; 9/9 direct-cycle episodes under all conditions | Legal execution and trajectory diversification do not imply target-directed completion | Information-theoretic impossibility of the raw observation boundary |
| TG6 post-hoc mechanism audit | 138 exact cross-task allowed-input collision groups; 134 contain different task targets; cycle states retain eligible actions outside the detected pair | The current selector/controller lacks a durable target-directed progress state under repeated observable states | That the initial task description is absent or unusable in principle |

## Mechanistic Interpretation

The strongest supported explanation is a representation-and-control failure.
The current controller has access to the declared runtime boundary
`observation`, `historical_actions`, and `admissible_actions`, and it can:

- select admissible actions;
- switch skills and SkillGraph edges;
- reduce some immediate action repetition;
- increase observable-state and action novelty.

It does not, however, maintain a persistent state of which task-relevant
subgoals have been achieved, which candidate actions have already failed for
the current objective, or what observable evidence would count as progress.
Consequently, a new action may be novel without being useful, and a skill or
edge switch may occur without changing the task's completion trajectory.

The correct claim is therefore:

> Under the frozen TraceGraph protocol, trajectory diversification and
> admissibility control are insufficient for task completion when the
> selector lacks a target-directed progress representation that persists
> across repeated observable states.

The paper must not claim:

> The raw observation boundary makes the task information-theoretically
> impossible.

The initial observation contains the task sentence. The evidence instead
shows that the current selector fails to preserve and operationalize that task
information after the environment returns to repeated room states.

## Recommended Paper Structure

### 1. Motivation

Start from the failure of endpoint collapse:

```text
well-formed response -> evidence-grounded answer -> useful answer
admissible action    -> observable transition -> task progress
```

These implications are not automatic.

### 2. Historical-reuse evidence

Use Phase 5 as a bounded motivating result. Report the separate counts for
contract validity, evidence resolution, admission, selection, and answer
correctness. Do not frame it as proof that typed history improves accuracy.

### 3. TraceGraph mechanism

Define the runtime input boundary and the constrained SkillGraph. Make the
trace fields explicit: candidate skills, permitted edges, selected edge,
admissible action, observable snapshot, and terminal decision.

### 4. TG6 negative result

Report the frozen 72-episode comparison. Separate:

- legality and trace validity;
- direct-cycle behavior;
- action/state novelty;
- target-surface and repeated-state diagnostics;
- task success.

The primary endpoint remains task completion, not novelty.

### 5. Discussion

State that anti-cycle control addresses a local recurrence symptom, whereas
task completion requires a progress state. This explains why
`history_aware_anti_cycle` and `observable_progress_aware` changed trajectory
shape without changing the negative completion outcome.

## Next Experiment: Target-Directed Progress Representation

The next experiment should be a **design-only, zero-network ablation** before
any new episode execution. It should not reopen TG6 or reuse Phase 5 rows as
TraceGraph data.

### Hypothesis

If the main failure is missing progress representation rather than merely
selector order, then a persistent progress state derived only from the initial
task observation, subsequent observations, action history, and admissible
actions should reduce repeated-state failure and improve task completion.

### Conditions

1. `baseline_first_eligible`: frozen TG6 baseline.
2. `history_aware_anti_cycle`: frozen local cycle-control ablation.
3. `progress_memory`: maintain an auditable task-progress ledger derived only
   from permitted runtime inputs. The ledger must record observed subgoal
   hypotheses, evidence supporting or contradicting them, completed-action
   history, and unresolved next-step candidates.
4. Optional diagnostic-only `oracle_progress`: never used for the main claim;
   it may be included only if a separately specified post-hoc upper bound is
   needed.

The main experiment must not consume hidden simulator state, planner state,
future expert actions, private task labels, or target gold.

### Primary Measurements

- episode success;
- completion before the step limit;
- two-cycle episode rate;
- repeated observable-state rate;
- target-surface action hit rate as a post-hoc diagnostic only;
- progress-ledger validity and provenance completeness;
- admissibility and trace validity;
- number of abstentions and hard invariant violations.

### Decision Logic

- **Supports missing-progress hypothesis:** `progress_memory` improves task
  success and reduces the primary cycle endpoint without violating the runtime
  boundary.
- **Supports observability limitation:** `progress_memory` is valid and
  auditable but cannot improve completion, while the indistinguishable-goal
  audit remains present.
- **Rejects both simple explanations:** progress memory improves neither
  cycles nor completion, indicating that the SkillGraph/action abstraction or
  environment interface requires a different redesign.

Any such experiment requires a separately versioned zero-network preflight,
fresh task identities, a contamination audit, and fresh exact authorization
before episode execution. No authorization is created by this note.

## Claim Ceiling

The current evidence supports the following bounded contribution:

> TraceGraph provides an auditable protocol for constrained skill composition
> and reveals a concrete failure mode: legal, diverse trajectories can still
> fail systematically when target-directed progress is not represented and
> preserved.

The current evidence does not support claims of universal agent improvement,
cross-domain transfer, WebShop transfer, information-theoretic impossibility,
or superiority over all alternative controllers.

## Source Artifacts

- Phase 5 analysis:
  `artifacts/acl2027_phase5_admission_grounding_analysis_v1/analysis_manifest.json`
- TG6 execution report:
  `paper/acl2027/results/tracegraph_tg6_trajectory_failure_analysis_execution_v2.md`
- TG6 mechanism audit:
  `paper/acl2027/results/tracegraph_tg6_trajectory_failure_mechanism_audit_v1.md`
- TG6 audit artifact:
  `artifacts/acl2027_tracegraph_tg6_trajectory_failure_mechanism_audit_v1/audit.json`
- Current state:
  `paper/acl2027/experiment_state.json`
