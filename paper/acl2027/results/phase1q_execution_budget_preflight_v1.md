# Phase 1Q: execution eligibility and budget preflight

## Purpose

Phase 1Q converted the frozen Phase 1P contribution-aligned design into an
auditable execution plan. It bound every prior/gate condition to an immutable
candidate and fresh cold fallback, checked local executor eligibility, and
derived conservative call and cost matrices without provider access.

This phase is protocol and budget evidence only. It does not measure any
real-task method effect.

## Audit result

The immutable zero-network preflight passed all 19 checks:

- all Phase 1P, Phase 1O, and skill-document hashes matched;
- all six prior-by-gate candidate bindings were present;
- candidate and fallback branches were charged equally;
- all 48 task identities received an explicit executor decision;
- OfficeQA: 24/24 eligible, with no reference-answer access;
- SpreadsheetBench: 24/24 eligible, with no golden-cell-value access;
- unsupported identities would route to `abstain`, with no silent exclusion;
- retries remain disabled and one provider attempt is allowed per logical call;
- future request bodies must omit `max_tokens`;
- provider, paid, network, and formal-scaling calls remained zero.

Decision:

```text
execution_plan_frozen_paid_execution_closed
```

Aggregate fingerprint:

```text
de85e8ad2c72f4edea5585ae2147a782bb11545cbf31f72a3ac6da41326df00d
```

## Call and cost matrix

| Plan | Calls | Candidate | Fallback | Planning tokens | Planning ceiling |
|---|---:|---:|---:|---:|---:|
| Development only | 192 | 96 | 96 | 720,000 | CNY 39.744 |
| Staged confirmation | 384 | 192 | 192 | 1,440,000 | CNY 79.488 |
| Full frozen design | 960 | 480 | 480 | 3,600,000 | CNY 198.720 |

The monetary values use configurable planning assumptions of CNY 20 per
million input tokens and CNY 80 per million output tokens. They are not an
Alibaba Cloud or Token Plan quotation, not an execution authorization, and
not request-side token limits. Current provider rates must be verified before
any paid successor is authorized.

## Scientific interpretation

Phase 1Q removes execution-eligibility and budget ambiguity. It does not
strengthen the empirical status of typed priors, sparse-probe
representativeness, or candidate-retaining triage. The ACL main claim remains
partially supported, not established, and the paper direction does not
change.

The full frozen design fits just under the historical CNY 200 planning bound
only under the stated assumptions. A staged path remains scientifically and
financially safer because it exposes implementation or attribution failures
before the full 960-call design.

## Next step

Phase 1R should remain zero-network and freeze the exact 192-call
development-only runner, request identities, resume/audit behavior, and hard
stops. Paid execution, `qwen3.8-max`, the legacy 24/40 batch, and formal
scaling remain closed pending a separate provider-rate review and explicit
authorization.
