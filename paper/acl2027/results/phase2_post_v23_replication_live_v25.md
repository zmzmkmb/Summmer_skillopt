# ACL 2027 Phase 2 post-v23 replication live v25

## Scope

This was the explicitly authorized replication-only execution of the immutable v24 schedule. It used exactly 320 qwen3.7-plus attempts, temperature 0, zero retries, no `max_tokens`, JSON-object responses, and CNY 3.50 stage and cumulative ceilings. Calibration, development acquisition, formal history, probe, held-out, later stages, other models, and formal scaling were not authorized.

## Execution audit

All 320 attempts completed with 320 unique logical requests, request hashes, and provider request IDs. The request-start and ledger hash chains, exact-prefix accounting, and one-second pacing passed. Usage was exact: 694,816 input tokens plus 2,579 output tokens equals 697,395 total tokens. Local cost was exactly CNY 1.410264, below both ceilings. There were zero retries, terminal rows, duplicates, or calls in forbidden stages. Authorization closed automatically at completion.

## Replication gate

All 320 responses were contract-valid. Accuracy was cold 59/80, copied-global 61/80, global-only 57/80, and contextual-typed-prior 59/80. The replication-only paired comparison was contextual typed prior minus global-only = +0.0250, with 4 wins, 2 losses, and 74 ties. Under the unchanged v21/v23 preregistered gate, this is **negative** because typed losses are at least 2; the positive threshold was not met. The result does not justify a positive causal typed-prior claim.

Audit fingerprint: `35a683a78dd6057b8e3e5122373de024706eba033e3742c04eaf081fdba0c779`.
