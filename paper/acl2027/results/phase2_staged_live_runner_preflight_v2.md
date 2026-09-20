# Phase 2 Staged Live-Runner Preflight v2

This zero-network v2 replaces v1 only as the authorizable staged-runner
preflight. All v1 files and its fingerprint remain unchanged. The v1 static
tests passed, but independent acceptance reproduced five defects that make v1
unsafe to authorize:

1. The original 710-request plan is family-block interleaved. A 60-call
   calibration authorization stopped silently after the first 12 calibration
   rows when v1 encountered the next partition.
2. A development authorization could not resume a calibration ledger because
   v1 required every historical row to carry the current authorization hash.
3. v1 charged the complete historical ledger length against the current
   authorization's call allowance.
4. v1 coverage accepted arbitrary caller-supplied string IDs, with no binding
   to verifier-confirmed trajectories, tasks, responses, families, or hashes.
5. The v1 aggregate fingerprint did not directly bind runner or test source.

## v2 execution contract

v2 preserves the original Phase 2 B v2 freeze and all 710 canonical requests.
It adds a deterministic execution-only schedule ordered by complete stages and
then by original `call_index`: 60 calibration, 10 development acquisition, 160
formal history, 160 probe, and 320 held-out requests. Every row preserves its
`logical_call_id`, `request_hash`, canonical body, original index, family,
condition, and partition. The strict bijection audit reports 710 rows, zero
omissions, zero duplicates, zero request-hash changes, and schedule SHA-256
`01c4e03660648cf8d5b150f78bf783f273b99899fa6fa4ac8be495090e44dd60`.

Exact-prefix resume is defined against this staged schedule. Historical ledger
rows permanently retain their producing authorization ID and SHA-256. An
immutable authorization registry resolves every historical authorization;
only rows appended under the current authorization consume its allowance.
Global and per-stage usage and CNY totals remain cumulative, terminal rows are
not retried, and stage order cannot be skipped.

Coverage can only be established by a hashed local candidate-materialization
artifact bound to the complete formal-history ledger and verifier schema. It
requires eight independent verifier-confirmed supports in each of five frozen
families and rejects duplicate trajectory, task, logical request, response, or
support identities. The checked-in preflight does not fabricate a passing
candidate artifact and therefore correctly reports `coverage-incomplete`.
Probe requires a passing coverage artifact. Held-out additionally requires all
160 exact probe rows and a passing probe audit bound to coverage, probe-ledger,
and analyzer/verifier hashes.

## Cost and authorization boundaries

| Stage | Calls | Estimated CNY | Hard ceiling CNY |
|---|---:|---:|---:|
| Calibration | 60 | 0.386880 | 0.50 |
| Development acquisition | 10 | 0.084960 | 0.11 |
| Formal history | 160 | 1.359360 | 1.64 |
| Probe | 160 | 1.455360 | 1.75 |
| Held-out | 320 | 2.910720 | 3.50 |
| **Cumulative** | **710** | **6.197280** | **7.50** |

Every stage requires a new immutable authorization bound to the v2 preflight,
schedule, freeze, request-plan and partition-audit hashes, exact route and
stage, `qwen3.7-plus`, temperature 0, retries 0, omitted `max_tokens`, a stage
call cap, stage CNY ceiling, and cumulative CNY ceiling. Formal scaling is not
a prerequisite and remains false throughout the staged pilot.

## Verification

The cache-free focused suite passed 27/27 tests. The combined Phase 2 and
handoff suite passed 41/41 tests. The focused suite includes the complete mock
lifecycle `60 -> 10 -> 160 -> coverage -> 160 -> probe audit -> 320`, ending
with exactly 710 staged-prefix ledger rows under five distinct authorization
hashes. It also covers the five v1 regressions, exact usage and cost stops,
single-attempt provider failures, invalid usage, stage authorization, trusted
coverage provenance, and closed-preflight zero-call behavior.

The immutable manifest directly binds the v2 preflight and closed authorization
configs, runner and test sources, Phase 2 B v2 freeze, original request plan,
partition audit, staged schedule, preflight audit, candidate schema, and probe
audit schema. Its aggregate fingerprint is
`0bf2e595a664a37978f214c6aad64a50c9a03c4751a38a567c527c940dba8b70`.
The run recorded exactly zero network, provider, model, Qwen, and paid API
calls. All execution switches remain false.

v2 is technically ready for creation of a separate calibration-only
authorization, but this preflight does not create or open one. The minimal
first scope is exactly 60 calibration calls, CNY 0.50 stage and cumulative
ceilings, zero retries, no `max_tokens`, and no later stage or formal-scaling
permission. This is execution-readiness evidence only and establishes no Phase
2 method effect.
