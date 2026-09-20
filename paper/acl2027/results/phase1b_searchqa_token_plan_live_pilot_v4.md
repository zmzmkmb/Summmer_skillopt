# Phase 1B SearchQA Token Plan Live Pilot v4: Terminal Partial Result

Date: 2026-08-09

## Decision

The frozen v4 artifact is a terminal partial result and must not be resumed or overwritten. The runner stopped correctly after a provider-side content inspection rejection returned no usage metadata. Paid API permission is disabled. Formal scaling remains disabled.

## Protocol

V4 added an output-only primary prompt override and at most one isolated format-normalization request. A repair request saw only the rejected raw model response, never the SearchQA question, context, skill, retrieval state, or gold answer. Primary and repair attempts had separate frozen token envelopes and shared attempt-first journaling.

## Preflight

- 2,448 zero-network logical calls completed.
- 2,579 deterministic attempts, including 131 visible retries.
- 8,010,240 simulated total tokens and zero paid calls.
- Reopening the completed preflight produced zero new calls and zero provider invocations.
- Summary fingerprint: `3dc5bab0de414fdcc202da327863b40765051613683385fea83dbd8e72b76655`.
- V3/V4 regression tests: 8 passed.

## Live Result

- Completed logical calls: 220 / 2,448.
- Provider attempts: 235.
- Successful attempts: 220.
- Failed attempts: 15.
- Format-repair attempts: 14 / 14 successful.
- Known-usage attempts: 234.
- Unknown-usage attempts: 1.
- Known input tokens: 546,814.
- Known output tokens: 8,507.
- Known total tokens: 555,321.
- Request IDs present: 234 / 235.
- Attempts with reasoning content: 0.
- Partial-call mean EM: 0.772727.
- Partial-call mean F1: 0.843598.
- Partial-call mean substring EM: 0.909091.

The first live smoke used one primary request, 3,432 input tokens and 9 output tokens, predicted `Grover Cleveland`, and obtained EM/F1/sub-EM of 1.0.

## Terminal Failure

The next primary request was rejected with HTTP 400 and provider code `data_inspection_failed`: the provider reported that the input text might contain inappropriate content. The exception contained provider error ID `chatcmpl-832b037e-fe7c-4044-9d96-eda49f6e648a`, but no token usage metadata. Under the frozen accounting contract, unknown usage requires immediate refusal of further paid execution.

This was not a formatting-repair failure. All 14 primary strict-parser failures were repaired successfully. The v4 artifact cannot be resumed because its terminal unknown-usage attempt is already journaled.

## Next Protocol Decision

Any continuation requires a separate v5 protocol. It must pre-register handling of provider content-inspection rejections and unknown usage without tuning on the held-out answer, use a new runner/config/artifact directory, and pass zero-network development fixtures plus a bounded smoke. V3 and v4 artifacts remain immutable.
