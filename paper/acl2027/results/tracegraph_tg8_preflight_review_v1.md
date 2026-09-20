# TraceGraph TG8 Preflight Review v1

Date: 2026-09-09

## Review status

TG8 v1 is a valid zero-network design artifact, but it is **not execution
ready**. The preflight is structurally complete: 24 fresh tasks, 96 planned
rows, four conditions, zero selected-task overlap with TG4/TG6/TG7, and zero
network/provider/model/API/paid calls. No episode authorization is open.

## Blocking findings

1. The decision gates do not identify the 2x2 factorial effects. The v1 gate
   compares the structured-plus-controller condition against baseline, which
   confounds representation, controller, and interaction. v2 must preregister
   representation main effect, controller main effect, and difference-in-
   differences interaction separately.
2. The sample has only four identities per family-by-split cell and one seed per
   identity. Either expand the design or explicitly downgrade it to a pilot that
   reports effect sizes and cluster-aware intervals only.
3. The schedule uses the first lexicographically sorted identities and contains
   repeated object/receptacle/template clusters. v2 must use deterministic
   hash-based stratified sampling with cluster exclusions or cluster-aware
   analysis.
4. The structured subgoal ledger and observable-delta rule are not yet an
   executable specification. The four selectors need pseudocode, exact
   candidate/tie-break rules, explicit first-eligible semantics, and unit/
   adversarial tests before readiness.
5. Metric denominators and invalid-run rules are incomplete. v2 must define
   episode-level versus transition-level aggregation, false-progress events,
   collision taxonomy, confidence intervals, and make any hard-invariant
   violation invalidate the entire factorial run rather than produce a partial
   method result.

## Required v2 work

- Freeze the estimands and paired contrasts before selecting new tasks.
- Add deterministic subgoal grammar and state-delta evidence rules.
- Add decoy/negative ledger tests: target word without state change, state
  change without target mention, repeated snapshots, failed actions, and
  synonymous observations.
- Add selector-difference and budget contracts: identical model, history cap,
  tie-break, action normalization, timeout, and condition randomization.
- Decide whether v2 is a pilot or a powered study. Until that decision is
  recorded, do not call any outcome “supported” or “replicated.”
- Add TG7 audit provenance for target-surface hits and collision classes, since
  those quantities motivate TG8 but are currently recomputed post hoc.

## Go / no-go

**No-go for TG8 zero-step readiness and episode execution in v1.** The next
admissible action is a separately versioned TG8 v2 zero-network redesign and
its cache-free selector/unit-test suite. Provider/model/API, paid, Phase 0-6,
Phase 6, WebShop, other-model, and other-dataset permissions remain closed.
