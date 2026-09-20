# Phase 1K: Paired-model capability preflight

## Decision

The zero-network paired-model preflight passed. Four requests were frozen for `qwen3.6-flash` and `qwen3.8-max` across OfficeQA `UID0001` and SpreadsheetBench `45635`. Network calls and paid calls were both zero.

- Aggregate fingerprint: `46f82a0386e7cc33fa1d134f829275fdf8e4bf8b31bf8c42237a371713edbd89`
- Unique request hashes: `4/4`
- Same OfficeQA content across models: passed
- Same SpreadsheetBench content across models: passed
- Explicit 12-item `{period, value}` OfficeQA operands: passed
- Explicit independent per-column SpreadsheetBench semantics: passed
- Reference-answer leakage: none
- Golden-formula leakage: none

The OfficeQA output limit is 1,200 tokens. The SpreadsheetBench limit is 1,400 tokens with exactly 12 compact edits and an explanation capped at 160 characters. Thinking is disabled and temperature is zero for both models.

## Scientific consequence

This is protocol readiness, not method-effect evidence. It does not strengthen or weaken the typed-prior, sparse-probe, or three-way triage claims. It creates a fair decision point for choosing a task-valid substrate.

A live successor should execute exactly four calls in the frozen order. If `qwen3.6-flash` passes both tasks, it remains viable. If only `qwen3.8-max` passes, the stronger model should become the substrate. If neither passes, the OfficeQA/SpreadsheetBench route or the real-task claim scope must change before any 24/40 scaling.

The four paid calls and the OfficeQA 24 / SpreadsheetBench 40 batch remain unauthorized and closed.