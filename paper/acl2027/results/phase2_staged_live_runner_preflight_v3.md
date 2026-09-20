# ACL 2027 Phase 2 staged live-runner preflight v3

## Decision

The zero-network v3 preflight passed focused and combined regression suites and is ready for independent acceptance review. This task did not create, open, or execute a provider authorization. All execution switches remain false, including `formal_scaling_allowed`.

## Regression and repairs

Independent audit reproduced the five v1 defects: the interleaved prefix stopped at 12 calibration rows; authorization-hash drift blocked cross-stage resume; whole-ledger length consumed new authorization quota; caller-authored string IDs could forge coverage; and the fingerprint did not bind runner source and tests. v1 remains immutable and non-authorizable.

v3 reuses the immutable v2 staged schedule as a strict 710-row bijection. It preserves every logical ID, canonical request body, family, partition, request hash, and original call index. Staged order is `60/10/160/160/320`; schedule SHA-256 is `01c4e03660648cf8d5b150f78bf783f273b99899fa6fa4ac8be495090e44dd60`.

Candidate materialization replays formal-history raw responses through the frozen parser/normalizer and private formal-history gold. It binds all 160 history rows, each task/request/response/family, gold, verifier, materializer, schema, provenance, and leakage audit. Forged verdicts, wrong gold, parser failure, family drift, duplicate identities, source/config drift, and forbidden gold access are rejected. Missing or insufficient supports are `coverage-incomplete`, not method failure. No real passing candidate artifact was written.

Probe analysis replays the complete probe ledger and probe-only gold with a deterministic analyzer. It binds coverage, ledger, analyzer, schema, condition grid, and gold-access boundary; caller-authored `passed=true`, hash replacement, ledger drift, analyzer drift, incomplete probe, and held-out leakage are rejected. No real probe audit was written.

The runner provides closed-by-default `preflight`, `audit`, `execute-stage`, and `resume` CLI commands. Open provider activation requires exact authorization bindings, all three execution switches, route/model/temperature/retry/max-token policy, stage calls, stage ceiling, and cumulative ceiling. Ledger entries persist raw provider response, exact usage, request and authorization provenance, terminal error, and a hash chain using temp-file flush/fsync/atomic replace. Resume validates the staged exact prefix and refuses terminal attempts, duplicates, order drift, unknown usage, provider exceptions, and cost breaches.

## Verification

Focused v3: **19 passed, 0 failed**. Combined requested suite: **60 passed, 0 failed**. The mock lifecycle covered `60 calibration -> 10 development -> 160 formal history -> trusted local materialization -> 160 probe -> trusted local audit -> 320 held-out`, exactly 710 rows, five authorization hashes, and no duplicate logical requests. Crash-resume was tested in every stage.

Estimated costs: calibration CNY 0.386880, development acquisition CNY 0.084960, formal history CNY 1.359360, probe CNY 1.455360, held-out CNY 2.910720, total CNY 6.197280. Hard ceilings: CNY 0.50, 0.11, 1.64, 1.75, 3.50, cumulative CNY 7.50. Ceilings are local audit controls, not request parameters.

The v3 aggregate fingerprint is `9794cfaaa01b7baf1b79fa334c1c2d30961b01f13da3522d46ce2770fdccac39`. It binds v3 config, closed authorization, runner, provider adapter, materializer, verifier, analyzer, tests, Phase 2 B v2 freeze, request plan, partition audit, staged schedule, gold manifests, schemas, and preflight audit. The v2 fingerprint `0bf2e595a664a37978f214c6aad64a50c9a03c4751a38a567c527c940dba8b70` is preserved.

All network, provider, model, Qwen, and paid API calls were **0**. Only after independent acceptance, the minimum future scope is a separately created calibration-only authorization for exactly 60 qwen3.7-plus calls, CNY 0.50 stage/cumulative ceiling, temperature 0, retries 0, no `max_tokens`, and formal scaling false. This task does not open that authorization.
