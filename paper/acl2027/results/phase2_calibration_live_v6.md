# Phase 2 Token Plan Calibration Live v6

## Scope

The user authorized only the Phase 2 v6 calibration stage for exactly 60
`qwen3.7-plus` Token Plan calls. Requests omitted `max_tokens`, used temperature
0, disabled thinking, allowed zero retries, and prohibited every later Phase 2
stage and formal scaling. The repository retained its CNY 0.50 hard stop as an
additional safety control rather than a user-requested budget.

## Pre-execution gates

- The immutable Token Plan route-preflight v6 manifest remained unchanged at
  SHA-256 `e949e266c827772de49ea7c6c0e498295d6ae61baf10f73d0fd3c5a123b32b99`.
- A separately bound live orchestrator persisted request starts before
  transport, enforced one-second start spacing across restarts, refused
  ambiguous retries, and closed authorization on completion or terminal error.
- The focused zero-network authorization, pacing, route, v5, and handoff suite
  passed 31/31. Handoff validation passed with 33 completed phases and 1,070
  immutable runs.

## Execution result

The first request used the Beijing Token Plan compatible endpoint and returned
`HTTP 401 Unauthorized`. The runner durably wrote one request-start event and
one terminal ledger row, made zero retries, and did not attempt the remaining
59 calibration requests. There were zero duplicate or out-of-scope requests,
no provider-accepted calls, no request ID, and no usage metadata. Consequently,
exact token usage and exact CNY cost are unknown; the known-usage cost lower
bound is CNY 0.0, not an exact cost.

The capability eligibility gate is unevaluable and therefore failed
incomplete. This result is transport authorization failure, not model
capability, prior-transfer, triage, or method-effect evidence.

## Closure and decision

Authorization `phase2-calibration-token-plan-v6-20260814` closed immediately as
`closed_terminal_hard_stop`. The active authorization registry is empty;
provider, Qwen, paid API, later-stage, and formal-scaling permissions are all
false. This ledger is terminal and must not be resumed or retried.

Before any new provider attempt, a valid `DASHSCOPE_API_KEY` with access to the
Beijing Token Plan compatible endpoint must be supplied and a new explicit,
separately versioned authorization must be obtained. No later Phase 2 stage is
authorized by this run.

## Immutable evidence

- Open authorization SHA-256: `d35f15c63837dc42a64c5179f93602b07b3e2d0ec350a8befa2547d1fd98b906`
- Terminal ledger SHA-256: `52518c8f564ddf476062b2660c3f6e552ee4d8c000eac26b70bf958dcd7ca3f4`
- Request-start ledger SHA-256: `ecd51ea0a2153af9d5dede6ea74b2fd4c1a81efd3b7e634f35def8bb8f7734d5`
- Authorization closure SHA-256: `caf6daf553bd061b4dcf6fd23e2f478e49780aea0438ff78b11d12073a439292`
- Original audit SHA-256: `cfa39dc2442dd0e855c4739050ed96fbb2a41cf6ce4bffbfaf547a522c7e4271`
- The additive v6.1 audit supplement corrects only the unknown-usage cost
  classification and preserves every original artifact.
