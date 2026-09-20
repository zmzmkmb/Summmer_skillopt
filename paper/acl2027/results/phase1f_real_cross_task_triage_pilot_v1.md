# Phase 1F real cross-task bounded smoke

## Decision

The two-call Token Plan smoke completed its full allowance but **did not pass the frozen smoke gate**. The provider and exact-usage path worked for both calls; the full OfficeQA 24 / SpreadsheetBench 40 batch remains closed, and paid permission was disabled without a retry.

## Measured result

| Task | Provider result | Task/schema result | Input | Output | Total |
|---|---|---|---:|---:|---:|
| OfficeQA UID0001 | Response + exact usage | Parseable JSON, wrong answer: 1580 vs reference 2602 | 1431 | 89 | 1520 |
| SpreadsheetBench 45635 | Response + exact usage | Strict schema failed because ` explanation` had a leading space; formula also disagreed with the golden workbook | 328 | 224 | 552 |
| **All paid attempts** | 2 attempts, 0 retries, 0 rate limits | Smoke gate failed | **1759** | **313** | **2072** |

The bounded submanifest reports 1520 tokens under its successful-call usage field. Exact paid accounting must include the schema-failed second response, so the audited total is 2072 tokens.

## Diagnosis

OfficeQA exposed a real temporal-aggregation error rather than a transport problem. The supplied table contains both a fiscal-year 1940 row (1580) and January-December 1940 monthly values; the model copied 1580 although the question asks for calendar-year expenditures, whose monthly sum is 2602.

SpreadsheetBench returned syntactically valid JSON but misspelled the required key as ` explanation`. Even after normalizing that key, its single global-range formula is not equivalent to the golden B5:E7 row-relative, per-column formulas. This is therefore more than a cosmetic parser failure.

## Scientific interpretation

This smoke does not evaluate copied-global, global-only, contextual, binary gate, triage gate, or frozen MOAR. It only establishes that real cross-task payloads can reach qwen3.6-flash with exact usage while revealing that the current one-shot task protocol is not reliable enough to unlock the paired batch. No ACL method claim should be drawn from these two calls.

## Next gate

Before any new paid call, freeze a new versioned no-network protocol that (1) makes calendar-versus-fiscal aggregation explicit without leaking the answer, (2) uses robust structured-output validation while retaining the raw response, and (3) represents SpreadsheetBench as executable per-cell workbook edits rather than accepting a textual formula sketch. A new paid smoke requires separate authorization.

## Provenance

- Config SHA-256: 24717350bf174736fbeb9769e7c15048274869b16ec7ddfae9e08efd9c41f95f
- Raw results SHA-256: 9195c952e67c1d72e50188c778b7c304ebe6dab7624822ba6e8cfac1db1ba364
- Aggregate fingerprint: f0fbb4b60827429c548856e29e24c393bd71a67d635f75f90b953c9815362bd4
- Public OfficeQA provenance: ModelScope mirror, fingerprinted locally against the frozen split