# ACL 2027 Phase 2 staged live-runner preflight v4

## Decision

The separately versioned zero-network v4 preflight is ready for independent
acceptance and is not authorized for provider execution. It repairs the v3
manifest defect by making disk-backed manifest and aggregate-root validation a
mandatory gate for preflight, audit, execute-stage, and resume.

## Integrity repair

The v4 manifest binds 16 files: runner, integrity module, manifest builder,
provider adapter, verifier, materializer, probe analyzer, tests, both gate
schemas, the Phase 2 freeze, request plan, partition audit, staged schedule,
formal-history gold, and probe gold. Every stored digest must be canonical
lowercase 64-hex SHA-256 and is recomputed from current disk bytes.

The canonical manifest payload is independently hashed and compared with the
frozen config root. A separately versioned closed authorization binds both the
v4 config SHA-256 and manifest aggregate fingerprint, in addition to the
schedule and frozen-input hashes. This avoids a circular config/manifest hash
dependency while ensuring any future authorization must name both roots.

Negative tests reject the v3-style 65-character hash, runner or test byte drift,
manifest field injection, aggregate tampering, and an attacker who rewrites a
bound file and recomputes both its ordinary file hash and the manifest
aggregate. All binding failures occur before provider invocation.

## Preserved lifecycle

The v3 trusted evaluation and durable execution contracts remain intact:
deterministic formal-history materialization, private gold boundaries, forged
coverage and probe rejection, exact `60/10/160/160/320` scheduling, 710 unique
logical calls, five authorization hashes, atomic ledger persistence, hash-chain
validation, terminal-attempt refusal, exact quotas and costs, and crash resume
in every stage with zero duplicates.

Focused cache-free tests passed **26/26**. The requested v4, v3, and handoff
combined suite passed **51/51**. Local `preflight` and `audit` both returned
`preflight-passed-closed` for 710 scheduled requests.

The v4 aggregate fingerprint is
`17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`.
Network, provider, model, Qwen, and paid API calls were all **0**. No
authorization was opened, and formal scaling remains false.

This is execution-readiness evidence only. It does not add method-effect
evidence. Independent acceptance must pass before creating a new
calibration-only authorization for exactly 60 qwen3.7-plus calls under a CNY
0.50 stage and cumulative ceiling.
