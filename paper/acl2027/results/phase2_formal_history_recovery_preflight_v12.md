# Phase 2 Formal History Recovery Preflight v12

The zero-network v12 preflight passed and authorization remains closed. It binds the immutable v11 32-call completed prefix, permanently spends and excludes the ambiguous timeout task `6d77bf0f08ad11ebbd83ac1f6bf848b6`, and creates exactly 128 new logical requests.

The new schedule contains one deterministic replacement attribute-comparison task plus the 127 v11 tasks that were never attempted. The replacement `c172f6c4097e11ebbdb0ac1f6bf848b6` was selected from 2,894 eligible unused attribute-comparison records after excluding Phase 1 data and all 350 Phase 2 calibration/development/history/probe/held-out IDs. No development output, probe task, or held-out task is reused.

The combined contract contains exactly 160 unique task IDs and logical calls: 32 per family. The live orchestrator is source-bound and inert without a separately created authorization. Mock regressions cover the complete 128-call lifecycle, exact-prefix interruption recovery, terminal refusal, ambiguous-start refusal, one-second pacing semantics, zero retries, no `max_tokens`, deterministic verifier replay, and the frozen minimum-eight-per-family coverage gate.

The new-stage cost ceiling is CNY 1.64. The v11 completed prefix has a known CNY 0.075602 lower bound, but its terminal timeout has unknown usage, so a combined exact historical cost claim remains forbidden.

Aggregate fingerprint: `8827222c7d290050969531b7ee6a7c049ac287b0e3098b0ba4f8b15c43b762fe`.

All network, provider, model, and paid API counters are zero. Probe, held-out, later stages, and formal scaling remain unauthorized.
