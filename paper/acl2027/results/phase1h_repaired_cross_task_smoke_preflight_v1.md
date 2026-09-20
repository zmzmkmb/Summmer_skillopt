# Phase 1H: Repaired cross-task smoke preflight

## Decision

The zero-network preflight passed. Exactly one OfficeQA request (`UID0001`) and one SpreadsheetBench request (`45635`) were resolved from frozen local inputs and serialized in the required order. This config cannot execute live, and the OfficeQA 24 / SpreadsheetBench 40 batch remains closed.

## Frozen requests

- Model: `qwen3.6-flash`
- Temperature: `0`
- Thinking: disabled
- OfficeQA maximum output tokens: `1200`
- SpreadsheetBench maximum output tokens: `1800`
- OfficeQA request SHA-256: `47b00e72aad2925d904f1ae66f50a6dc19ac3a0ec50241550d6f6c2e346a8c39`
- SpreadsheetBench request SHA-256: `f57b377fe13233f3177f84f3b98f07dd3abfb1cdd3dd2b59542926a7a92ff4d2`

## Protocol checks

All 14 checks passed:

1. Exactly two requests were built in the frozen OfficeQA-then-SpreadsheetBench order.
2. The selected IDs are exactly `UID0001` and `45635` and belong to their frozen validation splits.
3. Both requests use the same model and temperature and have stable canonical hashes.
4. OfficeQA requires `answer`, provenance-rich `evidence`, and a structured `calculation` trace.
5. OfficeQA explicitly requires 12 calendar-month operands and forbids substituting a fiscal-year total.
6. The OfficeQA reference answer was not injected into the prompt.
7. SpreadsheetBench requires `target_range`, 12 exact per-cell `edits`, and `explanation`.
8. SpreadsheetBench forbids duplicate, missing, and out-of-range cells; no golden formula was injected.
9. Paid, network, live, and formal-scaling execution are disabled; the batch remains closed.

The focused and cross-phase regression suite passed `20/20` tests.

## Artifact audit

- Artifact: `artifacts/acl2027_phase1h_repaired_cross_task_smoke_preflight_v1`
- Expected/available runs: `1/1`
- Aggregate fingerprint: `170b5a7f356807d4ddaed42667392bee562ab31dca6b2ff3186db02213b2066a`
- Network calls: `0`
- Paid API calls: `0`

## Scientific interpretation

Phase 1H strengthens measurement validity: the next repaired smoke can test model behavior without the known Phase 1F temporal and output-schema confounds. It does **not** prove that typed/scoped priors improve real-task continual learning, that sparse probes predict downstream safety, or that three-way non-destructive triage outperforms simpler gates.

Therefore the paper's overall main claim remains **partially supported, not established**. No direction change is warranted from this preflight alone. The principal scientific risk remains sparse-probe representativeness, including the earlier accepted-but-harmful seed 176 and the unresolved SearchQA proxy-to-real mismatch.

## Next gate

A paid successor requires a separate immutable live-smoke config and explicit authorization. It may execute exactly these two frozen request payloads under the repaired response contracts. The 24/40 batch must remain closed until the two responses pass task-valid parsing, temporal/aggregation, workbook-execution, and exact-usage audits.