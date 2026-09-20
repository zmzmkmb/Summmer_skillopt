# Phase 1S v2 Response-Resilience Preflight

Date: 2026-08-11

## Outcome

The separately versioned zero-network Phase 1S v2 preflight passed all 12
checks. It remains bound to the exact immutable Phase 1R 192-call request plan
and preserves the terminal Phase 1S v1 config, request plan, manifest, and
results hashes.

| Measure | Result |
| --- | ---: |
| Frozen logical calls | 192 |
| Candidate / fallback calls | 96 / 96 |
| Preflight checks | 12 / 12 passed |
| Network calls | 0 |
| Paid API calls | 0 |
| Provider attempts | 0 |
| Reused Phase 1S v1 spent calls | 0 |

## Repaired Execution Semantics

The scientific response schemas are unchanged. The only permitted
normalization removes a leading Unicode BOM, outer whitespace, and one complete
outer Markdown JSON fence. It does not rename fields, insert fields, delete
fields, coerce types, repair answers, or relax schemas.

For every provider response with exact usage, v2 preserves the raw provider
text and normalized text before parsing. Malformed JSON and schema-invalid
responses become visible `invalid_output` records for that condition and
execution continues. They remain negative scientific outcomes and are not
silently excluded.

Unknown usage, provider exceptions, request-plan drift, call-count drift,
authorization drift, and the accounting ceiling remain terminal hard stops.
Terminal records remain non-resumable. Non-terminal valid and invalid records
form an exact append-only plan prefix for deterministic resume.

## Simulated Cases

- Valid execution and valid abstention both passed.
- Malformed JSON with known usage was preserved, charged, marked invalid, and
  followed by the next logical call.
- Valid JSON with a wrong `calculation` type was not coerced; it was preserved,
  charged, marked invalid, and followed by the next logical call.
- Unknown usage hard-stopped immediately.
- Pause and resume consumed each logical call exactly once.
- Request-plan drift was rejected.

## Scientific Interpretation

This fixes execution validity only. It does not add evidence for typed priors,
probe representativeness, or candidate-retaining triage, so the ACL main claim
remains partially supported and unchanged.

The v2 preflight does make the planned development experiment scientifically
usable: response-format failure rates can now be compared as part of each
condition rather than aborting the entire factorial design after one call.
Any provider execution still requires a separately immutable live
authorization config and new explicit authorization.

## Integrity

- Request-plan stable SHA-256:
  `9eeb21f0a40460deb4db4d480dce3f8bc5f329a2ea3ba98b6d730f3f1391cd41`
- Terminal v1 manifest SHA-256:
  `289f5567c07bfe225a0cef59feeadc32244d9c7540103eef34669535d8e8553d`
- Preflight audit SHA-256:
  `d36392442aae339948f134b0aed83a812381b747ea66faeb508c02eb035ae169`
- Preflight manifest SHA-256:
  `3608db2ee3a30561bb699c412372526358379643a9fefbba4772151fe7bc1a7f`
