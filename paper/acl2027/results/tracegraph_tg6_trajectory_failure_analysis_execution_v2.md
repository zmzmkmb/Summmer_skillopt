# TraceGraph TG6 Trajectory Failure Analysis Execution v2

Date: 2026-09-05

## Scope

The freshly authorized WSL Ubuntu attempt executed the frozen 24-task
development schedule under all three conditions, for exactly 72 episodes.
The authorization was bound to the declared preflight and runner
fingerprints. Each episode used at most 50 steps, zero retries, and stopped
on the first hard invariant violation. Runtime inputs remained exactly
`observation`, `historical_actions`, and `admissible_actions`.

## Integrity outcome

- 72/72 episodes started and completed;
- 0 hard invariant violations;
- 0/72 successes;
- 0 network, provider, model, API, or paid calls;
- 100% terminal-action admissibility;
- 100% trace validity;
- 0 abstentions;
- every episode reached the 50-step environment-done boundary.

## Main diagnostic results

On the primary nine-task `look_at_obj_in_light` stratum, all three conditions
had a two-cycle episode rate of 9/9 (100%). Therefore neither trajectory
ablation achieved the preregistered 50% episode-rate reduction threshold.
The same 100% episode-level two-cycle rate occurred in the 15-task transfer
stratum.

The ablations nevertheless changed trajectory shape. Averaged over all 24
tasks, baseline used 2.0 unique terminal actions and had mean cycle-step rate
1.064; history-aware anti-cycle used 3.0 unique actions and mean cycle-step
rate 0.851; observable-progress-aware used 11.875 unique actions and mean
cycle-step rate 0.851. Observable-progress-aware also increased the mean
number of unique observable snapshots from 3.0 under baseline to 12.167.

## Frozen decision gate

The result is **negative** under the preregistered rule: neither trajectory
ablation reduced primary-stratum two-cycle episode rate by at least 50%.
This is a mechanism result, not a broad capability claim. The evidence is
consistent with trajectory-level diversification being insufficient to solve
the task when the allowed observable inputs do not identify the required
goal-progress state. No Phase 0-6 artifact, Phase 6 execution, WebShop asset,
other model, other dataset, provider call, or official-source fallback was
used.

## Artifact

Result JSON:
`artifacts/acl2027_tracegraph_tg6_trajectory_failure_analysis_authorized_attempt_v2/result.json`
