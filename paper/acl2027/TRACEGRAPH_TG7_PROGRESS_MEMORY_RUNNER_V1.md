# TraceGraph TG7 Progress-Memory Runner v1

This runner binds the frozen TG7 progress-memory preflight to a local,
zero-network ALFWorld readiness check. It implements three paired selectors:
`baseline_first_eligible`, `task_anchor_aware`, and `progress_memory`.

The selector receives only `observation`, `historical_actions`, and
`admissible_actions`. The anchor is parsed once from the initial observation.
The progress ledger records only observable text/action evidence and carries
field-level provenance. No planner state, PDDL state, task file, evaluation
label, expert trajectory, provider, or model call is available to runtime
selection.

Version 1 is closed for episodes: it permits zero-step reset readiness only.
Any 72-row execution requires a separately versioned authorized configuration
whose hashes are bound to the completed readiness and exact user
authorization.
