# Phase 1G no-paid cross-task protocol repair

## Decision

The zero-call local preflight **passed**. The repaired protocol separates OfficeQA retrieval evidence from temporal/aggregation validity, preserves every structured-response normalization, and requires SpreadsheetBench output to cover the target range with executable per-cell edits. Paid API permission and the OfficeQA 24 / SpreadsheetBench 40 batch remain closed.

## OfficeQA development scale

Phase 1G freezes eight validation examples rather than using the full 246-question dataset:

- IDs: UID0001, UID0027, UID0039, UID0086, UID0070, UID0072, UID0217, UID0234
- Difficulty: 4 easy / 4 hard
- Document scope: 5 single-document / 3 multi-document
- Operation coverage includes calendar sums, temporal extrema, filtered sums, percent changes, range counts, percentage-point differences, means, and medians.

The 24-example validation split is reserved for confirmation after the protocol and model prompt are frozen. The complete 246-question corpus is not required for protocol development.

## Measured checks

All ten frozen preflight checks passed with zero provider calls:

- selected OfficeQA IDs resolve in the frozen validation split and local payload;
- a calendar-year trace with 12 distinct monthly operands is eligible for the deployment gate;
- the Phase 1F fiscal-year shortcut remains retrieval-supported but fails time-basis and period-count checks, so it is blocked before the gate;
- the Phase 1F whitespace-prefixed ` explanation` key is normalized to `explanation` while the raw response and normalization record are retained;
- normalization does not make the legacy single-formula SpreadsheetBench response acceptable;
- all 12 cells in B5:E7 receive exactly one formula edit, and the generated workbook reopens with every formula persisted.

## Scientific interpretation

This repair makes task failures identifiable as retrieval, temporal/aggregation, structured-output, workbook-execution, or deployment-gate errors. That separation is necessary before evaluating copied-global, global-only, contextual priors, or the accept/reject/abstain policy.

The spreadsheet preflight uses development-gold formulas to verify the execution and audit path. It does not claim that qwen3.6-flash can yet produce the new per-cell schema. Likewise, synthetic temporal traces verify the gate contract but do not provide new model accuracy evidence.

## Verification

- Tests: 16 passed across Phase 1G, Phase 1F smoke regression, and experiment handoff contracts.
- Network calls: 0
- Paid API calls: 0
- Config SHA-256: 1cc4cb092a8f9875bda2f5e16ca4c1851085316d2aefcc0d4309eede4f80ad38
- Aggregate fingerprint: d466de06903cc0625d1e9e85d6e847b04d3efd03e4079868740b16cc131a9584

## Next gate

Freeze a new immutable two-call smoke configuration and runner that uses the repaired OfficeQA trace schema and SpreadsheetBench per-cell edit schema. Review its zero-call request payloads before seeking separate authorization for any paid call. Do not open the 24/40 batch from Phase 1G.