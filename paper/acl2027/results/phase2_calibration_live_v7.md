# Phase 2 Token Plan Calibration Live v7

## Scope

The user authorized only Phase 2 v7 calibration for exactly 60
`qwen3.7-plus` Beijing Token Plan calls. Requests omitted `max_tokens`, used
temperature 0, disabled thinking, allowed zero retries, and prohibited every
later Phase 2 stage and formal scaling. The new authorization bound the
replacement API-key fingerprint without recording the key itself.

## Execution integrity

The complete 60-call schedule finished in 215 seconds. All 60 logical requests
were unique, accepted by the provider, and durably recorded with exact usage.
There were zero retries, duplicates, out-of-scope requests, or terminal errors.
The minimum request-start interval was 1.4749244 seconds. Authorization closed
immediately after the sixtieth call and the active registry is empty.

Exact usage was 67,630 input plus 7,179 output equals 74,809 total tokens.
Exact local accounting was CNY 0.192692.

## Frozen eligibility gate

The frozen parser accepts only JSON objects containing exactly the `answer`
key. All 60 provider outputs were plain text, so strict contract validity and
strict answer correctness were both 0/60. The complete-call and five-family
coverage checks passed, but the overall eligibility gate failed. No later
stage was executed or authorized.

This failure is a protocol-format failure. The frozen request body says
"return the frozen response schema" but never includes the required exact JSON
schema. Representative outputs such as `King Lear`, `Williamsburg`, and
`Thunder Road` are plausible answers but are invalid under the frozen parser.
The result must not be reclassified after observing responses.

## Non-gating diagnostic

An additive read-only diagnostic normalized the plain text without changing
the scientific gate. Exact whole-response matching found 8/60 answers. A more
permissive gold-answer-contained diagnostic found 53/60, distributed as 11/12
fact retrieval, 11/12 attribute comparison, 10/12 bridge attribute comparison,
10/12 entity bridge, and 11/12 relation inference. The containment metric is
optimistic and diagnostic only; it cannot override the strict 0/60 contract
result or authorize later stages.

## Decision

Phase 2 v7 calibration is closed completed but eligibility-failed. Preserve the
authorization, ledger, pacing chain, audit, and diagnostic unchanged. Do not
run development acquisition, formal history, probe, held-out, or formal
scaling. Any repaired calibration would require a new prompt/version, a new
zero-network preflight, and new explicit authorization; v7 cannot be resumed.

## Immutable evidence

- Open authorization SHA-256: `d98f54688b452feafd36c930838b0c96c13755b07c55f5bb306cca994c64b9b2`
- Ledger SHA-256: `13f6680d2a66ca2304c43fda72e5effdb1ee61aa0f2c39a6938d34a90e04f6fc`
- Pacing ledger SHA-256: `f885a7c265eefa20ac58e55c090f512f371098dcc37b8783e681867f4ea36d07`
- Audit SHA-256: `8cdb1c3d5f96972626d779a3ed28db7dc271c5defbd2a9f07fe739c1834fd28f`
- Closure SHA-256: `7fdb7cc363b56adac59826d89d86890e301ec46283c20b3f57ffb04a901cc162`
- Plain-text diagnostic SHA-256: `f1b7e487cf9d57aec7a734498664252a8ff7c0d752bcf72e6953d4b78ad82cfb`
