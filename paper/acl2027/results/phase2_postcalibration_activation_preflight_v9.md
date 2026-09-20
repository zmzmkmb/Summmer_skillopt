# Phase 2 Post-Calibration Activation Preflight v9

## Decision

This zero-network preflight accepts the completed v8 calibration as the only
new capability prerequisite for Phase 2 activation. It does not reopen the v8
authorization and does not authorize formal history, probe, held-out, or formal
scaling execution.

## Bound Evidence

The v8 audit records 60 completed calls, 60 exact-JSON contract-valid outputs,
45 correct answers, a passed eligibility gate, and a closed authorization. The
v4 preflight and Phase 2 B freeze remain the immutable source for the 710-call
full design.

## Next Authorization Boundary

Any future live authorization may cover only the 10-call development-acquisition
stage: two calls in each of five families, `qwen3.7-plus`, zero retries, no
`max_tokens`, and terminal hard stops for accounting, provider, schedule,
authorization, duplicate, and cost failures. Development outcomes are
diagnostic only and cannot become formal history.

Formal history, probe, held-out execution, and formal scaling remain closed and
require separately versioned preflight and explicit user authorization.
