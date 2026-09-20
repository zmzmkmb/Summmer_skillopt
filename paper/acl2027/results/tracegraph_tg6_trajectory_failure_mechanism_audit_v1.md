# TraceGraph TG6 Mechanism Audit v1

Date: 2026-09-07

## Status

This is a zero-network post-hoc audit of the completed TG6 trajectory
diagnostic. It reads 72 immutable episodes and 3,600 immutable transitions.
It runs no environment episodes and does not alter the frozen TG6 gate.

## Evidence

- 72/72 parent episodes and 3,600/3,600 transitions were audited.
- The runtime boundary remains exactly `observation`, `historical_actions`,
  and `admissible_actions`.
- The audit found 138 cross-task exact allowed-input fingerprint groups.
- Independent post-hoc task-surface parsing identifies 134 of those groups as
  containing different task targets. This is evidence that repeated execution
  can reach the same allowed-input state across different goals; it is not a
  claim that the initial task information is absent, because the initial
  observation contains the task sentence.
- When a two-action cycle was detected, an eligible action outside the cycle
  was available for 1,104 baseline transition states, 240 history-aware
  states, and 240 observable-progress-aware states.
- Goal-surface actions were available in 1,191 audited states. The selected
  action missed that post-hoc target surface in 1,066 baseline states
  (89.5%), 1,051 history-aware states (88.2%), and 1,078
  observable-progress-aware states (90.5%). This is a descriptive proxy, not a
  runtime label.
- Skill and edge switches frequently occurred on repeated observable
  snapshots: 987 baseline skill/edge switches, 900 history-aware skill/edge
  switches, and 826/828 observable-progress-aware skill/edge switches.
- Observable-progress-aware exploration produced 263 novel-action-to-novel
  state transitions out of 285 novel-action steps (92.3%). Thus action
  novelty was not equivalent to durable task progress.

## Interpretation

The strongest supported explanation is a representation-and-control failure:
the selector can diversify commands and switch SkillGraph nodes, but it does
not maintain a target-directed progress state that survives repeated room
states. History-aware anti-cycle control reduces direct cycle participation
without restoring completion. Observable-progress-aware control increases
exploration, but the frozen pilot still has 0/24 successes per condition and
9/9 direct-cycle two-cycle episodes per condition.

The paper should therefore claim an auditable limitation of the current
observable-state selector and trajectory controller, not an information-
theoretic impossibility of the raw observation boundary.

## Decision

The original TG6 trajectory gate remains negative. This audit is mechanism
evidence only and does not authorize a new held-out phase, provider/model/API
call, Phase 6, WebShop, other model, other dataset, or Phase 0-6 reuse.

## Artifacts

- Config:
  `configs/acl2027/tracegraph_tg6_trajectory_failure_mechanism_audit_v1.json`
- Audit:
  `artifacts/acl2027_tracegraph_tg6_trajectory_failure_mechanism_audit_v1/audit.json`
- Manifest:
  `artifacts/acl2027_tracegraph_tg6_trajectory_failure_mechanism_audit_v1/manifest.json`
- Audit SHA-256:
  `ef3d2b3c5720dfa6003940e069f5fce634e5bebc478b148829fed2ed099c02b3`
- Tests: 3/3 cache-free tests passed.
- Handoff validation: passed.
