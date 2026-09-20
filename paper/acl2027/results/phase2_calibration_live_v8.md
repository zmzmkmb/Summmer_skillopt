# Phase 2 Token Plan Calibration Live v8

## Scope

The user authorized only Phase 2 v8 calibration for exactly 60
`qwen3.7-plus` Beijing Token Plan calls. Requests omitted `max_tokens`, used
temperature 0, disabled thinking, requested JSON-object response mode, allowed
zero retries, and prohibited development acquisition, formal history, probe,
held-out execution, later stages, and formal scaling.

## Execution Integrity

All 60 logical requests completed and were accepted by the provider. There were
zero retries, duplicates, out-of-scope requests, or terminal errors. The
minimum request-start interval was 1.2107754 seconds, and authorization closed
immediately after the sixtieth call.

Exact usage was 69,910 input plus 502 output equals 70,412 total tokens.
Exact local accounting was CNY 0.143836. No request contained `max_tokens`.

## Frozen Eligibility Gate

The repaired v8 parser accepted all 60 responses as the exact JSON answer
object. Forty-five of 60 answers matched the frozen gold answers (75%), which
is exactly the inclusive upper boundary of the frozen accuracy band. The
complete-call, contract-validity, inclusive accuracy-band, minimum-success,
three-task-type, and five-skill-family checks all passed. The v8 eligibility
gate therefore passed.

This is a capability-calibration result for the repaired prompt contract. It
does not authorize or estimate any later Phase 2 causal stage.

## Decision

Phase 2 v8 calibration is closed completed with the eligibility gate passed.
Preserve the authorization, ledger, request-start ledger, audit, and closure
unchanged. Do not run development acquisition, formal history, probe, held-out
execution, any later Phase 2 stage, or formal scaling without a separate future
authorization and protocol.

## Immutable Evidence

- Open authorization SHA-256: `a9e4ca9ae0003a72249f5ff52d16c09d765f065a24efddb84f3e7f26e731e86c`
- Ledger SHA-256: `a22a83cf2a148a027b4fa513c626d3db622474c087df3a0587e315efb4c690f0`
- Request-start ledger SHA-256: `3c866edc6ee13a2055b0ce17aa62320cbbf80ec79957c1583121c52e21589879`
- Audit SHA-256: `d10dfe69eb9a2f2165ea9f1cd18aec1801f468d47420b50617b233bf19dbd1a8`
- Closure SHA-256: `00c521f476716a2c48e70f42452112c19a68e73bfefe953dfb6cea4acff284da`
- Closed authorization registry SHA-256: `1f3d2deb1afb5e72f9b2b9c4c3c54dd42b73bd51609834599a2c7118af6cef1d`
