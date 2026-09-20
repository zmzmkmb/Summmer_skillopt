# ACL 2027 Phase 2 v23 Held-out Recovery

## Execution

The independently authorized v23 recovery executed the exact 88-row v22
held-out-recovery schedule. The route was `qwen3.7-plus`, temperature 0, zero
retries, no `max_tokens`, and JSON-object responses. The CNY 1.00 stage and
CNY 2.00 cumulative ceilings were not reached; exact local cost was CNY
0.433632.

The run completed 88/88 attempts with 88 completed calls, 88 unique logical
requests, 88 unique request hashes, and 88 unique provider request IDs. It
used 213,680 input tokens and 784 output tokens, for 214,464 total tokens.
Retries and terminal rows were zero. The request-start and response ledger
hash chains, one-second pacing, and exact-prefix resume checks passed. The
authorization closed automatically at completion.

## Combined Held-out Gate

The audit combines 232 preserved completed v21 rows with the 88 new v23 rows,
forming the frozen 320-row, 80-task x 4-condition grid. All four conditions
were contract-valid for all 80 tasks:

| Condition | Correct | Accuracy |
| --- | ---: | ---: |
| cold | 62/80 | 0.775 |
| copied_global | 59/80 | 0.7375 |
| global_only | 59/80 | 0.7375 |
| contextual_typed_prior | 60/80 | 0.7500 |

The frozen primary contrast, contextual typed prior minus global-only, is
`+0.0125` with 2 typed wins, 1 typed loss, and 77 ties. Under the pre-registered
gate (positive requires margin >= 0.125, at least 3 wins, and zero losses;
negative requires margin <= -0.125 or at least 2 losses), the result is
`inconclusive`.

This does not authorize or imply calibration, development acquisition, formal
history, probe, later Phase 2 stages, or formal scaling.

## Integrity

- v22 preflight fingerprint: `8bcd47e190bf68a00e7df10c4b9d9b3ae35dbd14a076396498cd84031f7b8306`
- v23 zero-network preflight fingerprint: `e9891345a199695d8aa54211e2d63360fdd49d0677f2a6291363b040268df280`
- v23 combined audit fingerprint: `9ebaa09c1afdb81e1fa59f7fb429dbc31f8df7b5b26dd10070dfc31552297c2b`
- v23 response ledger SHA-256: `99d6fc7090faa252ef4eb58c3f227587ae40eca2015e223c9e3848a62ef3220d`
- Network/provider/model/paid counters for v23: `88/88/88/88`
- Forbidden-stage counters: all zero
