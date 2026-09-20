# TraceGraph TG7 Progress-Memory Runner v1

Date: 2026-09-09

## Design and readiness

TG7 froze 24 fresh ALFWorld task identities and 72 paired rows across
`baseline_first_eligible`, `task_anchor_aware`, and `progress_memory`.
The WSL reset-only readiness gate passed 24/24 tasks with zero actions,
episodes, and network/provider/model/API/paid calls.

The preflight aggregate fingerprint is
`48470f6d571cf4a40547304ea475a536ab9855b40efaf644839b40e7fcdfc0d2`.
The WSL readiness artifact is
`artifacts/acl2027_tracegraph_tg7_progress_memory_runner_v1/readiness_wsl_20260908.json`
with SHA-256
`b5ed392361360e0c3152e43a73f42da87be74b545a2521b1491fbb9c6089f3fc`.

## Authorized execution result

The exact authorized Ubuntu WSL runner completed the frozen schedule:

- 72/72 rows started and completed; 24 rows per condition;
- 50 transitions per row, 3,600 transitions total;
- 0/72 successes and 0 hard-invariant violations;
- 0 retries and 0 network/provider/model/API/paid calls;
- 100% trace validity, terminal-action admissibility, progress-ledger
  validity, and progress-ledger provenance completeness;
- runtime inputs remained exactly `observation`, `historical_actions`, and
  `admissible_actions`.

The immutable result is
`artifacts/acl2027_tracegraph_tg7_progress_memory_runner_v1/result_authorized_wsl_20260909.json`
with SHA-256
`34ea3456f7d361761b9c6eff369c466a799a1c2427da18f703060c27546ed4ff`.
It is bound to authorization receipt SHA-256
`c91e196d07ef65da6fe3206efe976c3922f8f9440d82ffc2e921fc59bedd39e6`,
authorized runner config SHA-256
`3189e528902bd23c9fcd73f084a4c07d8cd8b7a649b39923201ef128c9c8dcc7`,
the preflight aggregate above, and the WSL readiness hash above.

## Condition-level audit

`baseline_first_eligible` had 0/24 successes, 24/24 two-cycle episodes,
1,128 repeated snapshots, and a 9.38% post-hoc target-surface hit rate.
`task_anchor_aware` had 0/24 successes and 24/24 two-cycle episodes, while
its target-surface hit rate increased to 75.63%; this did not translate into
completion. `progress_memory` had 0/24 successes, 22/24 two-cycle episodes,
469 repeated snapshots, and an 11.88% target-surface hit rate.

The preregistered progress gate is not met: the paired success gain is 0 and
the pooled two-cycle rate changes from 100.0% to 91.67%, an 8.33% relative
reduction rather than the required 50%. The anchor-only gate is also not met
because the anchor condition improves target-surface selection but not task
success, while progress memory adds no completion gain.

A post-hoc audit of the raw result found 179 cross-task allowed-input
collision groups, including 24 groups with conflicting task-goal tuples.
Therefore the preregistered interpretation is **representation-limited**:
the augmented selectors obey the runtime contract and preserve all
invariants, but the available representation/controller does not turn legal
actions into durable task progress.

This is not evidence of information-theoretic impossibility and is not a
capability result for any provider or model. Preserve the raw result and do
not rerun or retry the 72 rows. Any follow-up must be a separately versioned,
zero-network design that changes the observable progress representation or
controller and obtains fresh authorization before execution.
