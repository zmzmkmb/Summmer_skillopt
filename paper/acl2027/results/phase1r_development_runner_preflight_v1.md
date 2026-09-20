# Phase 1R: development-only runner preflight

## Purpose

Phase 1R materialized the exact Phase 1Q development design as a deterministic,
resumable runner before any provider access. The runner covers:

```text
3 prior types x 2 probe strata x 2 gate policies x 2 task families
x 4 probes x 2 candidate/fallback branches = 192 calls
```

This phase is runner-readiness evidence only. It does not measure a real-task
method effect.

## Audit result

The immutable zero-network preflight passed every check:

- 192 unique logical calls and 192 separately executed physical requests;
- 24 condition cells with four probes and both charged branches;
- 96 candidate and 96 fresh cold-fallback calls;
- `max_tokens` absent, zero retries, and one attempt per logical call;
- deterministic append-only resume from an exact completed-plan prefix;
- hard stops on unknown usage, response-contract failure, or plan drift;
- exact usage retained when a response is malformed after usage is returned;
- explicit abstention exercised in the scripted audit;
- bounded local OfficeQA evidence and deterministic spreadsheet snapshots;
- 0 network calls, 0 provider attempts, and 0 paid API calls.

Decision:

```text
development_runner_preflight_passed_paid_execution_closed
```

Aggregate fingerprint:

```text
6e5fd2b207cde96b7c75d79eafaf7852b4e4318d0a187d437ff522f49356480e
```

The Phase 1P/Q/R regression passed 19 tests. The final Phase 1R targeted suite
passed 9 tests after direct-script execution was also verified.

## Request materialization

The immutable plan contains 52 unique request bodies across 192 logical calls.
Duplicate bodies are not cached or reused: all condition identities remain
separate physical requests. Compact prompt material totals approximately
1.35 million characters:

| Family | Calls | Min chars | Mean chars | Max chars |
|---|---:|---:|---:|---:|
| OfficeQA | 96 | 2,663 | 8,396.9 | 17,643 |
| SpreadsheetBench | 96 | 1,535 | 5,633.5 | 10,257 |

These character counts are not provider token counts. Phase 1Q's CNY 39.744
development estimate remains a planning assumption, not a quotation or
authorization. Current Token Plan rates and tokenizer usage must be reviewed
before a paid successor is frozen.

## Scientific interpretation

Phase 1R removes runner, resume, accounting, and request-materialization
ambiguity. It does not establish that contextual priors outperform
copied-global or global-only priors, that representative probes predict the
downstream stream better than shifted probes, or that candidate-retaining
triage improves safety over destructive gating.

The ACL main claim therefore remains partially supported, and the paper
direction does not change. The project should stop adding broad protocol
micro-phases. The next meaningful step is a separately authorized
development-only execution of this 192-call design after current rate and
token review. That result is the first one capable of changing the central
claim status.

