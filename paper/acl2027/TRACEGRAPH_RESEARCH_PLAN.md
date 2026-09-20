# TraceGraph Research Plan

Status: TG0 plan persisted on 2026-08-27. This document is the authoritative
plan for the `tracegraph-observable-state-skill-composition` research line.

## Research question

TraceGraph studies dynamic skill composition from observable agent state. The
question is whether a constrained SkillGraph can select and compose skills from
only the current observation, action history, and admissible actions, while
making the mechanism auditable. The first claim is mechanistic, not an
accuracy-improvement claim.

## Fixed design

- Primary environment: ALFWorld, before any WebShop work.
- SkillBank source: expert trajectories from the ALFWorld training split only.
- Runtime inputs: observation, historical actions, and admissible actions only.
- Composer: a constrained SkillGraph; it must expose the selected nodes,
  permitted edges, and the observable-state evidence for each transition.
- Base model: frozen `qwen3.7-plus`.
- No provider, model, API, or authorization-receipt action is part of TG0.

The runtime must not consume hidden environment state, oracle plans, task gold,
expert future actions, validation/test demonstrations, or labels that cannot be
derived from the three declared observable inputs.

## Stage sequence and preregistration

TG0 records this plan and governance boundary only. It creates no schedule,
SkillBank, model payload, authorization receipt, or external request.

TG1 may construct a versioned ALFWorld SkillBank only from training-split
expert trajectories and record trajectory, split, and skill provenance. TG2
may freeze the observable-state representation and constrained SkillGraph.
TG3 may run a zero-network mechanism audit that checks state-to-skill
eligibility, edge-constraint compliance, composition trace completeness, and
counterfactual rejection of unavailable or inadmissible skills. No stage may
claim accuracy improvement merely from these checks.

The preregistered mechanism gate requires all of the following on a held-out
ALFWorld evaluation protocol that is not used for SkillBank construction or
tuning:

1. Every selected skill and graph transition is reproducible from the declared
   observable inputs.
2. No trace uses hidden state, future expert action, evaluation trajectory, or
   Phase 0-6 data.
3. Every composed edge satisfies the frozen SkillGraph constraints.
4. Negative controls that remove an admissible action or make a skill
   ineligible are rejected or abstained from rather than silently substituted.
5. Trace records are complete enough to audit node selection, edge selection,
   rejection, and terminal action decisions.

Only after this gate is pre-registered, executed, and passed may a separately
versioned WebShop construction plan be considered. WebShop is not a fallback
dataset or parallel build during ALFWorld TG0-TG3.

## Historical isolation and contamination control

All ACL 2027 Phase 0-6 materials are `FROZEN / READ-ONLY` for TraceGraph.
They may be cited only as motivation or appendix diagnostics. They must never
be modified, rerun, tuned on, sampled as TraceGraph data, used to build a
SkillBank, used for prompt examples, used to choose thresholds, or used as an
evaluation substrate. In particular, Phase 6 is not a TraceGraph core
experiment and must not be executed, resumed, or used as a source of new
TraceGraph claims.

Each later TraceGraph artifact must declare `experiment_line`, the data split,
the source trajectory identities, the permitted runtime inputs, and a
contamination audit showing zero Phase 0-6 data dependence. Any provider or
model call remains prohibited unless a later, separately versioned plan opens
it through explicit user authorization.

## Claim boundary

TraceGraph TG0-TG3 can support a claim that observable-state-constrained skill
composition is or is not mechanically auditable under its frozen protocol. It
cannot by itself support claims of universal accuracy gains, cross-domain
generalization, WebShop transfer, or benefits from historical ACL 2027 phases.