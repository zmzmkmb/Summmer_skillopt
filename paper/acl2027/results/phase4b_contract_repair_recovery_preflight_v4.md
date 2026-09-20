# ACL 2027 Phase 4B-R4 recovery preflight

This zero-network recovery preflight preserves the 72 complete Phase 4B-R3 responses as provenance, excludes all 73 spent logical/request identities, and freezes 28 new canonical identities: one replacement for the orphan source row 73 and 27 rows for the unattempted source suffix 74-100.

All 28 provider-visible payloads remain byte-for-byte equivalent to their source transport projections. The orphan replacement therefore deliberately repeats one already-spent provider-visible payload under a new logical ID and request hash. This is disclosed recovery of missing response coverage, not a retry or resume of the spent canonical request identity.

The combined plan restores the frozen 100-row, 20-task, five-condition grid. It still has 80 unique transport payloads and 20 identical `global_only`/`contextual_typed` pairs, so those labels remain causally non-identifiable.

No network, provider, model, paid, Phase 4C, replication, cross-domain, or formal-scaling call was made. Because orphan usage is unknown, no stage or cumulative cost ceiling is frozen here. A separately versioned live-execution preflight and fresh exact explicit authorization are required before any provider call.

Aggregate fingerprint: `fc668155d0e1d787fe45bf381f5958d8f9d5d78759be3c0bab3951580254f066`.
