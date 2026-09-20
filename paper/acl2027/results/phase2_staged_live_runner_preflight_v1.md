# Phase 2 Staged Live-Runner Preflight v1

The recovered v1 preflight now parses and binds the existing immutable Phase 2 B v2 freeze config, request plan, and partition audit by exact SHA-256. It does not modify or replace any Phase 2 B v2 artifact.

The local runner validates all 710 ordered logical requests and enforces append-only exact-prefix resume, authorization-hash continuity, zero retries, omitted `max_tokens`, exact usage, raw/error preservation on terminal stops, stage boundaries, per-stage and cumulative call limits, per-stage and cumulative cost ceilings, independent verified-family coverage, and a complete exact-hash probe audit before held-out execution.

Staged pilot authorization is independent of formal scaling. `formal_scaling_allowed` must remain false. A provider attempt additionally requires `paid_api_allowed`, `provider_calls_allowed`, and `qwen_authorization_open` to be true in a separately versioned authorization config that binds this preflight hash; the stage must be explicitly listed with call and cost ceilings. The checked-in authorization remains closed with zero authorized stages and zero authorized calls.

| Stage | Calls | Estimated CNY | Hard ceiling CNY |
|---|---:|---:|---:|
| Calibration | 60 | 0.386880 | 0.50 |
| Development acquisition | 10 | 0.084960 | 0.11 |
| Formal history | 160 | 1.359360 | 1.64 |
| Probe | 160 | 1.455360 | 1.75 |
| Held-out | 320 | 2.910720 | 3.50 |
| **Cumulative** | **710** | **6.197280** | **7.50** |

The minimum recommended first authorization is calibration only: exactly 60 `qwen3.7-plus` calls, temperature 0, zero retries, no `max_tokens`, a CNY 0.50 stage and cumulative accounting ceiling, and formal scaling still false. Later stages require fresh separately versioned authorization after the preceding ledger is audited.

The cache-free focused suite passed 16 tests. This preflight made exactly zero network, provider, model, Qwen, and paid API calls. Its aggregate fingerprint is `1a4545b63f1b994505e3a724358518143ff50a68f444bb87cce49f64ba066a30`; runner source SHA-256 is `13ca56a78a1451e2ccaafc3f1b7aeb06afbcfcac2103540e9a161bc712f3ad8b`.
