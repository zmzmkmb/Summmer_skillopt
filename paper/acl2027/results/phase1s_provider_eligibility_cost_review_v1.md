# Phase 1S Provider Eligibility and Cost Review

Date: 2026-08-11

## Decision

The user explicitly confirmed on 2026-08-11 that the existing Token Plan endpoint
and key may be used for the frozen experiment, reported that the route had already
been tested successfully, and directed execution to continue without further
route delay. Phase 1S therefore uses:

`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`

The completed Phase 1R artifact remains unchanged. Phase 1S binds its exact
request plan by both file SHA-256 and stable content SHA-256.

## Frozen Execution Contract

- Model: `qwen3.7-plus`
- Logical and physical requests: exactly 192
- Candidate requests: 96
- Fresh fallback requests: 96
- Provider attempts per logical request: 1
- SDK and explicit retries: 0
- `max_tokens`: absent and forbidden
- Unknown usage or response-contract drift: terminal hard stop
- Request interval: at least 1 second between starts
- Route and key: existing user-confirmed Token Plan endpoint and `sk-` credential
- `qwen3.8-max`, 384-call staging, 960-call scaling, and the legacy 24/40 batch:
  closed

## Token and Cost Estimate

The input estimate uses the exact Phase 1R request materialization and the two
Phase 1N `qwen3.7-plus` usage observations as task-family calibration:

| Quantity | Tokens |
| --- | ---: |
| Calibrated input | 545,086 |
| Phase 1Q output envelope | 422,400 |
| Conservative input (+25%) | 681,358 |
| Conservative output (192 x 4,096) | 786,432 |

Using the reviewed Beijing list rates of CNY 2 per million input tokens and CNY
8 per million output tokens, the primary estimate is CNY 4.469372. The current
20% promotional estimate is CNY 3.5754976. The conservative list-price scenario
is approximately CNY 7.654172.

The user ceiling of CNY 200 is an accounting authorization ceiling only. It is
not a request-body field and must never be translated into `max_tokens`.

## Scientific Effect

This review improves provider compliance, cost validity, and execution
reproducibility. It adds no evidence yet for the three central method effects:
typed/scoped priors, probe representativeness, or candidate-retaining triage.
Those claims remain partially supported and require the 192-call execution.

## Next Gate

The existing `sk-` credential is present and the user authorization is recorded
for exactly 192 `qwen3.7-plus` calls. Rerun the zero-network regression, execute
the immutable plan once, close permission immediately, audit exact usage, and
score all three method effects.
