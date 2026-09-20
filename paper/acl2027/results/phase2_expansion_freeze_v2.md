# Phase 2 B Expansion Freeze v2

The Phase 2 B plan is frozen as a new design-only, ready-for-authorization version. Five families each contain 12 calibration, 2 development-acquisition, 32 formal-history, 8 probe, and 16 held-out tasks: 350 mutually exclusive tasks total.

The future request plan contains 60 calibration requests, 170 maximum history requests, 160 probe requests, and 320 held-out requests, for exactly 710 logical requests and 710 worst-case physical attempts at zero retries. The estimated cost is CNY 6.197280 and the conservative ceiling is CNY 7.50.

The plan binds `qwen3.7-plus`, temperature 0, no `max_tokens`, zero retries, exact-prefix append-only resume, deterministic request hashes, and terminal hard stops for drift, duplicate IDs, unknown usage, provider exceptions, non-prefix resume, and cost ceiling. It opens no authorization. Stage 4 requires at least eight independent verifier-confirmed supports per family; failure is `coverage-incomplete`, not method failure, and forbids probe and held-out execution.

No model, provider, paid, or network call occurred. See the readiness audit, partition audit, request plan, and run manifest for hashes and provenance.
