# TraceGraph TG8 Preflight Review v2

Date: 2026-09-09

## Decision

TG8 v2 is **no-go for readiness and episode execution**. It improves on v1 by
introducing three replicate seeds, explicit factorial contrasts, a pilot claim
boundary, and cluster-aware bootstrap analysis. However, three design
inconsistencies remain blocking.

## Blocking findings

1. The frozen sample contradicts the plan. The plan describes cells with at
   least five template clusters, while the v2 preflight contains only three
   templates for `valid_unseen/pick_two_obj_and_place` across six tasks. The
   cell therefore has strong within-template pseudoreplication.
2. The step-budget contract is impossible as written. Configuration freezes
   `max_steps_per_episode=50` but asks for sensitivity at 75 steps. A 50-step
   trajectory cannot identify a 75-step outcome.
3. `observable_subgoal_first_eligible` records the structured ledger but does
   not let it affect ranking. Consequently the representation factor has no
   behavioral effect in the first-eligible branch; the proposed representation
   main effect is partly structural zero rather than an empirical contrast.

## Required v3 changes

- Use a genuine `lexical/structured x greedy/anti-cycle` factorial in which the
  representation determines the progress score in both controller branches.
- Sample one identity from each selected template and reduce the balanced cell
  quota to five, yielding 30 task identities with no within-cell duplicate
  template.
- Treat unexecuted TG8 v1/v2 schedules as design provenance rather than spent
  behavioral data; exclude all executed TG4/TG6/TG7 identities.
- Run each authorized trajectory for at most 75 steps, with completion by step
  50 as the primary landmark and completion by step 75 as sensitivity.
- Materialize every task/replicate/condition row, seed, and condition order in
  the frozen schedule before selector readiness.

No episode, action, provider/model/API, network, paid, Phase 0-6, Phase 6,
WebShop, other-model, or other-dataset permission is opened by this review.
