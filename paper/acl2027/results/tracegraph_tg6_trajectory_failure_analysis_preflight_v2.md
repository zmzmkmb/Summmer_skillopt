# TraceGraph TG6 trajectory failure-analysis preflight v2

Date: 2026-09-05

## Result

The v1 design could not be frozen because only 2 fresh paired `valid_seen`
and 7 fresh paired `valid_unseen` identities remained in the
`look_at_obj_in_light` family after the TG4 and TG6-v4 exclusions. The v2
design preserves all 9 of those direct-cycle identities and adds 15 fresh
multi-step transfer identities.

The zero-network preflight froze 24 fresh development tasks and 72 paired
condition rows:

- 9 direct-cycle replication tasks: 2 seen and 7 unseen;
- 7 `pick_and_place_simple` tasks: 5 seen and 2 unseen;
- 8 `pick_two_obj_and_place` tasks: 5 seen and 3 unseen.

All task identities are disjoint from the frozen TG4 schedule and the TG6 v4
result. The three conditions are the unchanged first-eligible baseline, a
history-aware anti-cycle ablation, and an observable-progress-aware ablation.
The runtime input boundary remains exactly `observation`,
`historical_actions`, and `admissible_actions`.

## Boundary

This is design-readiness evidence only. It made zero network, provider,
model, API, or paid calls. `execution_authorized=false`; a fresh exact
authorization is required before the 72-row development pilot. The v1
failed preflight is preserved and is not reused.

Preflight aggregate fingerprint:
`b82976f1c5be80bd00d67f4e0397f8a72f4eb56282536864ca649a8f9fe74d07`.
