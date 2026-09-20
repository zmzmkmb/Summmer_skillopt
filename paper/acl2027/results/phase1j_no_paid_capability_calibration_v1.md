# Phase 1J: Zero-network capability calibration

## Decision

The Phase 1J diagnostic gate passed with zero network calls and zero paid calls. The immutable Phase 1I failures remain failures: diagnostic recovery localized the errors but did not convert either response into a task-valid result.

Aggregate fingerprint: `a3e9b2be74bc41fa191fde13fbe2dfb92ac16f9d35d8619c6149bac71cc0b0af`.

## OfficeQA diagnosis

The response supplied 12 unique, provenance-bearing monthly evidence items. Independent recomputation produced the reference answer:

```text
132 + 129 + 143 + 159 + 154 + 153 + 177 + 200 + 219 + 287 + 376 + 473 = 2602
```

The failure channels are now separated:

- retrieval or provenance failure: `false`;
- operand-schema failure: `true`, because operands were numbers rather than `{period, value}` items;
- arithmetic failure: `true`, because the reported result was `2561`;
- answer mismatch: `true`, because the answer also reported `2561`.

The revised validator recomputes from evidence and requires both the answer and calculation result to agree. It explicitly forbids silently replacing a wrong model answer with the recomputed value.

## SpreadsheetBench diagnosis

All 12 complete edit objects were recovered from the immutable truncated prefix for diagnosis only. Cell coverage was exact, but all 12 formulas disagreed with the golden workbook. The response therefore has three independent failures:

- JSON completion failure: `true`;
- edit-schema/completion failure: `true` for the raw response;
- formula-semantics failure: `true` with `12/12` golden mismatches.

The frozen development semantics now state that each output column compares its own three people. The compact golden-shape JSON is 1,331 UTF-8 bytes, closes successfully, contains all 12 cells once, and stays below the 6,000-byte guard. This shows that output size is controllable, but it does not show that a model can generate the correct formulas.

## Model qualification

`qwen3.6-flash` is not currently qualified as the real-task substrate because both immutable Phase 1I tasks remain invalid. Phase 1J cannot determine whether the revised contract fixes generation without another live call, so it also cannot justify immediate replacement solely from local replay.

The next defensible test is a separately authorized paired capability confirmation using the same repaired two-task contract for `qwen3.6-flash` and one stronger candidate such as `qwen3.8-max`. The OfficeQA 24 / SpreadsheetBench 40 batch must remain closed until at least one model-contract pair meets the task-valid floor.

## Paper consequence

This phase strengthens protocol validity and error attribution, not the paper's central method claim. It confirms that retrieval, arithmetic, schema, completion, and formula-semantic failures can be audited separately while negative evidence is retained. It does not test copied-global/global-only/contextual priors, sparse-probe representativeness, or accept/reject/abstain deployment behavior.

Therefore the ACL mainline remains unchanged and partially supported, not established. The real-task evidence route is still blocked. If the repaired paired confirmation cannot produce a task-valid floor, the evaluation suite or the scope of the real-task claim must change before scaling.
